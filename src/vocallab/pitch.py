from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Protocol

import numpy as np
from scipy.ndimage import median_filter

from vocallab.audio import load_wav
from vocallab.models import PitchSettings, PitchTrack
from vocallab.music import hz_to_midi


class PitchEngine(Protocol):
    name: str

    def track(
        self, samples: np.ndarray, sample_rate: int, settings: PitchSettings
    ) -> PitchTrack: ...


class AutocorrelationPitchEngine:
    name = "autocorrelation-v1"

    def track(self, samples: np.ndarray, sample_rate: int, settings: PitchSettings) -> PitchTrack:
        frame_length = max(128, int(round(settings.frame_seconds * sample_rate)))
        hop_length = max(1, int(round(settings.hop_seconds * sample_rate)))
        if samples.size < frame_length:
            samples = np.pad(samples, (0, frame_length - samples.size))
        frame_count = 1 + (samples.size - frame_length) // hop_length
        times = (np.arange(frame_count) * hop_length + frame_length / 2) / sample_rate
        frequencies = np.zeros(frame_count, dtype=np.float64)
        confidence = np.zeros(frame_count, dtype=np.float64)
        rms = np.zeros(frame_count, dtype=np.float64)
        minimum_lag = max(2, int(sample_rate / settings.max_hz))
        maximum_lag = min(frame_length - 2, int(sample_rate / settings.min_hz))
        window = np.hanning(frame_length)
        fft_length = 1 << (2 * frame_length - 1).bit_length()

        for index in range(frame_count):
            start = index * hop_length
            frame = samples[start : start + frame_length].astype(np.float64)
            rms[index] = np.sqrt(np.mean(frame * frame))
            if rms[index] < 1e-4:
                continue
            frame = (frame - np.mean(frame)) * window
            spectrum = np.fft.rfft(frame, n=fft_length)
            correlation = np.fft.irfft(spectrum * np.conjugate(spectrum), n=fft_length)
            correlation = correlation[: maximum_lag + 2]
            if correlation[0] <= 1e-12:
                continue
            normalized = correlation / correlation[0]
            search = normalized[minimum_lag : maximum_lag + 1]
            local_peaks = np.flatnonzero(
                (search[1:-1] >= search[:-2]) & (search[1:-1] > search[2:])
            ) + 1
            if local_peaks.size:
                strong = local_peaks[search[local_peaks] >= 0.9 * np.max(search[local_peaks])]
                peak_index = int(
                    strong[0]
                    if strong.size
                    else local_peaks[np.argmax(search[local_peaks])]
                )
            else:
                peak_index = int(np.argmax(search))
            lag = float(minimum_lag + peak_index)
            if 0 < peak_index < search.size - 1:
                left, center, right = search[peak_index - 1 : peak_index + 2]
                denominator = left - 2 * center + right
                if abs(denominator) > 1e-12:
                    lag += 0.5 * (left - right) / denominator
            frequencies[index] = sample_rate / lag
            confidence[index] = float(np.clip(search[peak_index], 0.0, 1.0))

        raw_midi = hz_to_midi(frequencies)
        voiced = (confidence >= settings.voicing_threshold) & np.isfinite(raw_midi)
        corrected = _correct_octaves(raw_midi, voiced)
        smoothed = _smooth_voiced(corrected, voiced)
        nearest = np.rint(smoothed)
        cents = 100.0 * (smoothed - nearest)
        voicing = np.clip(confidence * np.minimum(1.0, rms / 0.01), 0.0, 1.0)
        return PitchTrack(
            time_seconds=times,
            frequency_hz=frequencies,
            raw_midi=raw_midi,
            corrected_midi=corrected,
            smoothed_midi=smoothed,
            cents=cents,
            voicing_probability=voicing,
            confidence=confidence,
            rms=rms,
            tracker=self.name,
        )


def _correct_octaves(raw_midi: np.ndarray, voiced: np.ndarray) -> np.ndarray:
    corrected = raw_midi.copy()
    prior: float | None = None
    for index in range(raw_midi.size):
        if not voiced[index]:
            corrected[index] = np.nan
            continue
        value = float(raw_midi[index])
        if prior is not None:
            candidates = np.asarray([value - 24, value - 12, value, value + 12, value + 24])
            value = float(candidates[np.argmin(np.abs(candidates - prior))])
        corrected[index] = value
        prior = value
    return corrected


def _smooth_voiced(pitch: np.ndarray, voiced: np.ndarray) -> np.ndarray:
    smoothed = pitch.copy()
    indexes = np.flatnonzero(voiced)
    if indexes.size == 0:
        return smoothed
    breaks = np.flatnonzero(np.diff(indexes) > 1) + 1
    for group in np.split(indexes, breaks):
        if group.size >= 3:
            filter_size = min(5, group.size // 2 * 2 + 1)
            smoothed[group] = median_filter(
                pitch[group], size=filter_size, mode="nearest"
            )
    return smoothed


def track_file(
    path: Path, settings: PitchSettings, engine: PitchEngine | None = None
) -> PitchTrack:
    samples, sample_rate = load_wav(path)
    return (engine or AutocorrelationPitchEngine()).track(samples, sample_rate, settings)


def save_pitch_track(path: Path, track: PitchTrack, settings: PitchSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        time_seconds=track.time_seconds,
        frequency_hz=track.frequency_hz,
        raw_midi=track.raw_midi,
        corrected_midi=track.corrected_midi,
        smoothed_midi=track.smoothed_midi,
        cents=track.cents,
        voicing_probability=track.voicing_probability,
        confidence=track.confidence,
        rms=track.rms,
        tracker=np.asarray(track.tracker),
        settings=np.asarray(str(asdict(settings))),
    )


def load_pitch_track(path: Path) -> PitchTrack:
    with np.load(path, allow_pickle=False) as payload:
        return PitchTrack(
            time_seconds=payload["time_seconds"],
            frequency_hz=payload["frequency_hz"],
            raw_midi=payload["raw_midi"],
            corrected_midi=payload["corrected_midi"],
            smoothed_midi=payload["smoothed_midi"],
            cents=payload["cents"],
            voicing_probability=payload["voicing_probability"],
            confidence=payload["confidence"],
            rms=payload["rms"],
            tracker=str(payload["tracker"]),
        )

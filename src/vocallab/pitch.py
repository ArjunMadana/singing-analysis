from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from importlib import metadata, util
from math import gcd
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from scipy.signal import resample_poly

from vocallab.audio import frame_rms, load_wav
from vocallab.errors import AnalysisError
from vocallab.models import PitchSettings, PitchTrack
from vocallab.music import hz_to_midi

TORCHCREPE_VERSION = "0.0.24"
TORCHCREPE_INSTALL_COMMAND = f"python -m pip install torchcrepe=={TORCHCREPE_VERSION}"
TORCHCREPE_ALGORITHM = (
    f"torchcrepe-{TORCHCREPE_VERSION}-full-viterbi-p0.21-"
    "centered-rms-60db-median3-mean3-scipy-polyphase-v1"
)


class PitchEngine(Protocol):
    name: str

    def track(
        self, samples: np.ndarray, sample_rate: int, settings: PitchSettings
    ) -> PitchTrack: ...


class TorchCrepePitchEngine:
    def __init__(
        self,
        *,
        model: str = "full",
        periodicity_threshold: float = 0.21,
        batch_size: int = 2_048,
        device: str | None = None,
    ) -> None:
        capability = torchcrepe_capability()
        if not capability["compatible"]:
            raise AnalysisError(
                f"TorchCREPE {TORCHCREPE_VERSION} is required. "
                f"Install it with: {TORCHCREPE_INSTALL_COMMAND}"
            )
        self.model = model
        self.periodicity_threshold = periodicity_threshold
        self.batch_size = batch_size
        self.device = device or str(capability["device"])
        algorithm = (
            TORCHCREPE_ALGORITHM
            if model == "full" and periodicity_threshold == 0.21
            else (
                f"torchcrepe-{TORCHCREPE_VERSION}-{model}-viterbi-"
                f"p{periodicity_threshold:g}-centered-rms-60db-median3-mean3-"
                "scipy-polyphase-v1"
            )
        )
        self.name = f"{algorithm}-{self.device}"

    def track(self, samples: np.ndarray, sample_rate: int, settings: PitchSettings) -> PitchTrack:
        import torch
        import torchcrepe

        target_rate = 16_000
        divisor = gcd(sample_rate, target_rate)
        resampled = resample_poly(
            np.asarray(samples, dtype=np.float32),
            target_rate // divisor,
            sample_rate // divisor,
        ).astype(np.float32)
        audio = torch.from_numpy(resampled).unsqueeze(0)
        hop_length = int(round(settings.hop_seconds * target_rate))

        probability_batches = []
        with torch.no_grad():
            for frames in torchcrepe.preprocess(
                audio,
                target_rate,
                hop_length,
                self.batch_size,
                self.device,
                True,
            ):
                probabilities = torchcrepe.infer(frames, self.model, self.device, embed=False)
                probabilities = probabilities.reshape(audio.size(0), -1, 360).transpose(1, 2)
                probability_batches.append(probabilities.cpu())
        all_probabilities = torch.cat(probability_batches, dim=2)
        raw_pitch, periodicity = torchcrepe.postprocess(
            all_probabilities,
            settings.min_hz,
            settings.max_hz,
            decoder=_fast_viterbi_decoder,
            return_periodicity=True,
        )
        silent = _centered_silence_mask(
            resampled,
            hop_length,
            periodicity.shape[1],
            threshold_db=-60.0,
        )
        periodicity[:, torch.from_numpy(silent)] = 0.0
        periodicity = torchcrepe.filter.median(periodicity, 3)
        corrected_pitch = torchcrepe.threshold.At(self.periodicity_threshold)(
            raw_pitch, periodicity
        )
        smoothed_pitch = torchcrepe.filter.mean(corrected_pitch, 3)

        frequency = raw_pitch.squeeze(0).numpy().astype(np.float64)
        corrected_midi = hz_to_midi(corrected_pitch.squeeze(0).numpy().astype(np.float64))
        smoothed_midi = hz_to_midi(smoothed_pitch.squeeze(0).numpy().astype(np.float64))
        confidence = periodicity.squeeze(0).numpy().astype(np.float64)
        times = np.arange(frequency.size, dtype=np.float64) * settings.hop_seconds
        rms_timeseries = frame_rms(
            samples,
            sample_rate,
            settings.frame_seconds,
            settings.hop_seconds,
        )
        rms_times = (
            np.arange(rms_timeseries.size, dtype=np.float64) * settings.hop_seconds
            + settings.frame_seconds / 2.0
        )
        rms = np.interp(
            times,
            rms_times,
            rms_timeseries,
            left=0.0,
            right=0.0,
        )
        cents = 100.0 * (smoothed_midi - np.rint(smoothed_midi))
        return PitchTrack(
            time_seconds=times,
            frequency_hz=frequency,
            raw_midi=hz_to_midi(frequency),
            corrected_midi=corrected_midi,
            smoothed_midi=smoothed_midi,
            cents=cents,
            voicing_probability=confidence,
            confidence=confidence,
            rms=rms,
            tracker=self.name,
        )


def _fast_viterbi_decoder(logits: Any) -> tuple[Any, Any]:
    """Decode TorchCREPE bins without librosa's multi-minute JIT warm-up."""
    import torch
    import torchcrepe

    probabilities = torch.softmax(logits, dim=1).detach().cpu().numpy()
    transition = _viterbi_transition()
    decoded: list[np.ndarray] = []
    offsets = tuple(range(-11, 12))
    for observations in probabilities:
        frame_count = observations.shape[1]
        backpointers = np.empty((frame_count, 360), dtype=np.int8)
        score = np.log(np.maximum(observations[:, 0], 1e-30)) - np.log(360.0)
        candidates = np.empty((len(offsets), 360), dtype=np.float64)
        for frame in range(1, frame_count):
            candidates.fill(-np.inf)
            for row, offset in enumerate(offsets):
                if offset >= 0:
                    prior = np.arange(0, 360 - offset)
                else:
                    prior = np.arange(-offset, 360)
                current = prior + offset
                candidates[row, current] = score[prior] + transition[prior, current]
            choices = np.argmax(candidates, axis=0)
            backpointers[frame] = choices.astype(np.int8) - 11
            score = np.max(candidates, axis=0) + np.log(np.maximum(observations[:, frame], 1e-30))
        path = np.empty(frame_count, dtype=np.int64)
        path[-1] = int(np.argmax(score))
        for frame in range(frame_count - 1, 0, -1):
            path[frame - 1] = path[frame] - int(backpointers[frame, path[frame]])
        decoded.append(path)
    bins = torch.tensor(np.stack(decoded), device=logits.device)
    return bins, torchcrepe.convert.bins_to_frequency(bins)


def _centered_silence_mask(
    samples: np.ndarray,
    hop_length: int,
    frame_count: int,
    *,
    threshold_db: float,
) -> np.ndarray:
    """Match TorchCREPE's centered frames without importing librosa/Numba."""
    window_size = 1_024
    padded = np.pad(
        np.asarray(samples, dtype=np.float64),
        (window_size // 2, window_size // 2),
    )
    energy = np.square(padded)
    cumulative = np.concatenate(([0.0], np.cumsum(energy)))
    starts = np.arange(frame_count, dtype=np.int64) * hop_length
    ends = starts + window_size
    rms = np.sqrt((cumulative[ends] - cumulative[starts]) / window_size)
    dbfs = 20.0 * np.log10(np.maximum(rms, 1e-10))
    return dbfs < threshold_db


@lru_cache(maxsize=1)
def _viterbi_transition() -> np.ndarray:
    prior, current = np.meshgrid(np.arange(360), np.arange(360), indexing="ij")
    transition = np.maximum(12 - np.abs(prior - current), 0).astype(np.float64)
    transition /= transition.sum(axis=1, keepdims=True)
    return np.log(np.maximum(transition, 1e-300))


@lru_cache(maxsize=1)
def torchcrepe_capability() -> dict[str, object]:
    installed = util.find_spec("torchcrepe") is not None
    version = metadata.version("torchcrepe") if installed else None
    device = "cpu"
    cuda_available = False
    if installed:
        try:
            import torch

            cuda_available = bool(torch.cuda.is_available())
            device = "cuda" if cuda_available else "cpu"
        except Exception:
            installed = False
    return {
        "installed": installed,
        "compatible": installed and version == TORCHCREPE_VERSION,
        "version": version,
        "required_version": TORCHCREPE_VERSION,
        "model": "full",
        "decoder": "viterbi",
        "device": device,
        "cuda_available": cuda_available,
        "install_command": TORCHCREPE_INSTALL_COMMAND,
        "silent_fallback": False,
    }


def track_file(
    path: Path, settings: PitchSettings, engine: PitchEngine | None = None
) -> PitchTrack:
    samples, sample_rate = load_wav(path)
    return (engine or TorchCrepePitchEngine()).track(samples, sample_rate, settings)


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

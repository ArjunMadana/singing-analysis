from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from vocallab.audio import load_wav
from vocallab.cache import file_hash
from vocallab.pitch import load_pitch_track


def waveform_summary(
    audio_path: Path, cache_root: Path, max_points: int = 1_200
) -> dict[str, Any]:
    cache_root.mkdir(parents=True, exist_ok=True)
    key = f"{file_hash(audio_path)}-{max_points}"
    output = cache_root / f"{key}.npz"
    if output.exists():
        with np.load(output) as payload:
            return {
                "time": payload["time"].tolist(),
                "minimum": payload["minimum"].tolist(),
                "maximum": payload["maximum"].tolist(),
                "duration": float(payload["duration"]),
            }
    samples, sample_rate = load_wav(audio_path)
    bucket = max(1, int(np.ceil(samples.size / max_points)))
    padded = np.pad(samples, (0, (-samples.size) % bucket), constant_values=np.nan)
    frames = padded.reshape(-1, bucket)
    minimum = np.nanmin(frames, axis=1)
    maximum = np.nanmax(frames, axis=1)
    time = np.arange(frames.shape[0]) * bucket / sample_rate
    duration = samples.size / sample_rate
    np.savez_compressed(
        output, time=time, minimum=minimum, maximum=maximum, duration=duration
    )
    return {
        "time": time.tolist(),
        "minimum": minimum.tolist(),
        "maximum": maximum.tolist(),
        "duration": duration,
    }


def pitch_visualization(
    reference_path: Path,
    user_path: Path,
    alignment_path: Path,
    max_points: int = 2_000,
    reference_shift_semitones: int = 0,
) -> dict[str, Any]:
    reference = load_pitch_track(reference_path)
    user = load_pitch_track(user_path)
    with np.load(alignment_path) as alignment:
        reference_indices = np.asarray(alignment["reference_indices"], dtype=int)
        user_indices = np.asarray(alignment["user_indices"], dtype=int)
    reference_indices = np.clip(reference_indices, 0, len(reference.time_seconds) - 1)
    user_indices = np.clip(user_indices, 0, len(user.time_seconds) - 1)
    stride = max(1, int(np.ceil(max(len(reference_indices), 1) / max_points)))
    ref_index = reference_indices[::stride]
    user_index = user_indices[::stride]
    reference_values = np.asarray(reference.smoothed_midi)[ref_index]
    return {
        "time": np.asarray(reference.time_seconds)[ref_index].tolist(),
        "reference_midi": _nullable(reference_values),
        "shifted_reference_midi": _nullable(
            reference_values + reference_shift_semitones
        ),
        "reference_shift_semitones": reference_shift_semitones,
        "user_midi": _nullable(np.asarray(user.smoothed_midi)[user_index]),
        "reference_confidence": np.asarray(reference.voicing_probability)[ref_index].tolist(),
        "user_confidence": np.asarray(user.voicing_probability)[user_index].tolist(),
        "tracker": user.tracker,
    }


def transport_mapping(
    reference_path: Path,
    user_path: Path,
    alignment_path: Path,
    max_points: int = 3_000,
) -> dict[str, list[float]]:
    """Return monotonic canonical-to-source playback mappings."""
    reference = load_pitch_track(reference_path)
    user = load_pitch_track(user_path)
    with np.load(alignment_path) as alignment:
        canonical_indices = np.asarray(alignment["reference_indices"], dtype=int)
        user_indices = np.asarray(alignment["user_indices"], dtype=int)
        if "current_reference_indices" in alignment:
            current_reference_indices = np.asarray(
                alignment["current_reference_indices"], dtype=int
            )
        else:
            latency = (
                float(alignment["microphone_latency_seconds"])
                if "microphone_latency_seconds" in alignment
                else 0.0
            )
            hop = _median_hop(np.asarray(user.time_seconds))
            current_reference_indices = user_indices - int(round(latency / hop))
    valid = (
        (canonical_indices >= 0)
        & (canonical_indices < len(reference.time_seconds))
        & (current_reference_indices >= 0)
        & (user_indices >= 0)
        & (user_indices < len(user.time_seconds))
    )
    canonical = np.asarray(reference.time_seconds)[canonical_indices[valid]]
    reference_hop = _median_hop(np.asarray(reference.time_seconds))
    current_reference = current_reference_indices[valid] * reference_hop
    user_time = np.asarray(user.time_seconds)[user_indices[valid]]
    canonical, current_reference, user_time = _collapse_mapping(
        canonical, current_reference, user_time
    )
    stride = max(1, int(np.ceil(max(len(canonical), 1) / max_points)))
    return {
        "canonical_time": canonical[::stride].tolist(),
        "reference_time": current_reference[::stride].tolist(),
        "user_time": user_time[::stride].tolist(),
    }


def _nullable(values: np.ndarray) -> list[float | None]:
    return [float(value) if np.isfinite(value) else None for value in values]


def _collapse_mapping(
    canonical: np.ndarray,
    reference: np.ndarray,
    user: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not canonical.size:
        empty = np.array([], dtype=np.float64)
        return empty, empty, empty
    unique, starts = np.unique(canonical, return_index=True)
    reference_values = np.empty_like(unique)
    user_values = np.empty_like(unique)
    ends = np.append(starts[1:], canonical.size)
    for position, (start, end) in enumerate(zip(starts, ends, strict=True)):
        reference_values[position] = np.median(reference[start:end])
        user_values[position] = np.median(user[start:end])
    return unique, reference_values, user_values


def _median_hop(times: np.ndarray) -> float:
    differences = np.diff(times)
    return float(np.median(differences)) if differences.size else 0.01

from __future__ import annotations

import numpy as np
from scipy.signal import correlate, correlation_lags

from vocallab.models import AlignmentResult


PROFILE_BANDS = {"pitch-focused": 0.15, "performance": 0.08, "strict": 0.015}


def estimate_global_offset(
    reference_feature: np.ndarray,
    user_feature: np.ndarray,
    hop_seconds: float,
    max_offset_seconds: float = 5.0,
) -> tuple[float, float]:
    reference = _normalize_feature(reference_feature)
    user = _normalize_feature(user_feature)
    if reference.size < 3 or user.size < 3 or not np.any(reference) or not np.any(user):
        return 0.0, 0.0
    correlation = correlate(user, reference, mode="full", method="fft")
    lags = correlation_lags(user.size, reference.size, mode="full")
    maximum_lag = max(1, int(round(max_offset_seconds / hop_seconds)))
    valid = np.abs(lags) <= maximum_lag
    correlation = correlation[valid]
    lags = lags[valid]
    best = int(np.argmax(correlation))
    denominator = np.linalg.norm(user) * np.linalg.norm(reference)
    confidence = float(np.clip(correlation[best] / denominator, 0.0, 1.0)) if denominator else 0.0
    # Positive means the user signal occurs later than the reference.
    return float(lags[best] * hop_seconds), confidence


def constrained_alignment(
    reference_feature: np.ndarray,
    user_feature: np.ndarray,
    hop_seconds: float,
    global_offset_seconds: float,
    profile: str = "performance",
    max_points: int = 3_000,
) -> AlignmentResult:
    if profile not in PROFILE_BANDS:
        raise ValueError(f"Unknown alignment profile '{profile}'.")
    offset_frames = int(round(global_offset_seconds / hop_seconds))
    ref_start = max(0, -offset_frames)
    user_start = max(0, offset_frames)
    reference = np.asarray(reference_feature[ref_start:], dtype=np.float64)
    user = np.asarray(user_feature[user_start:], dtype=np.float64)
    common = min(reference.size, user.size)
    if common < 2:
        return AlignmentResult(
            global_offset_seconds, np.array([], dtype=int), np.array([], dtype=int), 0.0, profile
        )
    # Downsampling bounds DTW memory and is recorded in the returned index path.
    stride = max(1, int(np.ceil(max(reference.size, user.size) / max_points)))
    reference = _normalize_feature(reference[::stride])
    user = _normalize_feature(user[::stride])
    n, m = reference.size, user.size
    band = max(2, int(np.ceil(max(n, m) * PROFILE_BANDS[profile])))
    costs: list[dict[int, float]] = []
    predecessors: list[dict[int, tuple[int, int]]] = []

    for i in range(n):
        expected = i * (m - 1) / max(n - 1, 1)
        low = max(0, int(np.floor(expected - band)))
        high = min(m - 1, int(np.ceil(expected + band)))
        row: dict[int, float] = {}
        previous_row = costs[i - 1] if i else {}
        predecessor_row: dict[int, tuple[int, int]] = {}
        for j in range(low, high + 1):
            local = abs(reference[i] - user[j])
            if i == 0 and j == 0:
                row[j] = local
                continue
            candidates: list[tuple[float, tuple[int, int]]] = []
            if j in previous_row:
                candidates.append((previous_row[j], (i - 1, j)))
            if j - 1 in row:
                candidates.append((row[j - 1], (i, j - 1)))
            if j - 1 in previous_row:
                candidates.append((previous_row[j - 1], (i - 1, j - 1)))
            if candidates:
                prior_cost, predecessor = min(candidates, key=lambda item: item[0])
                row[j] = local + prior_cost
                predecessor_row[j] = predecessor
        costs.append(row)
        predecessors.append(predecessor_row)

    if (m - 1) not in costs[-1]:
        # A pathological length mismatch can miss the exact endpoint; use the best reachable end.
        end_j = min(costs[-1], key=lambda j: costs[-1][j] + abs(j - (m - 1)))
    else:
        end_j = m - 1
    i, j = n - 1, end_j
    path: list[tuple[int, int]] = [(i, j)]
    while (i, j) != (0, 0):
        predecessor = predecessors[i].get(j)
        if predecessor is None:
            break
        i, j = predecessor
        path.append((i, j))
    path.reverse()
    reference_indices = np.asarray(
        [ref_start + i * stride for i, _ in path], dtype=np.int64
    )
    user_indices = np.asarray(
        [user_start + j * stride for _, j in path], dtype=np.int64
    )
    mean_cost = costs[-1][end_j] / max(len(path), 1)
    confidence = float(np.exp(-mean_cost))
    return AlignmentResult(
        global_offset_seconds,
        reference_indices,
        user_indices,
        confidence,
        profile,
    )


def estimate_microphone_latency(
    reference_pitch: np.ndarray,
    user_pitch: np.ndarray,
    reference_indices: np.ndarray,
    current_reference_indices: np.ndarray,
    hop_seconds: float,
    max_latency_seconds: float = 2.5,
) -> tuple[float, float]:
    """Estimate a constant capture delay after system-audio synchronization.

    The score removes the best integer transposition for each candidate lag, so a
    singer in another key can still provide latency evidence. Local timing remains
    visible after this one global device-delay correction.
    """
    reference = np.asarray(reference_pitch, dtype=np.float64)
    user = np.asarray(user_pitch, dtype=np.float64)
    reference_indices = np.asarray(reference_indices, dtype=int)
    current_reference_indices = np.asarray(current_reference_indices, dtype=int)
    maximum = max(1, int(round(max_latency_seconds / hop_seconds)))
    candidates: list[tuple[int, float, int]] = []
    for lag in range(-maximum, maximum + 1):
        user_indices = current_reference_indices + lag
        valid = (
            (reference_indices >= 0)
            & (reference_indices < reference.size)
            & (user_indices >= 0)
            & (user_indices < user.size)
        )
        boundary_coverage = float(np.mean(valid))
        if np.count_nonzero(valid) < 12:
            continue
        reference_values = reference[reference_indices[valid]]
        user_values = user[user_indices[valid]]
        reference_voiced = np.isfinite(reference_values)
        user_voiced = np.isfinite(user_values)
        voiced = reference_voiced & user_voiced
        evidence = int(np.count_nonzero(voiced))
        reference_evidence = int(np.count_nonzero(reference_voiced))
        if evidence < 12 or reference_evidence < 12:
            continue
        difference = user_values[voiced] - reference_values[voiced]
        shift = round(float(np.median(difference)))
        residual = np.minimum(np.abs(difference - shift), 3.0)
        coverage_penalty = 1.0 - evidence / reference_evidence
        voicing_mismatch = float(np.mean(reference_voiced != user_voiced))
        score = (
            float(np.mean(residual))
            + 0.75 * coverage_penalty
            + 0.5 * voicing_mismatch
            + 2.0 * (1.0 - boundary_coverage)
        )
        candidates.append((lag, score, evidence))
    if not candidates:
        return 0.0, 0.0
    candidates.sort(key=lambda item: (item[1], -item[2], abs(item[0])))
    best_lag, best_score, best_evidence = candidates[0]
    alternatives = [
        item for item in candidates[1:] if abs(item[0] - best_lag) >= 5
    ]
    second_score = alternatives[0][1] if alternatives else best_score
    margin = max(0.0, second_score - best_score)
    evidence_factor = min(1.0, best_evidence / 100.0)
    confidence = float(np.clip((margin / 0.25) * evidence_factor, 0.0, 1.0))
    return best_lag * hop_seconds, confidence


def calibrated_alignment_confidence(
    global_confidence: float,
    local_confidence: float,
    microphone_latency_confidence: float,
    reference_indices: np.ndarray,
    user_indices: np.ndarray,
    reference_frame_count: int,
    user_frame_count: int,
) -> tuple[float, float]:
    """Combine independent evidence without treating path existence as certainty."""
    reference_indices = np.asarray(reference_indices, dtype=int)
    user_indices = np.asarray(user_indices, dtype=int)
    if not reference_indices.size or not user_indices.size:
        return 0.0, 0.0
    reference_coverage = len(np.unique(reference_indices)) / max(reference_frame_count, 1)
    user_coverage = len(np.unique(user_indices)) / max(user_frame_count, 1)
    matched_coverage = float(np.clip(min(reference_coverage, user_coverage), 0.0, 1.0))
    evidence = (
        0.35 * float(np.clip(global_confidence, 0.0, 1.0))
        + 0.25 * float(np.clip(local_confidence, 0.0, 1.0))
        + 0.25 * float(np.clip(microphone_latency_confidence, 0.0, 1.0))
        + 0.15 * matched_coverage
    )
    # Even ideal automated evidence is not a calibration measurement.
    return float(min(0.95, evidence)), matched_coverage


def reconcile_latency_estimates(
    pitch_seconds: float,
    pitch_confidence: float,
    energy_seconds: float,
    energy_confidence: float,
    reference_quality: float,
    agreement_seconds: float = 0.15,
) -> tuple[float, float, str]:
    """Select a latency estimate while exposing disagreement between evidence types."""
    pitch_weight = float(np.clip(pitch_confidence * reference_quality, 0.0, 1.0))
    energy_weight = float(
        np.clip(energy_confidence * (0.5 + 0.5 * reference_quality), 0.0, 1.0)
    )
    disagreement = abs(pitch_seconds - energy_seconds)
    if disagreement <= agreement_seconds and pitch_weight + energy_weight > 0:
        estimate = (
            pitch_seconds * pitch_weight + energy_seconds * energy_weight
        ) / (pitch_weight + energy_weight)
        confidence = min(0.95, (pitch_weight + energy_weight) / 2 + 0.2)
        return float(estimate), float(confidence), "pitch-energy-consensus"
    if energy_weight > pitch_weight * 1.25:
        confidence = energy_weight * float(np.exp(-disagreement / 2.0))
        return energy_seconds, float(confidence), "energy-envelope"
    confidence = pitch_weight * float(np.exp(-disagreement / 2.0))
    return pitch_seconds, float(confidence), "pitch-contour"


def _normalize_feature(feature: np.ndarray) -> np.ndarray:
    values = np.asarray(feature, dtype=np.float64)
    if values.size == 0:
        return values
    values = np.log1p(np.maximum(values, 0.0) * 100.0)
    median = np.median(values)
    scale = np.median(np.abs(values - median))
    if scale < 1e-9:
        scale = np.std(values)
    return (values - median) / scale if scale > 1e-9 else np.zeros_like(values)

from __future__ import annotations

import numpy as np

from vocallab.models import TranspositionResult
from vocallab.music import decompose_shift


def detect_transposition(
    reference_midi: np.ndarray,
    user_midi: np.ndarray,
    confidence: np.ndarray | None = None,
    minimum_shift: int = -12,
    maximum_shift: int = 12,
) -> TranspositionResult:
    reference = np.asarray(reference_midi, dtype=np.float64)
    user = np.asarray(user_midi, dtype=np.float64)
    valid = np.isfinite(reference) & np.isfinite(user)
    if confidence is not None:
        weights = np.asarray(confidence, dtype=np.float64)
        valid &= weights > 0
    else:
        weights = np.ones(reference.shape, dtype=np.float64)
    if not np.any(valid):
        return TranspositionResult(0, 1, 0.0, 0.0, 0, 0)
    difference = user[valid] - reference[valid]
    valid_weights = weights[valid]
    scores: list[tuple[int, float, float]] = []
    for shift in range(minimum_shift, maximum_shift + 1):
        errors = np.abs(100.0 * (difference - shift))
        median_error = _weighted_median(errors, valid_weights)
        support = 100.0 * float(
            np.sum(valid_weights[errors <= 50.0])
        ) / float(np.sum(valid_weights))
        scores.append((shift, support, median_error))
    # Key detection is a mode-finding problem. Sorting by median absolute error can
    # invent a midpoint shift between two incompatible pitch clusters.
    scores.sort(key=lambda item: (-item[1], item[2], abs(item[0])))
    best_shift, support, best_error = scores[0]
    second_shift, second_support, second_error = scores[1]
    best_errors = np.abs(100.0 * (difference - best_shift))
    support_margin = max(0.0, support - second_support)
    confidence_margin = max(0.0, second_error - best_error)
    reliable = (
        support >= 50.0
        and support_margin >= 10.0
        and confidence_margin >= 20.0
    )
    pitch_class, octave = decompose_shift(best_shift)
    return TranspositionResult(
        best_shift=best_shift,
        second_best_shift=second_shift,
        confidence_margin_cents=confidence_margin,
        support_percentage=support,
        octave_shift=octave,
        pitch_class_shift=pitch_class,
        support_margin_percentage=support_margin,
        reliable=reliable,
    )


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    sorted_values = values[order]
    sorted_weights = weights[order]
    cutoff = np.sum(sorted_weights) / 2.0
    return float(sorted_values[np.searchsorted(np.cumsum(sorted_weights), cutoff)])

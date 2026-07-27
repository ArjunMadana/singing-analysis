from __future__ import annotations

from dataclasses import asdict

import numpy as np

from vocallab.models import (
    Discrepancy,
    NoteEvent,
    ScoringMode,
    TranspositionResult,
)


def pitch_metrics(errors_cents: np.ndarray) -> dict[str, float | int | str]:
    errors = np.asarray(errors_cents, dtype=np.float64)
    errors = errors[np.isfinite(errors)]
    if errors.size == 0:
        return {
            "voiced_frame_count": 0,
            "status": "insufficient voiced overlap",
        }
    absolute = np.abs(errors)
    metrics: dict[str, float | int | str] = {
        "voiced_frame_count": int(errors.size),
        "median_signed_cents": float(np.median(errors)),
        "median_absolute_cents": float(np.median(absolute)),
        "mean_absolute_cents": float(np.mean(absolute)),
        "p90_absolute_cents": float(np.percentile(absolute, 90)),
        "sharp_frame_percentage": float(100.0 * np.mean(errors > 0)),
        "flat_frame_percentage": float(100.0 * np.mean(errors < 0)),
    }
    for tolerance in (15, 25, 35, 50, 100):
        metrics[f"within_{tolerance}_cents_percentage"] = float(
            100.0 * np.mean(absolute <= tolerance)
        )
    bias = float(metrics["median_signed_cents"])
    metrics["persistent_bias"] = (
        "sharp" if bias > 15 else "flat" if bias < -15 else "centered"
    )
    return metrics


def build_scoring_modes(
    reference_midi: np.ndarray,
    user_midi: np.ndarray,
    confidence: np.ndarray,
    transposition: TranspositionResult,
    selected_shift: int | None = None,
) -> dict[str, object]:
    reference = np.asarray(reference_midi, dtype=np.float64)
    user = np.asarray(user_midi, dtype=np.float64)
    weights = np.asarray(confidence, dtype=np.float64)
    valid = (
        np.isfinite(reference)
        & np.isfinite(user)
        & np.isfinite(weights)
        & (weights > 0)
    )
    reference = reference[valid]
    user = user[valid]
    weights = weights[valid]
    shift = transposition.best_shift if selected_shift is None else int(selected_shift)
    manual = selected_shift is not None
    reliable = manual or transposition.reliable
    absolute_errors = 100.0 * (user - reference)
    residual_errors = absolute_errors - shift * 100.0
    octave_errors = 100.0 * (((user - reference + 6.0) % 12.0) - 6.0)
    interval_metrics = _interval_contour_metrics(reference, user)
    octave_steps = (
        (user - reference - octave_errors / 100.0) / 12.0
        if reference.size
        else np.array([], dtype=np.float64)
    )
    default_mode = (
        ScoringMode.TRANSPOSITION_ADJUSTED
        if reliable
        else ScoringMode.ORIGINAL_PITCH
    )
    return {
        "default_mode": default_mode.value,
        "selected_shift": shift,
        "shift_source": "manual" if manual else "detected",
        "transposition_reliable": reliable,
        "modes": {
            ScoringMode.ORIGINAL_PITCH.value: {
                "title": "Original pitch",
                "description": (
                    "Median frame-by-frame distance from the artist pitch contour. "
                    "This is not a detected key difference."
                ),
                "metrics": pitch_metrics(absolute_errors),
                "scoring_reference": "original_artist_pitch",
            },
            ScoringMode.TRANSPOSITION_ADJUSTED.value: {
                "title": "Key-adjusted melody",
                "description": (
                    f"Reference shifted {shift:+d} semitones before note scoring."
                ),
                "metrics": pitch_metrics(residual_errors),
                "scoring_reference": "transposition_shifted_reference",
                "available": reliable,
            },
            ScoringMode.OCTAVE_INVARIANT.value: {
                "title": "Octave-invariant melody",
                "description": "Pitch-class accuracy with octave placement reported separately.",
                "metrics": {
                    **pitch_metrics(octave_errors),
                    "median_octave_displacement": (
                        float(np.median(octave_steps)) if octave_steps.size else 0.0
                    ),
                },
                "scoring_reference": "octave_equivalent_reference",
            },
            ScoringMode.INTERVAL_CONTOUR.value: {
                "title": "Interval and contour",
                "description": "Relative melodic movement independent of starting key.",
                "metrics": interval_metrics,
                "scoring_reference": "relative_contour",
            },
        },
    }


def aligned_pitch_evidence(
    reference_pitch: np.ndarray,
    user_pitch: np.ndarray,
    reference_confidence: np.ndarray,
    user_confidence: np.ndarray,
    reference_indices: np.ndarray,
    user_indices: np.ndarray,
    threshold: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if reference_indices.size == 0:
        empty = np.array([], dtype=np.float64)
        return empty, empty, empty, empty
    in_range = (
        (reference_indices >= 0)
        & (reference_indices < reference_pitch.size)
        & (user_indices >= 0)
        & (user_indices < user_pitch.size)
    )
    reference_indices = reference_indices[in_range]
    user_indices = user_indices[in_range]
    if reference_indices.size == 0:
        empty = np.array([], dtype=np.float64)
        return empty, empty, empty, empty
    reference = reference_pitch[reference_indices]
    user = user_pitch[user_indices]
    confidence = np.minimum(
        reference_confidence[reference_indices], user_confidence[user_indices]
    )
    valid = np.isfinite(reference) & np.isfinite(user) & (confidence >= threshold)
    return reference[valid], user[valid], confidence[valid], reference_indices[valid]


def build_discrepancies(
    notes: list[NoteEvent],
    reference_times: np.ndarray,
    aligned_reference_pitch: np.ndarray,
    aligned_user_pitch: np.ndarray,
    aligned_reference_indices: np.ndarray,
    shift: TranspositionResult,
    confidence: np.ndarray,
    reference_quality: float = 1.0,
    alignment_quality: float = 1.0,
    scoring_reliable: bool = True,
) -> list[Discrepancy]:
    results: list[Discrepancy] = []
    if aligned_reference_pitch.size == 0:
        return [
            Discrepancy(
                "low-confidence alignment",
                0.0,
                0.0,
                0.0,
                0.0,
                "No sufficiently voiced aligned frames were available for scoring.",
                0.0,
                1.0,
            )
        ]
    if not scoring_reliable:
        return [
            Discrepancy(
                "low-confidence transposition",
                0.0,
                0.0,
                0.0,
                0.0,
                "No coherent global key shift was detected. Choose a key manually "
                "before treating note-level pitch differences as accuracy feedback.",
                0.0,
                2.5,
                provisional=True,
                reliability_reason="Detected pitch differences were multimodal.",
            )
        ]
    times = reference_times[
        np.clip(aligned_reference_indices, 0, reference_times.size - 1)
    ]
    errors = 100.0 * (
        aligned_user_pitch - (aligned_reference_pitch + shift.best_shift)
    )
    for note in notes:
        stable_start = note.attack_end_seconds
        stable_end = note.release_start_seconds
        selected = (times >= stable_start) & (times <= stable_end)
        if np.count_nonzero(selected) < 3:
            continue
        note_errors = errors[selected]
        median = float(np.median(note_errors))
        spread = float(np.std(note_errors))
        evidence_confidence = float(np.median(confidence[selected]))
        note_confidence = float(
            np.clip(
                evidence_confidence * reference_quality * alignment_quality,
                0.0,
                1.0,
            )
        )
        kind: str | None = None
        explanation = ""
        magnitude = abs(median)
        provisional = reference_quality < 0.6
        reliability_reason = (
            "Reference vocal separation is unavailable; full-mix pitch may track "
            "an instrument or harmonic."
            if provisional
            else None
        )
        octave_residual = abs(((median + 600.0) % 1200.0) - 600.0)
        if provisional and abs(median) >= 900:
            kind = "low-confidence reference"
            magnitude = octave_residual
            explanation = (
                "Reference pitch may have tracked a different source or harmonic; "
                "this region is not reliable enough to score."
            )
            note_confidence = min(note_confidence, 0.2)
        elif median <= -35:
            kind = "consistently flat"
            explanation = f"Stable pitch was centered {abs(median):.0f} cents flat."
        elif median >= 35:
            kind = "consistently sharp"
            explanation = f"Stable pitch was centered {median:.0f} cents sharp."
        elif spread >= 40:
            kind = "unstable sustained note"
            magnitude = spread
            explanation = f"Stable-region pitch varied by {spread:.0f} cents (standard deviation)."
        if kind and provisional and kind != "low-confidence reference":
            explanation = f"Provisional full-mix estimate. {explanation}"
        if kind:
            results.append(
                Discrepancy(
                    kind,
                    note.start_seconds,
                    note.end_seconds,
                    magnitude,
                    note_confidence,
                    explanation,
                    max(0.0, note.start_seconds - 0.25),
                    note.end_seconds + 0.25,
                    note.midi_pitch + shift.best_shift,
                    note.midi_pitch + shift.best_shift + median / 100.0,
                    provisional,
                    reliability_reason,
                )
            )
    return sorted(results, key=lambda item: item.magnitude * item.confidence, reverse=True)[:20]


def discrepancies_as_dicts(items: list[Discrepancy]) -> list[dict[str, object]]:
    return [
        {"id": f"discrepancy-{index}", **asdict(item)}
        for index, item in enumerate(items, start=1)
    ]


def _interval_contour_metrics(
    reference: np.ndarray, user: np.ndarray
) -> dict[str, float | int | str]:
    if reference.size < 2:
        return {
            "transition_count": 0,
            "status": "insufficient transitions",
        }
    reference_steps = np.diff(reference)
    user_steps = np.diff(user)
    selected = (np.abs(reference_steps) >= 0.5) | (np.abs(user_steps) >= 0.5)
    if not np.any(selected):
        return {
            "transition_count": 0,
            "status": "insufficient transitions",
        }
    errors = 100.0 * (user_steps[selected] - reference_steps[selected])
    direction = np.sign(reference_steps[selected]) == np.sign(user_steps[selected])
    return {
        "transition_count": int(np.count_nonzero(selected)),
        "median_absolute_interval_error_cents": float(np.median(np.abs(errors))),
        "contour_direction_agreement_percentage": float(100.0 * np.mean(direction)),
    }

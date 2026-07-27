from __future__ import annotations

from typing import Any

import numpy as np

from vocallab.models import NoteEvent


DEFAULT_PRE_ROLL_SECONDS = 0.75
DEFAULT_POST_ROLL_SECONDS = 0.75
DEFAULT_MINIMUM_SECONDS = 2.5
DEFAULT_MAXIMUM_SECONDS = 6.0
GROUP_GAP_SECONDS = 0.3


def build_practice_targets(
    discrepancies: list[dict[str, Any]],
    notes: list[NoteEvent],
    mapping: dict[str, list[float]],
) -> list[dict[str, Any]]:
    measurements = _annotate_measurements(discrepancies, notes)
    groups: list[list[dict[str, Any]]] = []
    for measurement in measurements:
        if groups and _can_group(groups[-1][-1], measurement):
            groups[-1].append(measurement)
        else:
            groups.append([measurement])
    return [
        _target(group, notes, mapping, target_index)
        for target_index, group in enumerate(groups, start=1)
    ]


def map_canonical_time(
    mapping: dict[str, list[float]], canonical_seconds: float, source: str
) -> float:
    canonical = np.asarray(mapping.get("canonical_time", []), dtype=float)
    values = np.asarray(mapping.get(source, []), dtype=float)
    if not canonical.size or canonical.size != values.size:
        return canonical_seconds
    return float(np.interp(canonical_seconds, canonical, values))


def _annotate_measurements(
    discrepancies: list[dict[str, Any]], notes: list[NoteEvent]
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for index, original in enumerate(discrepancies, start=1):
        item = dict(original)
        item["id"] = str(item.get("id") or f"discrepancy-{index}")
        note_index = _associated_note(item, notes)
        item["baseline_note_id"] = (
            f"note-{note_index + 1}" if note_index is not None else None
        )
        item["note_index"] = note_index
        item["phrase_id"] = notes[note_index].phrase_id if note_index is not None else None
        annotated.append(item)
    return sorted(annotated, key=lambda item: float(item["start_seconds"]))


def _associated_note(item: dict[str, Any], notes: list[NoteEvent]) -> int | None:
    start = float(item["start_seconds"])
    end = float(item["end_seconds"])
    best: tuple[float, int] | None = None
    for index, note in enumerate(notes):
        overlap = max(0.0, min(end, note.end_seconds) - max(start, note.start_seconds))
        distance = 0.0 if overlap else min(
            abs(start - note.end_seconds), abs(note.start_seconds - end)
        )
        score = overlap * 100.0 - distance
        if best is None or score > best[0]:
            best = (score, index)
    return best[1] if best else None


def _can_group(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    same_note = previous.get("baseline_note_id") == current.get("baseline_note_id")
    gap = float(current["start_seconds"]) - float(previous["end_seconds"])
    same_phrase = (
        previous.get("phrase_id")
        and previous.get("phrase_id") == current.get("phrase_id")
    )
    return bool(
        same_note
        or (
            same_phrase
            and gap <= GROUP_GAP_SECONDS
            and _compatible(str(previous["kind"]), str(current["kind"]))
        )
    )


def _compatible(first: str, second: str) -> bool:
    def family(kind: str) -> str:
        lowered = kind.lower()
        if "flat" in lowered:
            return "flat"
        if "sharp" in lowered:
            return "sharp"
        if "confidence" in lowered or "harmonic" in lowered:
            return "confidence"
        if "unstable" in lowered or "drift" in lowered:
            return "stability"
        return lowered

    return family(first) == family(second)


def _target(
    group: list[dict[str, Any]],
    notes: list[NoteEvent],
    mapping: dict[str, list[float]],
    target_index: int,
) -> dict[str, Any]:
    measurement_start = min(float(item["start_seconds"]) for item in group)
    measurement_end = max(float(item["end_seconds"]) for item in group)
    note_indices = sorted(
        {int(item["note_index"]) for item in group if item.get("note_index") is not None}
    )
    context_indices = list(note_indices)
    if note_indices:
        first = note_indices[0]
        if first > 0 and notes[first - 1].phrase_id == notes[first].phrase_id:
            if notes[first].start_seconds - notes[first - 1].end_seconds <= 0.6:
                context_indices.insert(0, first - 1)
    note_start = (
        min(notes[index].start_seconds for index in context_indices)
        if context_indices
        else measurement_start
    )
    note_end = (
        max(notes[index].end_seconds for index in context_indices)
        if context_indices
        else measurement_end
    )
    note_loop = _bounded_loop(
        min(measurement_start, note_start) - DEFAULT_PRE_ROLL_SECONDS,
        max(measurement_end, note_end) + DEFAULT_POST_ROLL_SECONDS,
        measurement_start,
        measurement_end,
    )
    phrase_indices = [
        index
        for index, note in enumerate(notes)
        if note_indices and note.phrase_id == notes[note_indices[0]].phrase_id
    ]
    phrase_loop = _bounded_loop(
        min((notes[index].start_seconds for index in phrase_indices), default=note_loop[0])
        - DEFAULT_PRE_ROLL_SECONDS,
        max((notes[index].end_seconds for index in phrase_indices), default=note_loop[1])
        + DEFAULT_POST_ROLL_SECONDS,
        measurement_start,
        measurement_end,
    )
    loop_start, loop_end = note_loop
    return {
        "id": f"practice-target-{target_index}",
        "discrepancy_ids": [item["id"] for item in group],
        "measurements": group,
        "measurement_start_seconds": measurement_start,
        "measurement_end_seconds": measurement_end,
        "loop_start_seconds": loop_start,
        "loop_end_seconds": loop_end,
        "mapped_user_loop_start_seconds": map_canonical_time(
            mapping, loop_start, "user_time"
        ),
        "mapped_user_loop_end_seconds": map_canonical_time(
            mapping, loop_end, "user_time"
        ),
        "baseline_note_ids": [
            f"note-{index + 1}" for index in note_indices
        ],
        "phrase_id": group[0].get("phrase_id"),
        "confidence": min(float(item.get("confidence", 0.0)) for item in group),
        "provisional": any(bool(item.get("provisional")) for item in group),
        "reason_for_grouping": (
            "Grouped compatible measurements within one phrase."
            if len(group) > 1
            else "Expanded the measured error to musical note context."
        ),
        "loop_presets": {
            "note_context": {"start": note_loop[0], "end": note_loop[1]},
            "short_phrase": {"start": phrase_loop[0], "end": phrase_loop[1]},
            "full_phrase": {"start": phrase_loop[0], "end": phrase_loop[1]},
        },
    }


def _bounded_loop(
    start: float,
    end: float,
    measurement_start: float,
    measurement_end: float,
) -> tuple[float, float]:
    start = max(0.0, start)
    if end - start < DEFAULT_MINIMUM_SECONDS:
        missing = DEFAULT_MINIMUM_SECONDS - (end - start)
        start = max(0.0, start - missing / 2)
        end = start + DEFAULT_MINIMUM_SECONDS
    if end - start > DEFAULT_MAXIMUM_SECONDS:
        center = (measurement_start + measurement_end) / 2
        start = max(0.0, center - DEFAULT_MAXIMUM_SECONDS / 2)
        end = start + DEFAULT_MAXIMUM_SECONDS
    return start, end

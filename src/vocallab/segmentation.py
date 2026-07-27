from __future__ import annotations

import numpy as np

from vocallab.models import NoteEvent, PitchTrack


def segment_notes(
    track: PitchTrack,
    voicing_threshold: float = 0.35,
    minimum_duration_seconds: float = 0.08,
    phrase_gap_seconds: float = 0.8,
) -> list[NoteEvent]:
    times = np.asarray(track.time_seconds)
    pitch = np.asarray(track.smoothed_midi)
    voiced = (
        np.asarray(track.voicing_probability) >= voicing_threshold
    ) & np.isfinite(pitch)
    if times.size < 2:
        return []
    hop = float(np.median(np.diff(times)))
    quantized = np.rint(pitch)
    boundaries = np.flatnonzero(
        voiced[1:] != voiced[:-1]
        | (voiced[1:] & voiced[:-1] & (np.abs(quantized[1:] - quantized[:-1]) >= 1))
    ) + 1
    groups = np.split(np.arange(times.size), boundaries)
    notes: list[NoteEvent] = []
    phrase_number = 1
    prior_end: float | None = None
    for group in groups:
        valid = group[voiced[group]]
        if valid.size == 0:
            continue
        start = float(times[valid[0]] - hop / 2)
        end = float(times[valid[-1]] + hop / 2)
        if end - start < minimum_duration_seconds:
            continue
        if prior_end is not None and start - prior_end >= phrase_gap_seconds:
            phrase_number += 1
        values = pitch[valid]
        center = float(np.median(values))
        duration = end - start
        edge = min(0.08, duration * 0.2)
        notes.append(
            NoteEvent(
                start_seconds=max(0.0, start),
                end_seconds=end,
                attack_end_seconds=start + edge,
                release_start_seconds=end - edge,
                midi_pitch=float(np.rint(center)),
                cents_offset=100.0 * (center - np.rint(center)),
                confidence=float(np.median(np.asarray(track.confidence)[valid])),
                phrase_id=f"phrase-{phrase_number}",
            )
        )
        prior_end = end
    return notes


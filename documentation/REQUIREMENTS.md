# VocalLab immutable requirements

Last updated: 2026-07-26

## Phase 1 acceptance boundary

1. Original imported media is never modified.
2. FFprobe lists audio stream indexes and metadata before assignment.
3. The operator explicitly selects microphone and reference streams.
4. Deterministic stages are keyed by source content, implementation version, and all
   output-affecting parameters.
5. Dense frame data is stored in NumPy artifacts, not relational JSON columns.
6. The first analyzed take creates a versioned reusable reference baseline.
7. Later takes reuse that baseline by default and process only take-specific inputs.
8. Pitch scoring excludes frames below the configured voicing threshold.
9. Transposition searches every integer semitone from -12 through +12 and reports
   the runner-up, confidence margin, evidence support, and octave decomposition.
   Candidate selection must prefer actual frame support over a lower median error;
   it must never invent a midpoint between incompatible pitch clusters.
10. Feedback states acoustic measurements and confidence; it does not diagnose vocal
    technique or health.
11. Reports are local static artifacts and do not upload or redistribute audio.
12. Missing optional models cause a visible degraded-mode warning, not a false claim
    that separation or neural pitch analysis occurred.

## Current milestone definition

The integrated local browser application must preserve the Phase 1 boundary and:

1. Decode every enabled playback source before enabling Play.
2. Schedule all enabled sources on one Web Audio clock.
3. Treat baseline/reference time as canonical and map reference and microphone
   offsets independently using one global song-start shift and one constant
   microphone-device latency. Never apply a local time-warp curve.
   When recordings have different lengths, align only their shared span after the
   detected global offset; never force unequal endpoints to match.
4. Stop and recreate source nodes atomically for pause, seek, loop, or target
   changes; partial playback must never be shown as Both.
   A disposed or superseded transport must never publish late readiness state into
   the active take.
5. Anchor repeated loops to an absolute epoch so timing error cannot accumulate.
6. Store any manual playback calibration per take, only after explicit Save, and
   never use it to change scoring.
7. Preserve precise discrepancy measurements separately from editable practice
   loops of at least 2.5 and at most 6 automatic seconds.
8. Group compatible nearby measurements into musically actionable targets.
9. Treat full-mix reference scoring as provisional and suppress authoritative
   octave-scale claims when harmonic tracking is plausible.
10. Make Demucs availability and explicit selection visible without silently
    downloading a model in automatic mode.
11. Report evidence-based alignment confidence, including candidate disagreement
    and coverage; path existence alone cannot produce 100% confidence.
12. Keep original-pitch, transposition-adjusted, octave-invariant, and
    interval/contour results separate. Only coherent detected shifts or explicit
    manual shifts may drive key-adjusted note discrepancies.
13. Show original reference, shifted reference, and user contours, and state which
    reference the selected scoring view uses.
14. A normal timeline click seeks. Custom loop creation requires an intentional
    drag; loop edges can be resized explicitly and loops can be cleared explicitly.
15. Label active reference provenance separately from settings for the next
    reference rebuild.
16. Scope an inspected recording and its stream-role draft to one project. Opening
    a fresh import or switching projects must show an empty file chooser, and the
    confirmation step must let the user choose a different recording.
17. Play at or beyond the canonical mapping endpoint must restart from the
    beginning. The UI must never claim playback while scheduling zero source nodes.
18. Playback must preserve recorded pitch. Corrected playback maps canonical time
    through the measured system-reference and microphone offsets while keeping both
    sources at exactly 1.0x. No variable-rate playback mode is permitted. Waveforms
    must use the same active timestamp offsets as the audio and pitch.

Desktop packaging and an advanced direct-manipulation piano roll remain later
milestones.

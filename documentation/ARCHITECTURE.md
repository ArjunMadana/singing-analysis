# Architecture

Last updated: 2026-07-26

VocalLab is a local Python library and CLI. `ProjectStore` owns SQLite metadata;
large deterministic results live under `artifacts/` and are addressed by cache keys.
The source recording is referenced by absolute path and SHA-256 and is never opened
for writing.

Processing flows in one direction:

`media -> extraction -> optional separation -> pitch -> segmentation/alignment -> scoring -> report`

The cache dependency graph mirrors that flow. A scoring tolerance change therefore
does not invalidate extraction or pitch, while a tracker change invalidates its
downstream alignment and scoring.

Interfaces are replaceable at the expensive/model-dependent boundaries:

- FFmpeg performs media decode and deterministic stream extraction.
- `Separator` supports Demucs when installed and an explicit contaminated-reference
  fallback when it is not.
- `PitchEngine` initially uses a deterministic autocorrelation implementation and
  retains raw, corrected, and smoothed contours.
- Alignment uses global energy-envelope correlation followed by a one-to-one
  shared-span mapping. It never performs local time warping.

SQLite stores projects, takes, baseline versions, and pointers to artifact manifests.
NumPy NPZ stores dense frame arrays. JSON manifests record source hashes, algorithms,
versions, settings, outputs, warnings, and cache-hit evidence.

Discrepancies retain saved-baseline times for stable comparisons. Report playback
maps those ranges through the saved constant offsets onto the current take timeline,
so a loop remains correct when the recording starts at a different timestamp.

The local application adds a typed FastAPI orchestration boundary and a React
Canvas workspace. API handlers call `ProjectStore`, `analyze_take`, pitch loaders,
and display-summary services; they do not duplicate DSP or scoring in TypeScript.
Media selected in the browser enters a library-owned staging directory and is
copied into project-owned storage on import. Artifact endpoints resolve only
allow-listed paths beneath the selected project.

The browser import draft contains its owning project ID, inspection token, and
stream-role choices. A project change or fresh Import action replaces the whole
draft rather than retaining independent global inspection fields. The confirmation
screen can also replace the draft explicitly through Choose different recording.
This prevents a staging token inspected for one project from appearing as the next
project's pending import.

Synchronization has two explicit layers: system audio is aligned to the saved song
reference, then pitch-contour and energy-envelope evidence estimate one constant
microphone capture latency. Their estimates, confidences, disagreement, selection
method, matched coverage, and calibrated overall confidence remain in provenance.
The alignment artifact stores canonical baseline indices, current system-reference
indices, and microphone indices after latency correction.

After the global offset establishes the overlapping start, baseline and current
reference frames advance one-to-one through their shared remaining span. A short
baseline excerpt therefore ends normally instead of being stretched over unrelated
audio. Calibrated coverage reports how much of each recording participated.

Browser playback uses `SharedAudioTransport`, not independent
`HTMLAudioElement` clocks. It decodes both WAV artifacts into one `AudioContext`
and schedules both sources at the same future context time. Canonical baseline
time maps independently to reference and microphone time. Normal corrected
playback applies the measured system-reference offset and microphone latency as
constant source-time offsets and schedules each source at 1.0x. The detailed DTW
path has been removed from analysis and playback. Pause, seek, loop change, and
target change stop and recreate one atomic node set. Loop iterations are anchored
to an absolute epoch, so timer delay does not accumulate into audio drift.

Each asynchronous source load carries a transport generation. Project/take changes
dispose the old generation; any fetch or decode that completes later is ignored and
cannot overwrite the active transport's readiness. Playback validates that every
selected source produced schedulable nodes. A cursor at or beyond the canonical
mapping endpoint rewinds to zero before scheduling, avoiding a false playing state
with no audio.

Playback exposes only raw simultaneous timestamps and constant-offset correction.
Every scheduled source has playback rate 1.0. Display waveforms use the selected
raw or corrected offsets so waveform, pitch, cursor, and audio refer to the same
active timeline.

Raw discrepancies remain precise analysis measurements. `PracticeTarget`
construction associates them with baseline notes, groups compatible nearby
measurements, expands to note/phrase context, adds 0.75 seconds of pre/post roll,
enforces a 2.5-second minimum, and caps automatic loops at 6 seconds. User loop
edits never alter the underlying measurement.

Scoring has four explicit views over the same aligned voiced evidence:
original absolute pitch, a globally shifted reference, octave-wrapped pitch class,
and interval/contour movement. Transposition detection ranks integer shifts by the
weighted proportion of evidence within 50 cents. A detected shift becomes
authoritative only when support, support margin, and residual-error margin all pass
their gates. Multimodal evidence therefore produces an uncertain result rather than
an unsupported compromise shift. `analysis.metrics` remains a compatibility alias
to the default mode; new consumers use `analysis.scoring.modes`.

Manual transposition is an inexpensive, non-persistent scoring view. The scoring API
loads saved pitch and alignment artifacts, recomputes residual metrics and practice
targets, and does not rerun extraction, separation, pitch tracking, or alignment.
Take comparisons select one common mode: key-adjusted only when both detections are
reliable, otherwise original-pitch.

The timeline uses an explicit interaction state. Seek mode turns pointer clicks into
transport seeks and cannot create a loop. Loop mode ignores click-sized gestures,
creates ranges only from intentional drags, and interprets drags near existing gold
edges as resize operations. Original, shifted, and user contours are independently
visible; the active scoring reference is emphasized.

The per-take playback override is stored separately from analysis JSON and source
media. It affects browser playback only after an explicit Save; it never changes
scoring or cached DSP artifacts.

The package supports Python 3.11 while CI verifies Python 3.12. Supporting 3.11 is a
deliberate compatibility choice for the current local host and does not constrain the
recommended production runtime.

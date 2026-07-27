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
- Alignment combines global energy-envelope correlation with band-constrained DTW.

SQLite stores projects, takes, baseline versions, and pointers to artifact manifests.
NumPy NPZ stores dense frame arrays. JSON manifests record source hashes, algorithms,
versions, settings, outputs, warnings, and cache-hit evidence.

Discrepancies retain saved-baseline times for stable comparisons. Report playback
maps those ranges through the alignment path onto the current take timeline, so a
loop remains correct when the current recording is delayed or locally time-warped.

The local application adds a typed FastAPI orchestration boundary and a React
Canvas workspace. API handlers call `ProjectStore`, `analyze_take`, pitch loaders,
and display-summary services; they do not duplicate DSP or scoring in TypeScript.
Media selected in the browser enters a library-owned staging directory and is
copied into project-owned storage on import. Artifact endpoints resolve only
allow-listed paths beneath the selected project.

Synchronization has two explicit layers: system audio is aligned to the saved song
reference, then pitch-contour and energy-envelope evidence estimate one constant
microphone capture latency. Their estimates, confidences, disagreement, selection
method, matched coverage, and calibrated overall confidence remain in provenance.
The alignment artifact stores canonical baseline indices, current system-reference
indices, and microphone indices after latency correction.

Browser playback uses `SharedAudioTransport`, not independent
`HTMLAudioElement` clocks. It decodes both WAV artifacts into one `AudioContext`
and schedules both sources at the same future context time. Canonical baseline
time maps independently to reference and microphone time. The path is applied in
bounded segments, with a playback-rate correction per segment for local warping.
Pause, seek, loop change, and target change stop and recreate one atomic node set.
Loop iterations are anchored to an absolute epoch, so timer delay does not
accumulate into audio drift.

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

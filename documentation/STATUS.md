# Implementation status

Last updated: 2026-07-26

## Current milestone

The private-recording correctness findings have been addressed in code. Scoring now
separates original pitch, key-adjusted melody, octave-invariant melody, and
interval/contour evidence. Transposition detection rejects unsupported compromise
shifts, timeline clicks and loop drags are distinct, and active reference provenance
is visually separate from the next rebuild method. The Vienna take was reanalyzed
against its existing Demucs/CUDA baseline; final listening checks remain open
because no controllable browser was available in this session.

## Implemented

- Existing CLI, static report, SQLite metadata, immutable source hashing, and
  content-addressed audio/pitch caching
- Typed FastAPI boundary and allow-listed project/artifact access
- Local project library with confirmed deletion
- Raw local media ingestion, FFprobe inspection, stream previews, level summaries,
  role suggestions, and explicit assignment
- Observable background jobs with accurate queued/running/completed/failed state
- Explicit notice when a running stage cannot be cancelled safely
- Cached waveform summaries and decimated aligned pitch transport
- Canvas waveform, pitch, confidence, and baseline-note timeline
- Shared-clock Web Audio playback with decoded-source readiness, atomic scheduling,
  GainNodes, and User/Reference/Both presets
- Raw, constant-offset, and full-alignment playback modes
- Per-take diagnostic offset with explicit save and a -2 to +2 second range
- Advanced synchronization diagnostics with pitch and energy latency candidates
- Drift-free loop epoch scheduling and separately mapped source boundaries
- Raw measurement windows plus grouped 2.5-6 second practice targets
- Note-context, short-phrase, full-phrase, and custom loop modes
- Alignment-aware practice-target navigation and configurable pre/post roll
- Keyboard controls that remain inactive in forms
- Device-latency estimation separate from system-audio synchronization, with
  pitch/energy reconciliation and calibrated evidence confidence
- One-second delayed-microphone regression coverage and loop mapping
- Project take history, side-by-side metrics, overlaid pitch contours, and
  confidence-aware discrepancy comparison
- Baseline add/edit/delete/unscore, undo/redo, version creation, and rollback
- Reference baseline reuse with extraction/pitch cache provenance
- Demucs 4.1.0 optional dependency boundary with explicit invocation only
- Import/reanalysis Demucs selector, installation status, exact command, model
  provenance, baseline preservation, and reference-version contour comparison
- Full-mix provisional labels and octave/harmonic ambiguity suppression
- Support-first modal transposition detection with an explicit reliability gate
- Original-pitch, key-adjusted, octave-invariant, and interval/contour scoring views
- Temporary manual-key scoring without extraction, separation, pitch, or alignment
  invalidation
- Original artist, shifted-reference, and user contour layers with visibility
  controls and scoring emphasis
- Explicit seek and loop tools, minimum loop-drag gesture, loop-edge resizing, and
  clear-loop control
- Active baseline provenance separated from next-reference-rebuild settings
- Mode-compatible take comparisons
- Project-scoped recording-import drafts with fresh-import reset and an explicit
  Choose different recording action
- Generation-safe asynchronous audio loading and replay-from-end scheduling guards

## Degraded behavior

- The deterministic autocorrelation tracker remains the active pitch engine.
- The Vienna pitch evidence is multimodal. No detected key passes the coherence
  gate, so note-level key-adjusted targets require a manual shift.
- Active-stage cancellation is not yet safe; the UI says so rather than claiming
  cancellation.
- Source upload into the local API copies the selected file into project-owned
  storage; the original is never modified.
- The private take's synchronization estimators select approximately 0.40 seconds,
  while the user reported roughly one second by ear. The override can test the
  remaining approximately 0.60 seconds, but that value has not been calibrated or
  saved.

## Not yet implemented

- Tauri/Electron packaging and a one-process desktop launcher
- True cancellation/restart of active FFmpeg or model processes
- Advanced direct-manipulation piano roll and arbitrary manual alignment anchors
- Separate microphone-clock drift estimation; current device correction is a
  constant latency plus system-reference local alignment
- Advanced note attacks/settling, interval, timing, vibrato, and repeatability
  taxonomy beyond measurements currently produced by the backend
- TorchCREPE/pYIN adapters and model-management UI
- Final private OBS listening validation in an attached browser

## Verified state

- 37 Python tests pass.
- 23 frontend transport/state/gesture/import-lifecycle tests pass.
- Frontend production build and ESLint pass.
- A bounded launch check returned HTTP 200 from both the local API and UI.
- A synthetic microphone delayed by approximately one second was corrected before
  pitch comparison, and its loop range mapped to the delayed take timeline.
- The private take was reanalyzed without modifying its recording or rebuilding its
  baseline: baseline v7 reused; Demucs 4.1.0/htdemucs/CUDA provenance retained;
  extraction, reference extraction, user pitch, and baseline caches all hit.
- Its former -6-semitone result was rejected as an unsupported midpoint. The
  strongest candidate is 0 st at 18.7% support, runner-up -12 st, with only a
  4.5-point support margin, so detection is correctly marked uncertain.
- Vienna mode results: original-pitch median absolute difference 1163.6 cents;
  octave-invariant median error 78.6 cents with median placement one octave below;
  interval median error 70.1 cents and contour-direction agreement 61.5% across 403
  detected transitions. The single stored discrepancy requests manual key selection
  rather than emitting misleading note scores.
- The newest Test take serves both 102.25-second WAV artifacts with valid RIFF
  headers and HTTP 200 responses; its 2,549-point canonical/reference/user mapping
  spans the take.

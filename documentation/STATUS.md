# Implementation status

Last updated: 2026-07-26

## Current milestone

The private-recording correctness findings have been addressed in code. Scoring now
separates original pitch, key-adjusted melody, octave-invariant melody, and
interval/contour evidence. Transposition detection rejects unsupported compromise
shifts, timeline clicks and loop drags are distinct, and active reference provenance
is visually separate from the next rebuild method. Synchronization and playback now
use timestamp shifts only: one song-start offset and one microphone-device latency,
with every source kept at 1.0x. The remaining listening check requires a
controllable browser/audio session. Pitch tracking now has one production path:
TorchCREPE 0.0.24 full model with Viterbi decoding and explicit capability
reporting.

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
- Raw simultaneous and pitch-preserving constant-offset playback modes
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
- One-to-one shared-span alignment for unequal recording lengths and
  mode-consistent waveform timestamp shifts
- Original-pitch frame error labeled separately from detected key difference
- TorchCREPE 0.0.24 full-model pitch tracking on CUDA when available, whole-track
  Viterbi decoding, periodicity confidence, and centered RMS silence gating
- Explicit pitch capability/install status with no autocorrelation or pYIN fallback
- Immutable migration of legacy baselines by re-pitching their preserved vocal stem
  without rerunning separation

## Degraded behavior

- Similar original-pitch medians can be dominated by a shared octave-tracking
  displacement. The Test evidence contains incompatible clusters near both 0 and
  -12 semitones, so this frame statistic is not a key detector or a sufficient
  take-ranking metric. The UI now exposes one decimal place for tolerance
  percentages, voiced-frame counts, and an explicit incoherent-evidence warning.
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
- Separate microphone-clock drift detection; current synchronization deliberately
  assumes one constant song-start shift and one constant device latency
- Advanced note attacks/settling, interval, timing, vibrato, and repeatability
  taxonomy beyond measurements currently produced by the backend
- Final private OBS listening validation in an attached browser

## Verified state

- 38 Python tests pass.
- 26 frontend transport/state/gesture/import-lifecycle tests pass.
- Frontend production build and ESLint pass.
- A bounded launch check returned HTTP 200 from both the local API and UI.
- A synthetic microphone delayed by approximately one second was corrected before
  pitch comparison, and its loop range mapped to the delayed take timeline.
- Vienna source recordings remain unmodified, and baseline versions 1-11 remain
  available. Baseline v11 re-pitches v10's preserved full-length Demucs vocal stem
  with TorchCREPE; no separation rerun occurred.
- Both Vienna takes now use baseline v11 and TorchCREPE. Take 1 reports 1262.3 cents
  across 559 aligned voiced frames and a -12-semitone candidate at 34.0% support.
  Take 2 reports 1186.4 cents across 295 frames and -12 semitones at 43.4% support.
  Neither candidate is reliable, so key-adjusted scoring remains gated.
- The newest Test take has a +1.06-second system-reference offset and approximately
  +0.28-second microphone latency. Both Test takes were reanalyzed with the
  `constant-offset` profile. Local warping has been removed; analysis and playback
  now advance the shared span one-to-one at 1.0x.
- Vienna take 2 was rebuilt as preserved baseline v10 with
  Demucs 4.1.0/htdemucs/CUDA. Its full 101.94-second canonical mapping advances
  one-to-one at 1.0x.
- TorchCREPE 0.0.24 is installed locally and selects the full model, Viterbi
  decoder, and CUDA device. Synthetic A4 and silence checks pass without invoking
  TorchCREPE's slow librosa/Numba silence path.
- The Test baseline was migrated from v3 to v4 using its preserved Demucs vocal
  stem. No separation rerun occurred. Both takes now use the same TorchCREPE
  tracker: take 1 reports 1185.2 cents across 296 aligned voiced frames and take 2
  reports 1197.3 cents across 1,136 frames.
- The Test takes no longer report an identical support value: their strongest
  -12-semitone candidates have 43.8% and 40.5% support. Both remain below the
  reliability gate, so the UI correctly treats the detected key as uncertain.

You are the lead engineer responsible for designing and implementing a local-first desktop application for analyzing singing accuracy.

The application’s working name is **VocalLab**.

Your task is to build the application iteratively, beginning with a working end-to-end vertical slice. Do not stop at planning, architecture discussion, pseudocode, or mock interfaces. Create the repository structure, write production-quality code, add tests, run the implementation, inspect outputs, and continue fixing problems until the current milestone works.

# Product intent

The application is a precise feedback tool for private singing practice.

The user’s core learning loop is:

1. Record a singing attempt while listening to a song.
2. Detect where the attempt diverged from the intended melody or performance.
3. Loop the problematic region.
4. Experiment with different ways of producing the phrase.
5. Record additional attempts.
6. Compare the attempts objectively.
7. Retain the approach that is accurate, comfortable, pleasant, and repeatable.
8. Gradually develop an internal sense of pitch that does not depend on visual feedback.

The application is not primarily a karaoke scoring game.

Its central purpose is to answer:

* Where did the user stop matching?
* How did the user differ?
* Was the note sharp, flat, late, early, unstable, undershot, overshot, or shifted?
* Did the user sing the correct melody in another key or octave?
* Did a note begin inaccurately and later settle?
* Did a sustained note drift?
* Was a changed note intentional or accidental?
* Which attempt was most accurate?
* Was the improvement repeatable?

The interface should prioritize specific discrepancies and fast experimentation rather than a large opaque overall score.

# Primary use case

The user listens to Spotify through headphones and records with OBS.

OBS produces a recording containing separate audio streams, ideally:

* Microphone
* System audio containing the song
* Optional combined monitoring mix

The application imports the OBS recording and uses:

* The microphone stream as the user performance
* The system-audio stream as the synchronization and reference source

All processing must remain local.

The application must not:

* Download music from Spotify
* Circumvent DRM
* Inspect or extract Spotify caches
* Redistribute music
* Upload copyrighted audio
* Provide music-sharing functionality
* Require a cloud account
* Depend on a public backend

The user is responsible for creating their own local OBS recordings for private analysis.

# Product principles

Follow these principles throughout implementation:

1. **Discrepancy-first**

   * The primary output is a prioritized list of meaningful mismatches.
   * Do not make an unexplained aggregate score the center of the product.

2. **Automatic by default, editable when needed**

   * Generate reference baselines automatically.
   * Surface uncertainty.
   * Allow the user to correct notes, timing, regions, and alignment.
   * Reuse corrected baselines forever.

3. **Measurements before diagnoses**

   * State what happened acoustically.
   * Do not claim to diagnose breath support, larynx position, vocal health, placement, resonance strategy, or physical technique.

4. **Accuracy without artistic rigidity**

   * Separate nominal melody accuracy from similarity to the original singer.
   * Do not classify every expressive difference as an error.
   * Preserve slides, vibrato, scoops, ornaments, and phrasing information.

5. **Transposition-aware**

   * A melody sung accurately in another key must not be treated as entirely wrong.
   * Detect global key changes and octave displacement.
   * Support interval-only comparison.

6. **Repeatability matters**

   * One accurate note may be luck.
   * Multiple similar accurate attempts indicate learned coordination.
   * Make comparison across attempts easy.

7. **Post-take feedback by default**

   * Avoid making the application primarily a live visual tuner.
   * The user should normally sing first, predict what went wrong, and review afterward.

8. **Local-first and inspectable**

   * Preserve raw outputs.
   * Cache deterministic computations.
   * Store model versions and settings.
   * Make intermediate artifacts available for debugging.

9. **Incremental recomputation**

   * Editing a note must not rerun source separation.
   * Changing scoring tolerances must not rerun pitch extraction.
   * Updating alignment anchors should only rerun alignment and downstream scoring.

10. **Elegant repeated use**

    * The first analysis of a song may require heavier processing and occasional correction.
    * Every subsequent take should be fast.

# Core workflows

## Workflow A: First take for a song

1. Create a song project.
2. Import an OBS recording.
3. Inspect all media streams with FFprobe.
4. Present all audio streams to the user.
5. Suggest stream roles:

   * Microphone
   * Reference/system audio
   * Mixed
   * Unknown
6. Allow auditioning and manual correction.
7. Extract normalized working audio without modifying the source.
8. Separate the reference audio into:

   * Vocals
   * Instrumental
9. Track pitch for:

   * User microphone
   * Isolated reference vocal
10. Extract synchronization features.
11. Estimate global offset.
12. Estimate constrained local alignment.
13. Detect transposition and octave displacement.
14. Build:

* Raw continuous reference pitch contour
* Smoothed reference contour
* Simplified editable note baseline

15. Display uncertainty and likely extraction errors.
16. Allow baseline correction.
17. Save the baseline.
18. Score the user’s take.
19. Present prioritized discrepancies.
20. Allow instant looping and comparison.

## Workflow B: Subsequent take

1. Open an existing song project.
2. Import another OBS recording.
3. Reuse the saved reference baseline and cached stems.
4. Extract the new microphone track.
5. Use the system-audio track for synchronization.
6. Align the new take.
7. Analyze it against the existing baseline.
8. Add it to take history.
9. Compare it with:

   * Previous take
   * Best take
   * Selected take
   * Phrase-level history
10. Highlight improvements, regressions, and repeated errors.

## Workflow C: Practice experiment

1. Select a flagged phrase or note.
2. Loop:

   * Reference
   * User
   * Both
   * Instrumental plus user
3. Record several variants.
4. Compare variants side by side.
5. Show:

   * Accuracy
   * Timing
   * Stability
   * Settling behavior
   * Repeatability
6. Let the user mark a take or phrase as preferred.
7. Allow a deliberate note substitution to be saved into a personal baseline.

# V1 scope

Keep V1 grounded, but implement its core correctly.

V1 must support:

* Importing an OBS MKV recording
* Detecting and extracting separate audio streams
* Manual stream assignment
* Isolating a reference vocal
* Pitch tracking for reference and user
* Global synchronization
* Constrained alignment
* Transposition detection
* Octave-shift detection
* Continuous pitch visualization
* Simplified note-baseline generation
* Manual note correction
* Note- and phrase-level discrepancy detection
* Loop playback
* Reusable song baselines
* Comparison of multiple takes
* Cached processing
* Local project persistence
* Automated tests
* A usable local graphical interface after the pipeline is validated

Do not include these in the first complete milestone:

* Real-time pitch feedback
* Automatic lyric or phoneme alignment
* Breath-support diagnosis
* Vocal-health diagnosis
* Timbre-quality scoring
* Choir-part extraction from arbitrary mixes
* Mobile applications
* Cloud synchronization
* Social or sharing features
* Spotify API integration
* Music downloading
* Universal support for every possible song

Design the architecture so lyrics and phoneme alignment can be added later, but do not let that delay the core V1.

# Analysis modes

Implement the following comparison modes.

## 1. Absolute pitch

Compare the user directly against the reference’s original pitch.

Use this to answer:

* Did the user sing in the original key?
* What was the absolute pitch difference?

## 2. Transposition-aware

Estimate the global integer semitone shift that best explains the user’s performance.

Search at least:

* −12 through +12 semitones

Return:

* Best shift
* Second-best shift
* Confidence margin
* Percentage of voiced evidence supporting the result

Example:

> Melody matched at −5 semitones.

## 3. Octave-invariant

Treat octave-equivalent notes as melodic matches while separately reporting octave displacement.

Example:

> Melody matched one octave below the reference.

## 4. Interval-only

Compare melodic intervals and contour without requiring the same starting pitch.

## 5. Simplified note accuracy

Compare stable portions of the user’s notes against discrete baseline notes.

## 6. Original-performance similarity

Compare continuous user pitch movement with the original singer’s contour.

This mode may consider:

* Slides
* Scoops
* Vibrato
* Transition shapes
* Phrase timing

Keep this score separate from nominal melody correctness.

# Discrepancy taxonomy

The system should identify and classify useful discrepancies.

At minimum:

* Consistently sharp
* Consistently flat
* Note began flat and settled
* Note began sharp and settled
* Overshot target
* Undershot interval
* Overshot interval
* Pitch drifted flat
* Pitch drifted sharp
* Unstable sustained note
* Early onset
* Late onset
* Early release
* Late release
* Wrong discrete note
* Octave substitution
* Deliberate alternate note
* Missing note
* Extra note
* Low-confidence pitch estimate
* Low-confidence alignment
* Contaminated reference region
* Multiple reference vocals detected
* Unscored consonant, breath, or silence

A discrepancy should include:

* Time range
* Phrase
* Baseline note
* Sung note or contour
* Magnitude
* Confidence
* Plain-language explanation
* Suggested loop region
* Comparison with prior takes

Example output:

> 0:42.10–0:43.35 — High note began 48 cents flat, reached the target after 210 ms, and remained centered for the rest of the note.

Another example:

> 1:02.50–1:04.00 — Correct melodic interval after accounting for a −3-semitone global transposition.

# Audio import

Support at minimum:

* MKV
* MP4
* MOV
* WAV
* FLAC
* MP3
* M4A

Use FFmpeg and FFprobe.

Inspect:

* Number of streams
* Codec
* Sample rate
* Channel count
* Duration
* Stream metadata
* Peak
* RMS
* Silence ratio
* Stereo correlation

Working audio should generally use:

* Mono when appropriate
* 48 kHz or a deliberate project-wide standard
* Floating-point arrays internally
* No clipping
* No pitch or time alteration during normalization

Preserve original imported files unchanged.

# Source separation

Use a pluggable separation interface.

Preferred initial implementation:

* Demucs or a compatible high-quality local model

Extract at least:

* Vocal stem
* Instrumental stem

Cache separation using a key containing:

* Source-file hash
* Model name
* Model version
* Settings
* Output sample rate

Expose confidence or warning indicators for:

* Backing-vocal contamination
* Vocal doubling
* Multiple singers
* Heavy reverb
* Instrument bleed
* Separation artifacts
* Low vocal prominence

Allow the user to mark reference regions:

* Valid lead vocal
* Backing vocal
* Instrumental
* Unreliable
* Excluded from scoring

# Pitch tracking

Use a pluggable interface.

Preferred initial engines:

* TorchCREPE 0.0.24 full model as the only production tracker
* No silent pitch-tracker fallback

Default vocal range:

* C2 through C7

Make the range configurable.

For every analysis frame, retain:

* Timestamp
* Fundamental frequency
* MIDI pitch
* Cents relative to nearest equal-tempered note
* Voicing probability
* Pitch confidence
* RMS or loudness
* Tracker identity
* Raw estimate
* Corrected estimate

Target frame hop:

* Roughly 5–15 ms

Make it configurable.

Maintain:

1. Raw pitch contour
2. Corrected pitch contour
3. Smoothed musical contour

Pitch cleanup may use:

* Temporal continuity
* Confidence
* Expected vocal range
* Harmonic evidence
* Octave-error correction
* Median filtering
* Viterbi-style sequence smoothing

Do not smooth away:

* Genuine vibrato
* Fast transitions
* Scoops
* Portamento
* Grace notes

Do not score insufficiently voiced frames.

# Note segmentation

Convert pitch contours into editable note candidates.

Use:

* Pitch stability
* Pitch jumps
* Energy
* Onset strength
* Voicing transitions
* Duration
* Musical context

Each note should contain:

* Start time
* End time
* Attack region
* Stable region
* Release region
* Optional transition region
* MIDI note
* Cents offset
* Confidence
* Phrase ID
* Ornamental flag
* Scored flag
* Source:

  * Automatic
  * Manual
  * MIDI
  * Imported

Full pitch weight should be applied mainly to the stable region.

The editor must allow:

* Move note
* Resize note
* Add note
* Delete note
* Split note
* Merge notes
* Quantize note
* Preserve microtonal offsets
* Mark ornament
* Mark unscored
* Group into phrase
* Undo
* Redo

# Alignment

Implement alignment in layers.

## Global alignment

Estimate initial latency and offset using one or more of:

* Cross-correlation
* Onset-envelope correlation
* Chroma correlation
* Spectral features
* Reference leakage in the microphone
* Manual sync marker

## Shared-span alignment

After global synchronization, advance baseline and current-reference frames
one-to-one through their shared span. Apply one separate constant microphone-device
latency. Do not use DTW or any other local time warp: early or late phrases, held
notes, missing notes, extra notes, and repeated sections must remain visible as
performance evidence.

Store and display:

* Global offset
* Microphone-device latency
* Shared-span coverage
* Alignment confidence
* Low-confidence regions

Allow manual alignment anchors.

Editing an anchor should rerun only alignment and downstream scoring.

# Scoring

Do not make a single overall score the main result.

Calculate and expose:

## Pitch

* Median signed cents error
* Median absolute cents error
* Mean absolute cents error
* 90th-percentile absolute cents error
* Percentage within ±15 cents
* Percentage within ±25 cents
* Percentage within ±35 cents
* Percentage within ±50 cents
* Percentage within ±100 cents
* Sharp-frame percentage
* Flat-frame percentage
* Persistent bias
* Note-center accuracy
* Interval accuracy
* Octave-error count

## Timing

* Median onset error
* Median release error
* Note-duration error
* Phrase-entry error
* Phrase-ending error
* Early-entry rate
* Late-entry rate
* Tempo drift
* Alignment deviation

## Stability

* Standard deviation in stable note regions
* Drift across sustained notes
* Time required to settle
* Attack-to-center difference
* End-of-note fall or rise
* Repeated-note consistency
* Repeated-phrase consistency

## Performance similarity

Where reliable:

* Continuous contour similarity
* Slide similarity
* Vibrato-rate similarity
* Vibrato-depth similarity
* Vibrato-onset similarity
* Phrase timing similarity

Do not penalize absence of vibrato in nominal note-accuracy mode.

# Repeatability and experiment comparison

This is a central feature, not a minor enhancement.

For repeated attempts at the same region, calculate:

* Mean accuracy
* Best accuracy
* Variance across attempts
* Consistency of onset
* Consistency of pitch center
* Consistency of drift
* Whether an apparent improvement repeated
* Whether one attempt was merely an outlier

Allow the user to compare:

* Take A vs. Take B
* Current vs. previous
* Current vs. personal best
* Current vs. average
* Several attempts of one phrase

Allow the user to select:

* Preferred take
* Preferred phrase
* Personal-baseline note change
* Intentional alternative note

# Primary interface

The main analysis screen should include:

* Reference waveform
* User waveform
* Isolated reference vocal waveform
* Optional instrumental waveform
* Reference pitch contour
* User pitch contour
* Simplified baseline notes
* Phrase regions
* Confidence overlay
* Playback cursor
* Loop range
* Scoring mode selector
* Transposition selector
* Octave handling
* Alignment confidence
* Prioritized discrepancy list

Clicking a discrepancy must:

* Select the region
* Zoom appropriately
* Loop it
* Show relevant measurements
* Allow quick comparison with another attempt

Playback modes:

* Reference only
* User only
* Both
* Instrumental plus user
* Isolated singer plus user
* User with pitch-shifted reference
* Slow playback without pitch change

# Project screens

Implement these screens over time:

1. Song library
2. Song-project overview
3. Import wizard
4. Track assignment
5. Processing status
6. Baseline editor
7. Take analysis
8. Take comparison
9. Practice-region view
10. Settings and model management

# Song project metadata

Store:

* Title
* Artist
* Optional Spotify URL
* Original key
* Preferred user key
* Preferred transposition
* Tags
* Notes
* Baseline versions
* Takes
* Last practiced date
* Personal best
* Processing state

No Spotify integration is required.

# Recommended architecture

Use a local-first modular architecture.

Suggested repository structure:

```text
vocal-lab/
├── apps/
│   ├── desktop/
│   └── api/
├── packages/
│   ├── audio_io/
│   ├── separation/
│   ├── pitch/
│   ├── segmentation/
│   ├── alignment/
│   ├── scoring/
│   ├── baseline/
│   ├── projects/
│   ├── visualization/
│   └── shared_models/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── synthetic/
│   └── fixtures/
├── scripts/
├── docs/
└── pyproject.toml
```

Recommended backend:

* Python 3.12+
* NumPy
* SciPy
* librosa
* PyTorch
* TorchCREPE 0.0.24
* Demucs
* FFmpeg
* FFprobe
* SoundFile
* Pydantic
* SQLite
* SQLAlchemy or equivalent
* FastAPI as a local service boundary if useful

Recommended frontend:

* TypeScript
* React
* Vite
* Canvas or WebGL for dense pitch and waveform rendering

Desktop packaging:

* Tauri preferred, or Electron if technical constraints justify it
* Python analysis backend may run as a managed local sidecar

Remain functional offline once models and dependencies are installed.

You may adjust technologies when there is a concrete engineering reason, but document the rationale and preserve all product requirements.

# Data storage

Use SQLite for relational metadata.

Do not store dense frame arrays directly in JSON.

Use an appropriate format such as:

* NumPy
* Parquet
* Zarr

Every analysis result must retain:

* Source hashes
* Model names
* Model versions
* Parameters
* Baseline version
* Alignment settings
* User overrides
* Application version
* Processing logs

Preserve prior analysis versions when:

* Baseline changes
* Alignment changes
* Models change
* Major parameters change

# Caching

Cache all expensive deterministic stages:

* Stream extraction
* Audio conversion
* Stem separation
* Pitch tracking
* Chroma
* Onset envelopes
* Waveform summaries
* Note segmentation
* Alignment
* Baseline generation
* Scoring

Cache keys must include all inputs capable of changing output.

Build explicit dependency invalidation.

Examples:

* Changing score tolerance invalidates scoring only.
* Editing notes invalidates note mapping and scoring.
* Editing alignment anchors invalidates alignment and scoring.
* Changing pitch tracker invalidates pitch and all downstream artifacts.
* Changing source separation model invalidates stems and downstream reference processing.

# Background processing

Long-running local jobs must be:

* Cancellable
* Restartable
* Observable
* Logged
* Cache-aware

Jobs include:

* Extraction
* Separation
* Pitch tracking
* Feature extraction
* Segmentation
* Alignment
* Baseline generation
* Scoring

The UI must remain responsive.

# Reliability

Handle these gracefully:

* Missing FFmpeg
* Unsupported codecs
* Corrupt recordings
* Silent tracks
* Clipping
* Very quiet microphones
* Reference bleed
* Wrong stream assignment
* Missing system audio
* Separation failure
* Pitch failure
* No voiced regions
* Alignment failure
* Partial-song mismatch
* Different recording version
* Live vs. studio mismatch
* Wrong verse or chorus
* Multiple singers
* Instrumental regions
* Low disk space
* Interrupted processing

Every recoverable error should include:

* What happened
* Why it may have happened
* What the user can do next
* Retry path

# Privacy

Default behavior:

* No account
* No uploads
* No cloud processing
* No telemetry containing audio
* No public sharing
* No redistribution
* No copyrighted reference audio in exports by default

Project deletion should optionally remove:

* Extracted tracks
* Stems
* Features
* Caches
* Analysis results

Never modify the original imported recording.

# Testing

Testing is mandatory.

## Unit tests

Include:

* Hz to MIDI
* MIDI to Hz
* Cents calculations
* Transposition detection
* Octave decomposition
* Pitch masks
* Smoothing
* Segmentation
* Timing metrics
* Stability metrics
* Cache invalidation
* Data migrations
* Alignment constraints

## Synthetic tests

Generate known vocal-like signals with:

* Fundamental
* Harmonics
* Noise
* Vibrato
* Slides
* Controlled onsets
* Controlled timing error
* Controlled pitch drift
* Controlled transposition
* Controlled octave displacement

Test:

* Perfect match
* Fixed sharp bias
* Fixed flat bias
* Undershoot
* Overshoot
* Late settling
* End-of-note drift
* Vibrato
* Missed note
* Extra note
* Early entrance
* Late entrance
* Tempo drift
* Partial phrase
* Silence
* Octave error

Expected ground truth must be known.

## Integration tests

Include:

* Import MKV
* Inspect streams
* Extract streams
* Run separation
* Run pitch tracking
* Align
* Detect transposition
* Produce a static report
* Cache and rerun
* Reuse baseline for a second take

## UI tests

Include:

* Import
* Stream preview
* Assignment
* Baseline editing
* Undo and redo
* Looping
* Comparison
* Error recovery
* Cache clearing

# Initial vertical slice

Implement this before building a large UI.

The first end-to-end milestone must:

1. Accept one OBS MKV recording.
2. Inspect and list audio streams.
3. Allow explicit mic and reference stream selection through CLI arguments or a minimal UI.
4. Extract both streams.
5. Separate the reference vocal.
6. Track reference and user pitch.
7. Estimate global synchronization.
8. Estimate constrained alignment.
9. Detect transposition.
10. Detect octave displacement.
11. Generate a continuous pitch comparison.
12. Generate a basic simplified note baseline.
13. Calculate core pitch metrics.
14. Identify a small discrepancy list.
15. Produce a static HTML report with:

    * Audio playback
    * Waveforms
    * Pitch contours
    * Baseline notes
    * Discrepancies
    * Metrics
16. Save all artifacts into a reusable project directory.
17. Import a second take and reuse the reference processing.
18. Compare the two takes.
19. Prove cache reuse in tests or logs.

Use one verse or chorus rather than requiring an entire song.

The first intended real-world test song is “Vienna,” but no song-specific logic may be hard-coded.

# Initial CLI

Provide a usable CLI during Phase 1.

Example:

```bash
vocallab inspect recording.mkv
```

```bash
vocallab create-project \
  --title "Vienna" \
  --artist "Billy Joel" \
  --project-dir ./projects/vienna
```

```bash
vocallab import-take \
  --project ./projects/vienna \
  --input ./recordings/vienna_take_01.mkv \
  --mic-stream 2 \
  --reference-stream 1
```

```bash
vocallab analyze \
  --project ./projects/vienna \
  --take latest
```

```bash
vocallab report \
  --project ./projects/vienna \
  --take latest \
  --open
```

Exact command design may change, but preserve equivalent capability.

# Implementation sequence

Follow this order unless repository constraints require a documented adjustment.

## Milestone 0: Repository and environment

* Inspect the existing repository.
* Preserve useful existing work.
* Establish the project structure.
* Add environment setup.
* Add dependency management.
* Detect FFmpeg.
* Add structured logging.
* Add typed configuration.
* Add basic CI.
* Add a short developer README.

## Milestone 1: Data and artifact layer

* Typed project models
* File hashing
* Artifact paths
* Cache manifests
* Versioning
* SQLite metadata
* Dense feature storage
* Dependency invalidation tests

## Milestone 2: Audio ingestion

* FFprobe inspection
* Stream metadata
* Audio previews
* Deterministic extraction
* Normalization
* Audio validation
* Unit and integration tests

## Milestone 3: Pitch pipeline

* Pitch-engine interface
* TorchCREPE full-model implementation with explicit capability reporting
* Legacy baseline migration without rerunning preserved source separation
* Voicing
* Confidence
* Smoothing
* Octave correction
* Synthetic pitch tests

## Milestone 4: Reference pipeline

* Source-separation interface
* Demucs integration
* Stem caching
* Reference pitch
* Confidence flags
* Simplified note segmentation

## Milestone 5: Alignment and transposition

* Global offset
* Alignment feature extraction
* One-to-one shared-span mapping
* Constant microphone-device latency
* Manual-anchor data model
* Transposition search
* Octave decomposition
* Synthetic and integration tests

## Milestone 6: Scoring and discrepancies

* Frame metrics
* Note metrics
* Phrase metrics
* Settling
* Drift
* Timing
* Discrepancy taxonomy
* Confidence-aware feedback

## Milestone 7: Static report

* Embedded local playback
* Pitch overlay
* Waveforms
* Baseline notes
* Discrepancy list
* Metrics
* Take comparison

## Milestone 8: Desktop UI

Only begin the full desktop UI after the pipeline and static report are validated.

Implement:

* Library
* Import wizard
* Track assignment
* Processing status
* Analysis view
* Loop playback
* Baseline editor
* Take comparison

# Development behavior

Work autonomously.

Do not pause after producing a plan unless blocked by missing credentials, missing files, or an irreversible choice.

When reasonable assumptions are needed:

* Choose a sensible default.
* Document it.
* Keep it configurable.
* Continue.

Do not remove ambitious requirements merely because they are difficult.

Instead:

* Build replaceable interfaces.
* Implement a robust first version.
* Add confidence and fallback behavior.
* Leave explicit extension points.
* Continue to the next working vertical slice.

Prefer a partially complete working system over a broad collection of unintegrated components.

After each milestone:

1. Run formatters.
2. Run type checks.
3. Run unit tests.
4. Run relevant integration tests.
5. Exercise the CLI manually.
6. Inspect generated artifacts.
7. Fix obvious issues.
8. Update documentation.
9. Summarize what changed and what remains.

# Code quality

Requirements:

* Strong typing
* Clear module boundaries
* Small replaceable interfaces
* Deterministic processing where possible
* Structured logs
* Useful exceptions
* No silent failures
* No unexplained magic constants
* Configuration validation
* Reproducible outputs
* Testable pure functions for calculations
* Comments explaining non-obvious DSP decisions
* Documentation for model and algorithm tradeoffs

Avoid:

* Giant untyped notebooks
* Logic embedded solely in UI components
* Hidden global state
* Recomputing expensive work unnecessarily
* Destructive file operations
* Hard-coded user paths
* Hard-coded song assumptions
* Premature microservices
* A decorative UI with a fake analysis backend

# Definition of success for V1

V1 is successful when the user can:

1. Record a verse or chorus with OBS.
2. Import the recording.
3. Confirm the microphone and song tracks.
4. Let the system build an initial reference.
5. Correct obvious baseline mistakes.
6. See exactly where their pitch or timing differed.
7. Click a discrepancy and loop it.
8. Try the phrase again.
9. Import the new attempt.
10. See whether it improved.
11. Repeat until the phrase is accurate and repeatable.
12. Reuse the same baseline without reprocessing the song.

The most important output is not:

> Your score is 83.

The most important output is:

> On this note, you began 61 cents flat, reached the target after 240 ms, and drifted flat again during the final 300 ms. Your second attempt reached the target 170 ms sooner and remained within ±25 cents.

Build toward that experience.

Begin by inspecting the repository and implementing Milestone 0 and the smallest working portion of Milestone 1. Continue through the vertical slice without waiting for additional product clarification unless an actual blocker prevents progress.

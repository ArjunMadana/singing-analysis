# Vocal Accuracy Analyzer

## Product and Technical Requirements Document

**Status:** Initial implementation specification
**Working name:** VocalLab
**Primary user:** A singer practicing along with commercially streamed music for private, personal analysis
**Deployment model:** Local-first desktop application
**Primary input:** Multitrack OBS recordings containing isolated microphone and system-audio tracks
**Primary output:** Visual and quantitative comparison of the user’s singing against one or more reusable melodic baselines

---

# 1. Product Summary

Build a polished local application that analyzes a recorded singing performance and compares it against a reference baseline derived from the original song, a simplified melody, a previous performance, or a manually supplied note track.

The application should make it easy to:

1. Record Spotify playback and a microphone as separate tracks using OBS.
2. Import the resulting OBS recording.
3. Automatically identify and extract the microphone and reference-audio tracks.
4. Isolate the original lead vocal from the reference audio.
5. Extract pitch, timing, note, vibrato, and phrasing information from both recordings.
6. Align the user’s performance with the reference.
7. Detect whether the user sang in a different key or octave.
8. Present clear, actionable feedback.
9. Save a corrected baseline so future takes of the same song can be analyzed quickly.
10. Compare multiple takes over time.

The application is intended for private practice. It must not include music-sharing, uploading, redistribution, public hosting, or music-library synchronization features.

---

# 2. Product Goals

## 2.1 Primary goals

The application must answer the following questions:

* Did I sing the intended melody?
* Which notes were sharp or flat?
* Do I tend to sing consistently sharp or flat?
* Did I sing in the same key as the original?
* Did I preserve the correct intervals if I changed the key?
* Were my entrances early or late?
* Did I sustain notes for the correct duration?
* Was my pitch stable during sustained notes?
* Did I match the original singer’s slides, vibrato, and phrasing?
* Am I improving across repeated takes?
* Which specific phrases should I practice again?

## 2.2 Experience goals

The application should feel:

* Automatic by default
* Transparent when uncertainty exists
* Editable when automatic analysis is imperfect
* Fast on repeated takes
* Musically informed rather than merely mathematical
* Useful to a singer without requiring expertise in signal processing
* Detailed enough for technical inspection when desired

## 2.3 Success criteria

A successful implementation allows the user to:

1. Import an OBS recording.
2. Select or confirm the microphone and system-audio tracks.
3. Generate a reference baseline.
4. Review and correct the baseline.
5. analyze a vocal take.
6. identify pitch and timing problems at phrase and note level.
7. repeat the process for a new take without regenerating the reference baseline.
8. see improvement across takes.

---

# 3. Non-Goals

The initial product does not need to:

* Record or download Spotify audio directly.
* Circumvent DRM or extract Spotify cache files.
* Redistribute, stream, upload, or share copyrighted audio.
* Replace OBS as the recording application.
* Provide real-time live pitch correction.
* Function as a digital audio workstation.
* Train a singing voice model.
* Judge vocal tone, beauty, genre authenticity, or emotional quality.
* Produce a single opaque “good singer” score.
* Support polyphonic choir analysis of the microphone recording.
* Automatically identify every singer in a complex duet.
* Guarantee perfect melody extraction from every commercial mix.

The architecture should not prevent later support for real-time analysis, but real-time operation is not required for the first release.

---

# 4. Core User Workflow

## 4.1 Recording workflow

The user configures OBS with separate audio tracks:

* Microphone
* System audio containing Spotify playback
* Optional combined monitoring mix

Recommended recording format:

* MKV container
* 48 kHz audio
* Separate audio tracks
* Lossless or high-quality audio codec where practical

The application should include an OBS setup guide showing the required configuration.

## 4.2 First analysis of a song

1. User creates a song project.
2. User imports an OBS recording.
3. Application inspects the container and lists all audio streams.
4. Application attempts to classify each stream as:

   * Microphone
   * Reference/system audio
   * Mixed audio
   * Unknown
5. User confirms or corrects track assignments.
6. Application extracts normalized working audio files.
7. Application isolates the lead vocal from the reference audio.
8. Application extracts:

   * Reference pitch contour
   * User pitch contour
   * Voicing probability
   * Loudness envelope
   * Chroma features
   * Onsets
   * Note candidates
9. Application estimates:

   * Global latency offset
   * Tempo relationship
   * Time-warp alignment
   * Key or transposition difference
   * Octave difference
10. Application creates an initial reference baseline.
11. User reviews the baseline in an editor.
12. User corrects obvious errors where needed.
13. Application saves the baseline.
14. Application calculates performance metrics.
15. Application displays phrase-, note-, and session-level feedback.

## 4.3 Subsequent take workflow

1. User opens an existing song project.
2. User imports a new OBS recording.
3. Application reuses the saved baseline.
4. Application extracts only the new microphone performance and synchronization reference.
5. Application aligns the new take.
6. Application calculates metrics.
7. Application adds the take to the project history.
8. Application shows changes relative to prior takes and the user’s personal best.

## 4.4 Partial-song workflow

The user must be able to analyze:

* Entire songs
* A verse
* A chorus
* A manually selected time range
* A repeated practice loop

The application must not require a complete recording of the song.

---

# 5. Baseline Types

The application must support multiple baseline types within the same song project.

## 5.1 Original-performance contour

Derived from the isolated lead vocal of the reference recording.

Use this baseline to measure:

* Performance similarity
* Slides
* Scoops
* Vibrato
* Timing
* Phrasing
* Artist-specific pitch behavior

The raw contour must preserve continuous pitch movement.

## 5.2 Simplified note baseline

Derived from the original-performance contour or manually entered.

Use this baseline to measure:

* Intended notes
* Note centers
* Intervals
* Relative timing
* Note durations

The simplified baseline should convert a continuous pitch curve into editable note events.

Each note event must include:

* Start time
* End time
* Target pitch
* MIDI note number
* Optional cents offset
* Confidence
* Source
* Phrase identifier
* Whether the note is optional, ornamental, or unscored

## 5.3 Previous-take baseline

The user may select any prior take as a comparison baseline.

Use this to measure:

* Consistency
* Improvement
* Stability
* Phrase timing
* Pitch drift
* Repeatability

## 5.4 Personal-best composite

The application may construct a composite baseline from the best-performing phrases across multiple takes.

This must be clearly labeled as a personal reference rather than an authoritative melody.

## 5.5 Manual or MIDI baseline

The application must allow:

* MIDI import
* MusicXML import as a later enhancement
* Manual piano-roll note entry
* Manual note deletion, movement, resizing, splitting, and merging

A manually edited baseline always takes precedence over automatically inferred notes.

---

# 6. Required Analysis Modes

## 6.1 Absolute-pitch mode

Compare the user’s actual pitch directly with the reference pitch.

Use this to determine whether the user sang in the original key and octave.

## 6.2 Transposition-aware mode

Automatically estimate the most likely global semitone offset between the user and the reference.

Example result:

> Melody matched at −5 semitones.

The system must distinguish a consistent key change from inaccurate singing.

## 6.3 Octave-invariant mode

Treat notes separated by whole octaves as equivalent for melody scoring while still reporting the octave difference.

Example:

> Melody and intervals matched, one octave below the original.

## 6.4 Interval-only mode

Compare melodic intervals and contour independently of absolute key.

This should be useful when the user intentionally chooses a different starting pitch.

## 6.5 Performance-similarity mode

Compare the user’s continuous pitch contour with the original singer’s contour.

This mode should consider:

* Slides
* Scoops
* Vibrato timing
* Vibrato rate
* Vibrato depth
* Note transitions
* Phrase timing

## 6.6 Note-accuracy mode

Compare the stable portion of each sung note with the simplified note baseline.

This mode must not heavily penalize:

* Consonants
* Breath sounds
* Initial pitch approach
* Intentional slides
* Vibrato around the note center
* Unvoiced gaps between syllables

---

# 7. Audio Import Requirements

## 7.1 Supported containers

At minimum:

* MKV
* MP4
* MOV
* WAV
* FLAC
* MP3
* M4A

## 7.2 Stream inspection

Use FFmpeg or FFprobe to inspect:

* Stream count
* Codec
* Sample rate
* Channel count
* Duration
* Stream title
* Stream metadata
* Peak and RMS levels
* Silence ratio
* Stereo correlation

## 7.3 Track assignment

The application should automatically suggest track roles using heuristics such as:

* Microphone tracks often contain isolated speech or singing.
* System-audio tracks often contain continuous full-band music.
* Mixed tracks contain both.
* Silent or nearly silent tracks should be ignored by default.

The user must be able to audition each track and override the assignment.

## 7.4 Working audio format

Convert analysis inputs to:

* Mono where appropriate
* 44.1 or 48 kHz
* Floating-point WAV or equivalent internal representation
* No clipping
* Consistent channel handling

Preserve the original file unchanged.

## 7.5 Audio normalization

Normalization must be used only for analysis convenience.

The application must not alter pitch or timing during normalization.

Retain original gain information for display.

---

# 8. Source Separation Requirements

## 8.1 Default separation

Use a local source-separation model to extract at least:

* Vocals
* Instrumental accompaniment

Preferred implementation:

* Demucs or a compatible high-quality local model

The separation layer must be abstracted so models can be changed later.

## 8.2 Caching

Stem separation is expensive and must be cached.

Cache keys should include:

* Source-file hash
* Model name
* Model version
* Separation settings
* Output sample rate

A previously separated song reference should never be separated again unless the source or settings change.

## 8.3 Quality handling

The application must expose a reference-vocal confidence indicator.

Potential issues to detect or flag:

* Backing-vocal contamination
* Multiple simultaneous singers
* Instrument bleed
* Heavy reverb
* Vocal doubling
* Low vocal prominence
* Separation artifacts

## 8.4 Manual reference-region controls

The user must be able to mark regions as:

* Valid lead vocal
* Backing vocal
* Instrumental
* Unreliable
* Excluded from scoring

---

# 9. Pitch Detection Requirements

## 9.1 Pitch-tracking engine

Implement a pluggable pitch-detection interface.

Recommended engines:

* TorchCREPE 0.0.24 full model as the only production tracker
* Viterbi temporal decoding and explicit periodicity/silence gating

The initial product does not expose tracker choice. If the pinned TorchCREPE
dependency is unavailable, analysis stops visibly instead of substituting a
lower-quality tracker.

## 9.2 Expected vocal range

Default analysis range:

* C2 through C7

Allow user override.

## 9.3 Output per frame

For each time frame, store:

* Timestamp
* Estimated fundamental frequency
* MIDI pitch
* Cents relative to nearest equal-tempered note
* Voicing probability
* Pitch confidence
* RMS or loudness
* Algorithm identifier

## 9.4 Frame rate

Target pitch analysis resolution:

* Approximately 5–15 milliseconds per hop

The frame rate should be configurable.

## 9.5 Pitch smoothing

Provide at least two contour representations:

* Raw tracker output
* Smoothed musical contour

Smoothing must preserve:

* Genuine vibrato
* Fast note transitions
* Scoops
* Portamento

It must reduce:

* Octave jumps
* One-frame glitches
* Unvoiced noise
* Harmonic tracking errors

## 9.6 Octave-error correction

Use temporal continuity, harmonic evidence, confidence, and expected vocal range to identify likely octave errors.

Do not silently destroy the raw estimate. Store corrected and uncorrected contours.

## 9.7 Unvoiced handling

Frames with insufficient voicing confidence must not contribute to pitch-accuracy scoring.

Consonants, breaths, and silence should be represented separately from missed notes.

---

# 10. Note Segmentation Requirements

## 10.1 Automatic segmentation

Convert pitch contours into note candidates using:

* Pitch stability
* Pitch-change boundaries
* Energy envelope
* Onset strength
* Voicing transitions
* Minimum note duration
* Musical context

## 10.2 Note states

Each detected note should include:

* Attack region
* Stable region
* Release region
* Optional transition region

Only the stable region should receive full intonation weight.

## 10.3 Ornament handling

The system should identify likely:

* Scoops
* Slides
* Grace notes
* Passing tones
* Vibrato
* Pitch falls
* Spoken or semi-spoken sections

These should be visually represented and optionally excluded from discrete note scoring.

## 10.4 Editable segmentation

The baseline editor must allow the user to:

* Drag note start and end times
* Move notes vertically
* Quantize to semitones
* Preserve microtonal offsets
* Split notes
* Merge notes
* Delete notes
* Add notes
* Mark ornamental notes
* Mark unscored regions
* Group notes into phrases

---

# 11. Alignment Requirements

## 11.1 Global synchronization

Estimate the initial offset between microphone and reference audio using one or more of:

* Cross-correlation of leaked reference audio
* Chroma correlation
* Spectral-feature correlation
* Onset-envelope correlation
* User-provided sync marker

## 11.2 Constant timeline alignment

The system/reference stream is a recording of the same source playback as the
baseline. Align it with one global timestamp offset, then advance both timelines
one-to-one through their shared span. Estimate microphone-device latency as a
second constant offset. Do not time-warp early or late singing, held notes, missed
notes, repeated notes, or partial recordings; those are performance evidence.

## 11.4 Alignment transparency

The user must be able to view:

* Global offset
* Regions with low alignment confidence
* Manual alignment anchors

## 11.5 Manual anchors

Allow the user to add synchronized marker pairs between the reference and performance.

Examples:

* First lyric entrance
* Chorus start
* Sustained high note
* Final phrase

Manual anchors should constrain or replace automatic alignment locally.

---

# 12. Transposition Detection

## 12.1 Global transposition

Estimate the semitone shift that minimizes robust pitch error across voiced, aligned frames.

Search at least:

* −12 through +12 semitones

Optionally support a wider range.

## 12.2 Octave detection

Report octave displacement separately from key transposition.

Example:

* Key shift: −2 semitones
* Octave displacement: −12 semitones
* Total absolute shift: −14 semitones

## 12.3 Confidence

Return:

* Best transposition
* Second-best transposition
* Confidence margin
* Percentage of frames supporting the estimate

## 12.4 Manual override

The user must be able to lock the project or take to a selected transposition.

---

# 13. Scoring Requirements

Avoid presenting a single unexplained overall score as the primary result.

Provide a score breakdown.

## 13.1 Pitch metrics

Calculate:

* Median signed cents error
* Median absolute cents error
* Mean absolute cents error
* 90th-percentile absolute error
* Percentage within ±15 cents
* Percentage within ±25 cents
* Percentage within ±35 cents
* Percentage within ±50 cents
* Percentage within ±100 cents
* Sharp-frame percentage
* Flat-frame percentage
* Persistent pitch bias
* Note-center accuracy
* Interval accuracy
* Octave-error count

## 13.2 Timing metrics

Calculate:

* Median onset timing error
* Median release timing error
* Note-duration error
* Phrase-entry timing error
* Phrase-ending timing error
* Early-entry rate
* Late-entry rate
* Tempo drift
* Alignment deviation

## 13.3 Stability metrics

Calculate:

* Pitch standard deviation during stable note regions
* Drift across sustained notes
* Initial-to-stable pitch settling
* End-of-note pitch fall or rise
* Unintended pitch wobble
* Consistency across repeated occurrences of the same note or phrase

## 13.4 Vibrato metrics

Where reliable, estimate:

* Vibrato rate in hertz
* Vibrato depth in cents
* Vibrato onset delay
* Vibrato regularity
* Similarity to reference vibrato

Do not treat absence of vibrato as automatically incorrect unless the user enables performance-imitation scoring.

## 13.5 Phrase metrics

For each phrase, calculate:

* Pitch accuracy
* Timing accuracy
* Stability
* Melody-contour accuracy
* Reference similarity
* Confidence
* Improvement relative to prior takes

## 13.6 Composite scores

Optional composite scores may include:

* Note accuracy
* Timing
* Stability
* Performance similarity
* Overall consistency

Weights must be visible and configurable.

The application must explain how each composite score is calculated.

---

# 14. Feedback Requirements

## 14.1 Actionable feedback

Feedback should be phrased in musically useful language.

Examples:

* “You were consistently about 22 cents flat in this phrase.”
* “The note settled accurately, but the attack began nearly a semitone low.”
* “You entered the chorus 140 ms early.”
* “The melody matched after transposing the reference down five semitones.”
* “Your sustained pitch became less stable near the end of the note.”
* “This interval was consistently smaller than the reference.”
* “This take improved on pitch accuracy but was less rhythmically consistent.”

## 14.2 Confidence-aware feedback

Do not state uncertain results as fact.

Use labels such as:

* High confidence
* Moderate confidence
* Low confidence
* Reference contamination detected
* Alignment uncertain
* Multiple vocal sources detected

## 14.3 Region prioritization

Automatically identify the most useful practice targets.

Rank regions based on:

* Magnitude of error
* Repetition of error
* Confidence
* Musical importance
* Difference from prior takes
* User-selected goals

## 14.4 Positive feedback

Highlight successful regions as well as mistakes.

Examples:

* Most accurate phrase
* Most improved phrase
* Best sustained note
* Most consistent interval
* Strongest rhythmic section

---

# 15. User Interface Requirements

## 15.1 Main screens

The application should include:

1. Song library
2. Song-project overview
3. Import wizard
4. Track-assignment screen
5. Processing-status screen
6. Baseline editor
7. Take-analysis screen
8. Take-comparison screen
9. Practice-region screen
10. Settings and model management

## 15.2 Song library

Each song card should show:

* Song title
* Artist
* Number of takes
* Baseline status
* Last practiced date
* Best recent metrics
* Detected preferred key
* Processing status

The user should be able to create a song manually without Spotify integration.

Optional metadata fields:

* Spotify URL
* Album
* Original key
* User’s preferred key
* Notes
* Tags

## 15.3 Import wizard

The wizard should:

1. Accept drag-and-drop files.
2. Inspect streams.
3. Let the user audition tracks.
4. Suggest microphone and reference tracks.
5. Let the user choose the song section.
6. Display estimated processing steps.
7. Start processing.
8. Surface recoverable errors clearly.

## 15.4 Baseline editor

The baseline editor should contain:

* Reference waveform
* Isolated-vocal waveform
* Spectrogram
* Raw pitch contour
* Smoothed pitch contour
* Simplified note track
* Phrase regions
* Confidence overlay
* Playback cursor
* Zoom controls
* Loop controls
* Alignment markers
* Transposition controls

The user must be able to solo or mute:

* Original mix
* Isolated reference vocal
* Instrumental stem
* User microphone
* Pitch sonification or guide tone

## 15.5 Analysis view

The primary analysis view should show:

* Reference pitch contour
* User pitch contour
* Note blocks
* Cents-error heatmap or overlay
* Alignment confidence
* Phrase boundaries
* Playback cursor
* Selected scoring mode

Selecting a note or phrase should display detailed metrics.

## 15.6 Comparison view

Allow comparison of:

* Two selected takes
* Current take versus personal best
* Current take versus rolling average
* Phrase-level history
* Metric trends over time

## 15.7 Playback

Playback must support:

* Reference only
* User only
* Both together
* Instrumental plus user
* Isolated vocal plus user
* Adjustable reference/user balance
* Loop selection
* Slow playback without pitch change
* Optional pitch-shifted reference matching the user’s key

---

# 16. Practice Tools

## 16.1 Looping

The user must be able to loop:

* A note
* A phrase
* A selected region
* A failed region suggested by the application

## 16.2 Guide playback

Support optional generated guide playback:

* Sine-wave note guide
* Piano-like note guide
* Simplified melody playback
* Count-in
* Reference vocal shifted into the user’s preferred key

## 16.3 Practice queue

Allow the user to save difficult phrases to a practice queue.

Each item should include:

* Song
* Time range
* Problem description
* Target metric
* Recent performance
* Improvement history

---

# 17. Data Model

## 17.1 Song project

```json
{
  "id": "uuid",
  "title": "Vienna",
  "artist": "Billy Joel",
  "spotify_url": "optional",
  "original_key": "optional",
  "preferred_transposition": -3,
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "tags": [],
  "notes": ""
}
```

## 17.2 Source recording

```json
{
  "id": "uuid",
  "song_id": "uuid",
  "original_path": "path",
  "file_hash": "sha256",
  "duration_seconds": 0,
  "streams": [],
  "reference_stream_id": "optional",
  "microphone_stream_id": "optional",
  "imported_at": "timestamp"
}
```

## 17.3 Baseline

```json
{
  "id": "uuid",
  "song_id": "uuid",
  "type": "original_contour | simplified_notes | midi | manual | prior_take",
  "source_recording_id": "optional",
  "model_versions": {},
  "transposition": 0,
  "start_offset": 0,
  "version": 1,
  "is_active": true,
  "created_at": "timestamp"
}
```

## 17.4 Note event

```json
{
  "id": "uuid",
  "baseline_id": "uuid",
  "phrase_id": "uuid",
  "start_seconds": 0,
  "end_seconds": 0,
  "midi_pitch": 60,
  "cents_offset": 0,
  "confidence": 0.95,
  "ornamental": false,
  "scored": true,
  "source": "automatic | manual | midi"
}
```

## 17.5 Take

```json
{
  "id": "uuid",
  "song_id": "uuid",
  "source_recording_id": "uuid",
  "baseline_id": "uuid",
  "detected_transposition": -5,
  "detected_octave_shift": 0,
  "created_at": "timestamp",
  "notes": ""
}
```

## 17.6 Analysis result

Store:

* Per-frame features
* Per-note metrics
* Per-phrase metrics
* Global metrics
* Constant alignment offsets and shared-span indices
* Confidence values
* Algorithm versions
* User overrides
* Processing logs

Use a binary or columnar format for dense frame-level arrays, such as NumPy, Parquet, or Zarr, rather than storing large arrays directly in JSON.

---

# 18. Technical Architecture

## 18.1 General architecture

Use a local-first modular architecture.

Recommended structure:

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
│   ├── visualization/
│   └── shared_models/
├── tests/
├── fixtures/
├── scripts/
└── docs/
```

## 18.2 Recommended stack

### Analysis backend

* Python 3.12+
* NumPy
* SciPy
* librosa
* PyTorch
* TorchCREPE 0.0.24
* Demucs
* FFmpeg and FFprobe
* SoundFile
* Pydantic
* SQLAlchemy or equivalent
* SQLite for project metadata
* FastAPI for local API boundaries

### Frontend

* TypeScript
* React
* Vite
* Canvas or WebGL waveform and pitch rendering
* A robust audio waveform library where useful
* State management kept minimal and explicit

### Desktop packaging

Preferred:

* Tauri or Electron wrapper around the local application

The analysis backend may run as a managed local sidecar process.

The application must remain functional without internet access after models and dependencies are installed.

## 18.3 Processing jobs

Long-running operations must run as cancellable background jobs:

* Audio extraction
* Source separation
* Pitch tracking
* Feature extraction
* Alignment
* Baseline generation
* Metric calculation

The user interface should show:

* Current stage
* Progress
* Cancel control
* Errors
* Retry control
* Cached stages

## 18.4 Reproducibility

Every analysis result must store:

* Application version
* Model names
* Model versions
* Parameter values
* Source-file hashes
* Baseline version
* Manual overrides

Changing a baseline or major analysis setting should create a new analysis version rather than silently overwriting prior results.

---

# 19. Performance Requirements

## 19.1 Responsiveness

The interface must remain responsive during all analysis tasks.

## 19.2 Caching

Cache all expensive deterministic operations.

At minimum:

* Extracted audio tracks
* Separated stems
* Pitch contours
* Chroma features
* Onset features
* Baseline notes
* Alignment results
* Render-ready waveform summaries

## 19.3 Incremental recomputation

Editing one baseline note should not rerun source separation or pitch extraction.

Changing the scoring tolerance should not rerun audio analysis.

Changing alignment anchors should rerun only alignment and downstream metrics.

## 19.4 Hardware acceleration

Use GPU acceleration where available for:

* Source separation
* Neural pitch tracking

Provide a CPU fallback.

The application should detect available hardware automatically.

## 19.5 Storage management

Provide:

* Cache-size display
* Per-project storage display
* Clear-cache controls
* Rebuild-cache controls
* Protection for original imported recordings

---

# 20. Reliability and Error Handling

The application must gracefully handle:

* Missing FFmpeg
* Unsupported codecs
* Corrupt recordings
* Silent microphone track
* Missing system-audio track
* Clipped microphone audio
* Heavy reference bleed into the microphone
* Very low vocal level
* Multiple singers
* Source-separation failure
* Pitch-tracking failure
* No reliable voiced regions
* Alignment failure
* Partial-song mismatch
* Different song version
* Live versus studio version mismatch
* User singing a different verse or repeated chorus
* Song sections with no lead vocal

Errors should include a plain-language explanation and a suggested resolution.

---

# 21. Privacy Requirements

The application must be local-first.

By default:

* Audio files remain on the user’s device.
* No audio is uploaded.
* No account is required.
* No telemetry contains audio or musical content.
* No copyrighted reference audio is redistributed.
* Exported reports must not embed reference audio unless the user explicitly chooses to include local excerpts for personal use.
* Project deletion must remove generated stems and derived files when requested.

Any future cloud feature must be opt-in and separately designed.

---

# 22. Export Requirements

Allow export of:

* Analysis summary as JSON
* Per-note metrics as CSV
* Pitch contours as CSV or NumPy
* Baseline notes as MIDI
* Static report as HTML or PDF
* Visualization image
* Practice-region list
* Project archive excluding original audio by default

The user should be able to choose whether a project archive includes:

* Original recording
* Extracted tracks
* Generated stems
* Derived features
* Baselines
* Analysis results

---

# 23. Testing Requirements

## 23.1 Unit tests

Cover:

* Frequency-to-MIDI conversion
* Cents-error calculation
* Transposition detection
* Octave handling
* Frame masking
* Pitch smoothing
* Note segmentation
* Note scoring
* Timing metrics
* Alignment constraints
* Cache invalidation
* Data migrations

## 23.2 Integration tests

Use synthetic and recorded fixtures to test:

* Perfect unison
* Fixed sharp bias
* Fixed flat bias
* Key transposition
* Octave displacement
* Vibrato
* Slides
* Missed notes
* Extra notes
* Early entrances
* Late entrances
* Tempo drift
* Partial-song imports
* Silent sections
* Mixed vocal contamination

## 23.3 Synthetic test generation

Generate known vocal-like signals with:

* Fundamental frequency
* Harmonics
* Vibrato
* Noise
* Formant-like filtering
* Controlled pitch transitions

Expected pitch and timing must be known exactly.

## 23.4 Golden-project tests

Maintain several small project fixtures with expected:

* Stream assignments
* Pitch tracks
* Alignments
* Note events
* Metrics

## 23.5 UI tests

Test:

* File import
* Track preview
* Baseline editing
* Undo and redo
* Loop playback
* Take comparison
* Error recovery
* Cache clearing

---

# 24. Acceptance Criteria

## 24.1 Import

* The user can import an OBS MKV recording with separate microphone and system-audio tracks.
* The application lists and previews all audio streams.
* The user can assign track roles.
* The application extracts working audio without altering the original.

## 24.2 Baseline creation

* The application can isolate a reference vocal from the system-audio track.
* The application can produce a continuous reference pitch contour.
* The application can produce a simplified editable note track.
* The baseline can be saved and reused.

## 24.3 Take analysis

* The application can extract the user’s vocal pitch.
* The application can align a partial or complete take to the reference.
* The application can detect a consistent semitone transposition.
* The application can distinguish octave displacement.
* The application reports pitch and timing metrics.
* Unvoiced regions are excluded from pitch scoring.

## 24.4 Visualization

* The user can view reference and user pitch together.
* The user can inspect note-level cents errors.
* The user can click a phrase and loop it.
* The user can see uncertainty and excluded regions.
* The user can switch among absolute, transposed, interval-only, note, and performance modes.

## 24.5 Repeated practice

* A second take can reuse the saved baseline.
* The user can compare two takes.
* The application identifies improved and worsened phrases.
* Expensive reference processing is not repeated.

## 24.6 Editing

* The user can correct baseline notes.
* The user can add manual alignment anchors.
* Metrics update after edits without rerunning unrelated processing.
* Edits support undo and redo.

---

# 25. Delivery Phases

## Phase 1: Analysis pipeline and command-line prototype

Implement:

* FFmpeg stream inspection and extraction
* Manual track assignment
* Reference-vocal separation
* Pitch tracking
* Basic alignment
* Transposition detection
* Pitch-error metrics
* Static pitch-contour plot
* Cached project directory
* Automated tests

CLI example:

```bash
vocallab analyze \
  --input vienna_take_01.mkv \
  --mic-stream 2 \
  --reference-stream 1 \
  --output projects/vienna
```

## Phase 2: Local graphical application

Implement:

* Song library
* Import wizard
* Stream audition
* Processing jobs
* Pitch visualization
* Playback
* Basic note segmentation
* Reusable baselines
* Take history

## Phase 3: Baseline editor

Implement:

* Piano-roll editing
* Phrase regions
* Excluded regions
* Alignment anchors
* Simplified melody generation
* MIDI import and export
* Undo and redo

## Phase 4: Advanced scoring

Implement:

* Note attack, stable, and release scoring
* Timing metrics
* Stability metrics
* Vibrato metrics
* Interval-only scoring
* Performance-similarity scoring
* Confidence-aware feedback

## Phase 5: Practice experience

Implement:

* Suggested difficult regions
* Practice queue
* Phrase looping
* Slow playback
* Transposed guide playback
* Trend analysis
* Personal-best composite

## Phase 6: Packaging and polish

Implement:

* Desktop installer
* Model download and management
* Hardware detection
* Cache controls
* Crash recovery
* Project backup and export
* Complete onboarding
* OBS setup guide

---

# 26. Initial Implementation Priorities

The agent should prioritize correctness and inspectability over premature scoring complexity.

The first complete vertical slice should be:

1. Import one OBS MKV file.
2. Extract microphone and reference tracks.
3. Separate the reference vocal.
4. Track pitch for the user and reference.
5. Estimate synchronization and transposition.
6. Display both contours.
7. Calculate cents error.
8. Save the reference analysis.
9. Import a second take.
10. Compare both takes against the same reference.

The first test song should use a relatively exposed solo vocal with a clear melody, such as “Vienna.”

Process only one verse or chorus initially.

---

# 27. Engineering Principles

The implementation should follow these principles:

* Keep original audio immutable.
* Cache expensive computations.
* Store every analysis parameter.
* Make uncertainty visible.
* Never hide manual corrections.
* Preserve raw model outputs alongside corrected outputs.
* Keep algorithms modular and replaceable.
* Separate signal extraction from scoring.
* Separate factual measurements from interpretive feedback.
* Avoid making artistic choices appear objectively wrong.
* Make repeated use dramatically faster than first-time setup.
* Prefer graceful degradation over total failure.
* Build the internal pipeline as a reusable library rather than embedding all logic in the interface.

---

# 28. Agent Instructions

Implement this project iteratively, beginning with the Phase 1 vertical slice.

Before writing substantial UI code:

1. Create the project structure.
2. Define typed data models.
3. Implement file hashing and artifact caching.
4. Implement FFprobe stream inspection.
5. Implement deterministic audio extraction.
6. Implement pitch-engine interfaces.
7. Implement alignment and transposition tests using synthetic signals.
8. Produce a static end-to-end analysis report.
9. Validate the pipeline on one real OBS recording.
10. Only then build the interactive application.

For every phase:

* Add automated tests.
* Add structured logging.
* Document setup and execution.
* Record model and dependency versions.
* Avoid hard-coding song-specific logic.
* Expose intermediate artifacts for debugging.
* Keep all audio processing local.
* Commit working vertical slices rather than large unvalidated batches.

The finished application should make a sophisticated analysis pipeline feel simple: import a recording, confirm the tracks, review the baseline once, and receive useful feedback on every future take.

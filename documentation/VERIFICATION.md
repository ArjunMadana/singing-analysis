# Verification

Last updated: 2026-07-26

## Backend and integrated API

Executed:

```powershell
python -m compileall -q src tests
python -m pytest
```

Result: **39 tests passed**.

Coverage includes:

- frequency/MIDI/cents conversion and pitch voicing;
- support-first transposition, reliability gating, multimodal evidence rejection,
  octave decomposition, and all four scoring modes;
- global system synchronization and constrained alignment;
- transposition-invariant microphone-latency estimation;
- a full synthetic one-second delayed-microphone analysis and loop mapping;
- stream inspection/extraction and assignment validation;
- cache keys and downstream invalidation;
- SQLite migration and connection lifetime;
- job progress and completion;
- project list/create/read/confirmed-delete;
- safe audio artifact allow-listing;
- raw media inspection, stream preview, and local import;
- waveform and aligned pitch retrieval;
- two-take baseline reuse and comparison contours;
- baseline version creation and activation;
- safe Demucs automatic fallback and explicit-installation enforcement;
- calibrated pitch/energy latency selection and confidence;
- persisted, bounded per-take playback offset;
- grouped practice-target construction and minimum/maximum loop rules;
- full-mix octave/harmonic scoring safeguards;
- static HTML report generation and alignment-aware looping.
- manual scoring API behavior and proof that it does not rewrite stored analysis;
- mode-compatible take comparisons.
- unequal-length partial-overlap alignment and playback-mapping safety evaluation.

The integrated API workflow generates two noncopyrighted MKV takes, detects the
known pitch relationship, reuses the active baseline, creates baseline version 2,
reactivates version 1, retrieves display artifacts, and compares the takes.

## Frontend

Executed:

```powershell
npm.cmd --prefix apps/web test
npm.cmd --prefix apps/web run lint
```

`npm test` performs a production Vinext/Vite build and then runs the frontend
state tests. Result: **27 tests passed**, build passed, and ESLint passed.

The tests cover the earlier state behavior plus shared scheduled starts, source
readiness, constant and nonlinear mapping, 20 loop epochs without accumulated
drift, failed-source behavior, mix/gain behavior during playback, pause/resume node
recreation, rapid target switching, click-to-seek, click-sized loop rejection,
intentional loop creation, loop-edge adjustment, project-scoped import drafts, and
clearing an inspected recording to choose another file. It also proves that late
loads from a disposed transport cannot overwrite active readiness and that Play at
the canonical endpoint rewinds and schedules real source nodes. It also proves that
the scheduler ignores nonlinear mapping data, schedules continuous 1.0x source
audio, and maps waveforms through the same constant offsets. No variable-rate
playback mode remains.

The pitch-axis test also verifies scientific pitch labels (`C4`, `C♯4`, `A4`) and
adaptive tick density for a wide visible range.

Before removing local warping, both local Test takes were inspected directly:

- source hashes, microphone/reference WAV hashes, alignment hashes, and user-pitch
  hashes differ;
- the tracks contain 7,537 versus 7,235 voiced frames, have different median MIDI
  values, and have only 0.18 correlation after timestamp alignment;
- their original-pitch median frame errors are 1097.7 and 1097.1 cents. The close
  aggregate values are real outputs dominated by a roughly one-octave displacement,
  not reused analysis;
- the new take's path has a +1.06-second system offset, 0.84x-1.24x local rates,
  and 38.2% non-pitch-safe half-second windows despite returning to the same net
  offset. Constant correction now uses +1.06 seconds plus microphone latency while
  keeping both recordings at 1.0x.

After removing local warping and reanalyzing both Test takes:

- both analyses report the `constant-offset` profile;
- take 1 remains 1097.7 cents median across 1,445 aligned voiced frames;
- take 2 is 1089.4 cents across 1,463 aligned voiced frames;
- within-25-cent rates are 7.958% and 7.587%, now displayed as 8.0% and 7.6%
  instead of both being rounded to 8%;
- raw user-track medians differ by 69.8 cents, proving the pitch evidence changed,
  while incompatible 0/-12-semitone clusters explain why the absolute-error median
  remains insensitive.

## Unequal-length Vienna take

Vienna take 1 covers approximately 45 seconds, while take 2 is 102.25 seconds and
starts several seconds earlier. Reproducing take 2 against the take-1 baseline
isolated the failure:

- global synchronization correctly found +3.26 seconds;
- the former constrained-DTW implementation incorrectly forced the 45-second
  reference endpoint to the 102-second take endpoint;
- 73.4% of pointwise mapping intervals fell outside 0.8x-1.25x;
- observed local rates ranged from 0x to 90.5x, explaining the severely mangled
  audio.

After the constant-offset correction, the same inputs map canonical
0.02-44.98 seconds to source 3.28-48.24 seconds one-to-one. The obsolete local
path is no longer analysis evidence or a playback option.

The existing Vienna take 2 was also rebuilt as new baseline v10 with Demucs
4.1.0/htdemucs/CUDA; versions 1-9 remain available. The resulting full-length
mapping covers canonical 0.02-101.94 seconds one-to-one at 1.0x.

## Private take metadata verification

The existing ignored private project was reanalyzed with cached extraction,
reference, and pitch artifacts. The recording itself was not modified.

Executed:

```powershell
python -m vocallab analyze `
  --project projects\1b27a59bfae04750aac558d74e9f542d `
  --take a1ba9ffa-7a03-46d6-8061-20174a03b089 `
  --separator demucs
```

Observed:

- baseline v7 reused with active provenance
  `demucs-4.1.0-htdemucs-cuda`, confidence 0.8, non-provisional;
- microphone extraction, reference extraction, user pitch, and baseline caches hit;
- pitch latency candidate 0.310 s at 2.4%;
- energy latency candidate 0.400 s at 75.6%;
- selected consensus 0.398 s at 55.0%;
- calibrated combined confidence 81.2%;
- matched alignment coverage 50%.

Both automated candidates disagree with the user's roughly one-second listening
estimate. The UI therefore exposes raw, constant, and full correction modes plus a
temporary -2 to +2 second override. Approximately +0.60 s is the value to test
next, but it was not listened to or saved in this session.

The previous -6-semitone detection had 0% direct support and was an arithmetic
compromise between incompatible pitch clusters. The new detector produces:

- strongest shift 0 st at 18.7% support;
- runner-up -12 st;
- support margin 4.5 percentage points;
- reliability `false`, so original pitch is the default and note discrepancies are
  withheld pending a manual key.

The four Vienna views report:

- original-pitch median absolute difference 1163.6 cents;
- octave-invariant median absolute error 78.6 cents and median octave displacement
  -1.0 octave;
- interval median absolute error 70.1 cents;
- contour-direction agreement 61.5% across 403 transitions.

Applying -12 st through the scoring API returned a temporary key-adjusted view and
14 practice targets without changing the stored take analysis or any upstream
artifacts. Its median signed residual was +44.4 cents, but median *absolute*
residual remained 1005.8 cents because the evidence still contains incompatible
octave/harmonic clusters. Both values are retained rather than substituting one for
the other.

## Bounded application launch

The API and UI were started as child processes on isolated local ports, polled,
and terminated in the same bounded verification command. Result:

```text
{'api': 200, 'web': 200}
```

This proves both documented services start and answer HTTP. A controllable browser
was unavailable in the session, so no claim is made that visual clicking or audio
playback was manually exercised in a browser.

## Packaging and source checks

Executed:

```powershell
python -m pip wheel --no-cache-dir --no-deps --no-build-isolation --wheel-dir .verification\wheels .
git -c safe.directory='C:/Users/arjun/OneDrive/Documents/_Development/singing-analysis' diff --check
```

The `vocallab-0.1.0` wheel built successfully, the Python 100-character line
audit passed, and `git diff --check` reported no whitespace errors.

## One-second offset result

The large-offset fixture uses a five-note synthetic melody with exactly one second
of leading microphone silence. VocalLab:

- estimated the constant microphone latency within 80 ms of one second;
- removed that latency before pitch comparison;
- kept median pitch error below 15 cents for the matching melody;
- mapped a baseline loop beginning near 0.1 seconds to the microphone timeline near
  1.1 seconds.

There is no timing score yet, so verification proves latency-corrected alignment
and pitch scoring—not advanced musical timing metrics.

## Demucs

- Installed locally: **yes, 4.1.0**
- Configured optional package: `demucs==4.1.0`
- Maintained source: `adefossez/demucs`
- Model: `htdemucs`
- Device: explicit runtime choice, CUDA when available, otherwise CPU
- Current Vienna baseline: `demucs-4.1.0-htdemucs-cuda`, `htdemucs`, confidence 0.8
- Download behavior: auto mode never invokes Demucs; model acquisition can occur
  only after the user explicitly installs the models extra and selects Demucs

The package/version/source check used the official
[Demucs PyPI page](https://pypi.org/project/demucs/) and
[adefossez/demucs repository](https://github.com/adefossez/demucs).

## TorchCREPE

- Installed locally: **yes, 0.0.24**
- Configured model: full
- Decoder: whole-track Viterbi
- Device: CUDA on the current host, otherwise explicit CPU
- Silence handling: centered 1,024-sample RMS gate at -60 dBFS
- Periodicity handling: median-3 filter and 0.21 contour threshold
- Silent fallback: none

The centered RMS gate replaces only TorchCREPE's built-in silence helper. That
helper lazily imports librosa and caused a multi-minute Numba cache scan in this
Windows/OneDrive environment. Neural inference, model periodicity, pitch-bin
conversion, and Viterbi decoding remain TorchCREPE-based.

The Test project was reanalyzed on the production path. Baseline v3's preserved
Demucs vocal stem was re-pitched and activated as immutable baseline v4; separation
was not rerun. Take 1 then reported a -12-semitone candidate with 43.8% support and
take 2 reported 40.5%. Their original-pitch medians are 1185.2 and 1197.3 cents,
respectively. Both detections remain unreliable rather than being promoted to a
confident key claim.

Vienna was migrated the same way from baseline v10 to v11. Take 1 reports a
1262.3-cent original-pitch median and 34.0% support for -12 semitones; take 2
reports 1186.4 cents and 43.4%. Both remain below the reliability gate. All source
recordings and baseline versions 1-10 remain unchanged.

The retained autocorrelation cache allowed a same-audio tracker comparison. Across
the matched reference and microphone artifacts, the two trackers agree within 50
cents after octave wrapping on 92.0%-97.0% of mutually voiced frames, but direct
absolute-octave agreement is only 0.0%-8.9%. Median old-minus-new displacement is
about +12 semitones for the reference and +24 for the microphone. This is strong
evidence that the former method tracked harmonics; it is not a labeled-ground-truth
accuracy percentage for TorchCREPE.

## Limitations of verification

- The private recording was present in ignored project storage and was used only
  for local metadata/reanalysis checks; no audio was copied into source control.
- Browser-control infrastructure reported no available browser. No claim is made
  for visually exercising the new scoring controls, seeking/loop gestures,
  listening, audio-device behavior, 20 audible loops, or manual calibration.
- Ruff passes on every Python file changed for TorchCREPE. Full-repository Ruff and
  mypy still report pre-existing cleanup work outside this change; neither is
  claimed as globally clean.

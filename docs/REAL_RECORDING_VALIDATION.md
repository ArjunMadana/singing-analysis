# Real OBS recording validation

Status: private take reanalyzed; browser listening checks still open

## 2026-07-26 validation record

- OS: Windows; exact build not captured
- Browser/version used for the user's first validation: not captured
- Browser automation for this engineering session: unavailable (no attached browser)
- Audio output device: not captured
- Recording: private OBS multitrack take in ignored project storage, approximately
  45 seconds
- Reference mode: `reference-mix-fallback-v1`
- Demucs: not installed
- System-reference offset: 0.000 s
- Old microphone latency: 0.390 s at 9.7% latency confidence
- Old combined alignment confidence: 100% (not calibrated)
- New pitch latency candidate: 0.390 s at 9.7%
- New energy latency candidate: 0.400 s at 75.6%
- New selected consensus: 0.399 s at 47.2%
- New calibrated alignment confidence: 79.3%
- Matched coverage: 50%
- Effective mapped offset at beginning/middle/end: approximately 0.42 s
- User's audible estimate from the first validation: roughly 1 second
- Manual diagnostic offset likely worth testing: approximately +0.60 s
- Manual offset saved: no
- Raw discrepancies: 20
- Grouped practice targets: 19
- Automatic practice-loop duration: 2.5-3.95 s
- Provisional full-mix targets: 19
- Octave/harmonic regions downgraded to unreliable reference: 5

Interpretation: both independent automated candidates support approximately 0.40
seconds and the saved path does not indicate drift. This conflicts with the
listening report, so the root cause cannot be declared solved by estimator changes.
The shared Web Audio transport and raw/constant/full modes remove the old
independent-clock defect. The next attached-browser check should compare full
alignment at +0.00 s and approximately +0.60 s manual override before saving any
calibration.

Not manually verified in this session:

- User-only, Reference-only, and Both playback
- seek/pause/resume synchronization on the actual audio device
- 20 audible loop iterations
- beginning/middle/end phrase identity
- the approximately +0.60 s calibration
- Demucs playback/reference A/B

Never commit the recording, extracted audio, stems, pitch artifacts, reports, or
screenshots containing private/copyrighted material. `local-fixtures/` is ignored by
Git.

## Recording checklist

- OBS recording uses MKV where practical.
- Microphone and Spotify/system audio are assigned to different audio tracks.
- Headphones prevent acoustic playback bleed where possible.
- Sample rate is 48 kHz.
- The test contains a short verse or chorus with several distinct note changes.
- Keep roughly one second of the observed microphone delay; do not manually shift
  the recording before import.

## Import and analysis

1. For another recording, place it under `local-fixtures/`, for example:

   ```text
   local-fixtures/obs-practice-take-01.mkv
   ```

2. Launch the API and UI from the repository root:

   ```powershell
   python -m vocallab serve --library projects
   npm.cmd --prefix apps/web run dev
   ```

3. Open `http://localhost:3000`, create the song project, and choose **Import take**.
4. Select the fixture, audition every detected stream, and override suggested roles
   so exactly one stream is **Microphone** and one is **Reference/system**.
5. Run analysis. Record the displayed:

   - system-audio offset;
   - microphone device latency;
   - alignment confidence;
   - detected transposition and octave displacement;
   - fallback/model warning;
   - extraction, pitch, and baseline cache events.

6. Click at least three discrepancies near the beginning, middle, and end. Confirm
   that each loop plays the intended microphone phrase despite the delay.
7. Import a second take and confirm baseline reuse plus extraction/pitch provenance.

## Constant-delay interpretation

VocalLab removes one constant microphone latency after aligning system audio to the
saved reference. The UI displays that latency separately. If beginning and ending
loops both remain synchronized, the delay is consistent enough for the current
model. If later loops drift while early loops are correct, record that as likely
clock drift or local alignment failure; separate microphone-clock drift estimation
is not yet implemented.

Musical timing metrics are not yet implemented. Current validation can confirm that
the constant capture delay is removed before pitch comparison, but must not claim a
verified onset/release timing score.

## Expected diagnostics

- Project-owned imported recording under `projects/<id>/imports/`
- Extract/pitch/separation cache manifests under `artifacts/cache/`
- Alignment path under `artifacts/analysis/<take-id>/alignment.npz`
- Cached display waveform summaries under `artifacts/display/waveform/`
- Static report under `reports/`
- Analysis provenance in the project SQLite database and report

## Common failures

- **No streams:** verify OBS advanced audio properties and track checkboxes.
- **Silent microphone:** select the isolated microphone track, not an unused track.
- **Wrong reference:** audition tracks and choose continuous system/music audio.
- **Large incorrect latency:** ensure the microphone and reference are from the same
  recording version and section.
- **Late-loop drift:** preserve the project and record the start/end mismatch; this
  may require microphone clock-drift estimation.
- **Contaminated pitch:** expected while Demucs is unavailable; do not treat a low-
  confidence full-mix contour as an authoritative melody.

## Observation record

Date:

Recording duration:

Assigned microphone stream:

Assigned reference stream:

Detected system offset:

Detected microphone latency:

Alignment confidence:

Beginning-loop result:

Middle-loop result:

Ending-loop result:

Constant delay or observed drift:

Second-take cache/baseline reuse:

Issues to reproduce with synthetic media:

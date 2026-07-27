# Local API

Last updated: 2026-07-26

The API binds to `127.0.0.1` by default. It accepts browser-selected media into a
library-owned incoming directory, then copies imported recordings into a specific
project. Arbitrary filesystem paths are never accepted as artifact URLs.

Primary endpoints:

- `GET /api/capabilities`
- `GET/POST /api/projects`
- `GET/DELETE /api/projects/{project_id}`
- `POST /api/recordings/inspect`
- `GET /api/recordings/{token}/preview/{stream_index}`
- `GET/POST /api/projects/{project_id}/takes`
- `GET /api/projects/{project_id}/takes/{take_id}`
- `POST /api/projects/{project_id}/takes/{take_id}/analyze`
- `GET/POST /api/jobs/{job_id}` and `/cancel`
- `GET /api/projects/{project_id}/takes/{take_id}/visualization`
- `GET /api/projects/{project_id}/takes/{take_id}/scoring?shift=-6`
- `PUT /api/projects/{project_id}/takes/{take_id}/playback-offset`
- `GET /api/projects/{project_id}/takes/{take_id}/audio/{user|reference}`
- `GET /api/projects/{project_id}/baseline`
- `POST /api/projects/{project_id}/baseline/versions`
- `POST /api/projects/{project_id}/baseline/{baseline_id}/activate`
- `GET /api/projects/{project_id}/compare?first=...&second=...`

Waveforms are cached min/max summaries capped for display. Pitch responses are
decimated aligned points with nullable unvoiced values and per-source confidence.
The visualization response also contains raw discrepancies, grouped practice
targets, canonical/reference/microphone playback mappings, the saved playback
override, calibrated synchronization diagnostics, and original plus shifted
reference pitch contours.

The scoring endpoint recomputes the four scoring views and key-adjusted practice
targets from existing pitch/alignment artifacts. Omitting `shift` returns the gated
detected result; an integer from -12 through +12 applies a temporary manual key.
The endpoint does not mutate the take, baseline, source recording, or expensive
cache artifacts.

`GET /api/capabilities` reports Demucs installation, compatible version, model,
device-selection behavior, download uncertainty, storage information, the exact
installation command, and silent-download policy.

The playback-offset endpoint accepts only -2.0 to +2.0 seconds and stores the value
on that take. It is a playback-only diagnostic and never changes analysis results.

Baseline note boundaries remain exact JSON records. Each baseline version includes
separation provenance and a decimated reference-pitch preview for A/B comparison.

# VocalLab

VocalLab is a local-first application for reviewing a recorded singing take,
looping specific pitch discrepancies, and comparing repeated attempts. Audio and
derived artifacts remain on the local machine.

## Requirements

- Python 3.11 or newer
- Node.js 22 or newer
- FFmpeg and FFprobe on `PATH`
- NumPy, SciPy, FastAPI, and Uvicorn

## Install

```powershell
python -m pip install --no-cache-dir -e .
npm.cmd --prefix apps/web ci --ignore-scripts --no-audit --no-fund
```

## Launch the local application

Use two terminals from the repository root.

Terminal 1:

```powershell
python -m vocallab serve --library projects
```

Terminal 2:

```powershell
npm.cmd --prefix apps/web run dev
```

Open `http://localhost:3000`. The local API listens on
`http://127.0.0.1:8000`. Neither service exposes a public listener by default.

The interface supports:

- project creation, opening, and confirmed deletion;
- local recording selection and FFprobe inspection;
- stream-level metadata, level summaries, audition, and role assignment;
- non-blocking analysis progress and honest cancellation status;
- Canvas waveform, pitch, confidence, and baseline-note visualization;
- shared-clock Web Audio playback with decoded-source readiness, User-only,
  Reference-only, Both, independent gains, and raw/constant/full correction modes;
- synchronization diagnostics and an explicit per-take playback-offset override;
- raw discrepancy measurements plus grouped, alignment-aware musical practice loops;
- zoom, pan, seeking, selection, loop presets/padding, and keyboard shortcuts;
- multiple takes, comparison contours, and confidence-aware changes;
- baseline note edits, undo/redo, version creation, and version rollback;
- Demucs selection during import/reanalysis and reference-version pitch comparison.

## Optional Demucs separation

Demucs is not required. Normal installation uses the explicit contaminated-mix
fallback. To install the reproducible optional model adapter:

```powershell
python -m pip install --no-cache-dir -e ".[models]"
```

VocalLab pins `demucs==4.1.0`, selects `htdemucs`, and records the selected CPU or
CUDA device in provenance. Neural separation is used only when explicitly
requested with `--separator demucs`; automatic mode never silently downloads a
model.

## CLI

The original CLI remains available:

```powershell
vocallab inspect recording.mkv
vocallab create-project --title "Vienna" --artist "Billy Joel" --project-dir projects/vienna
vocallab import-take --project projects/vienna --input recording.mkv --mic-stream 2 --reference-stream 1
vocallab analyze --project projects/vienna --take latest
vocallab report --project projects/vienna --take latest --open
```

## Development verification

```powershell
$env:PYTHONPATH = (Resolve-Path 'src').Path
python -m compileall -q src tests
python -m unittest discover -s tests -v
npm.cmd --prefix apps/web test
npm.cmd --prefix apps/web run lint
```

See [documentation/STATUS.md](documentation/STATUS.md),
[documentation/VERIFICATION.md](documentation/VERIFICATION.md), and
[docs/REAL_RECORDING_VALIDATION.md](docs/REAL_RECORDING_VALIDATION.md).

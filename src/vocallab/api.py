from __future__ import annotations

import json
import uuid
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Literal

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, HttpUrl

from vocallab.errors import VocalLabError
from vocallab.jobs import Job, JobManager
from vocallab.models import TranspositionResult
from vocallab.pipeline import AnalysisConfig, analyze_take
from vocallab.practice import build_practice_targets
from vocallab.scoring import (
    aligned_pitch_evidence,
    build_discrepancies,
    build_scoring_modes,
    discrepancies_as_dicts,
)
from vocallab.separation import demucs_capability
from vocallab.services import LibraryService, compare_analyses
from vocallab.visualization import (
    pitch_visualization,
    transport_mapping,
    waveform_summary,
)


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    artist: str = Field(min_length=1, max_length=200)
    spotify_url: HttpUrl | None = None


class ImportTakeRequest(BaseModel):
    recording_token: str
    microphone_stream: int
    reference_stream: int


class AnalyzeRequest(BaseModel):
    separator: Literal["auto", "demucs", "fallback"] = "auto"
    alignment_profile: Literal["pitch-focused", "performance", "strict"] = "performance"
    refresh_reference: bool = False


class PlaybackOffsetRequest(BaseModel):
    offset_seconds: float = Field(ge=-2.0, le=2.0)


class BaselineVersionRequest(BaseModel):
    take_id: str
    notes: list[dict[str, Any]]


class DeleteProjectRequest(BaseModel):
    confirmation: str


def create_app(library_root: Path | None = None) -> FastAPI:
    root = library_root or Path("projects")
    library = LibraryService(root)
    jobs = JobManager()
    app = FastAPI(title="VocalLab Local API", version="0.2.0")
    app.state.library = library
    app.state.jobs = jobs
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3100",
            "http://127.0.0.1:3100",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(VocalLabError)
    async def vocal_error(_: Request, exc: VocalLabError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/capabilities")
    def capabilities() -> dict[str, Any]:
        return {"demucs": demucs_capability()}

    @app.get("/api/projects")
    def projects() -> list[dict[str, Any]]:
        return library.list_projects()

    @app.post("/api/projects", status_code=201)
    def create_project(request: ProjectCreate) -> dict[str, Any]:
        return library.create_project(
            request.title,
            request.artist,
            str(request.spotify_url) if request.spotify_url else None,
        )

    @app.get("/api/projects/{project_id}")
    def project(project_id: str) -> dict[str, Any]:
        summary = library.project_summary(project_id)
        summary["takes"] = [
            _take_payload(take) for take in library.project(project_id).list_takes()
        ]
        return summary

    @app.delete("/api/projects/{project_id}")
    def delete_project(
        project_id: str, request: DeleteProjectRequest
    ) -> dict[str, bool]:
        library.delete_project(project_id, request.confirmation)
        return {"deleted": True}

    @app.post("/api/recordings/inspect")
    async def inspect_recording(
        request: Request, filename: str = Query(min_length=1, max_length=255)
    ) -> dict[str, Any]:
        suffix = Path(filename).suffix.lower()
        token = uuid.uuid4().hex
        target = library.incoming / f"{token}{suffix}"
        size = 0
        with target.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 8 * 1024 * 1024 * 1024:
                    raise HTTPException(413, "Recording exceeds the 8 GB local upload limit.")
                handle.write(chunk)
        if size == 0:
            target.unlink(missing_ok=True)
            raise HTTPException(400, "The selected recording was empty.")
        return library.register_upload(target, filename)

    @app.get("/api/recordings/{token}/preview/{stream_index}")
    def preview(token: str, stream_index: int) -> FileResponse:
        return FileResponse(library.preview_path(token, stream_index), media_type="audio/wav")

    @app.post("/api/projects/{project_id}/takes", status_code=201)
    def import_take(project_id: str, request: ImportTakeRequest) -> dict[str, str]:
        take_id = library.import_take(
            project_id,
            request.recording_token,
            request.microphone_stream,
            request.reference_stream,
        )
        return {"take_id": take_id}

    @app.get("/api/projects/{project_id}/takes")
    def takes(project_id: str) -> list[dict[str, Any]]:
        return [_take_payload(take) for take in library.project(project_id).list_takes()]

    @app.get("/api/projects/{project_id}/takes/{take_id}")
    def take(project_id: str, take_id: str) -> dict[str, Any]:
        return _take_payload(library.project(project_id).get_take(take_id))

    @app.post("/api/projects/{project_id}/takes/{take_id}/analyze", status_code=202)
    def analyze(
        project_id: str, take_id: str, request: AnalyzeRequest
    ) -> dict[str, str]:
        store = library.project(project_id)
        store.get_take(take_id)
        config = AnalysisConfig(
            separator=request.separator,
            alignment_profile=request.alignment_profile,
            refresh_reference=request.refresh_reference,
        )
        job = jobs.submit(
            project_id,
            take_id,
            lambda progress: analyze_take(store, take_id, config, progress),
        )
        return {"job_id": job.id}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> dict[str, Any]:
        current = jobs.get(job_id)
        if current is None:
            raise HTTPException(404, "Job not found.")
        return _job_payload(current)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str) -> dict[str, Any]:
        cancelled, message = jobs.cancel(job_id)
        return {"cancelled": cancelled, "message": message}

    @app.get("/api/projects/{project_id}/takes/{take_id}/visualization")
    def visualization(project_id: str, take_id: str) -> dict[str, Any]:
        store = library.project(project_id)
        row = store.get_take(take_id)
        analysis = _analysis(row)
        artifacts = {key: Path(value) for key, value in analysis["artifacts"].items()}
        pitch_view = pitch_visualization(
            artifacts["reference_pitch"],
            artifacts["user_pitch"],
            artifacts["alignment"],
            reference_shift_semitones=int(
                analysis.get("scoring", {}).get(
                    "selected_shift",
                    analysis.get("transposition", {}).get("best_shift", 0),
                )
            ),
        )
        mapping = transport_mapping(
            artifacts["reference_pitch"],
            artifacts["user_pitch"],
            artifacts["alignment"],
        )
        baseline_row = store.get_baseline(analysis["baseline_id"])
        notes = [
            _note_event(item)
            for item in json.loads(baseline_row["artifact_json"])["notes"]
        ]
        discrepancies = _map_discrepancy_loops(
            analysis.get("discrepancies", []),
            artifacts["reference_pitch"],
            artifacts["user_pitch"],
            artifacts["alignment"],
        )
        return {
            "waveforms": {
                "user": waveform_summary(
                    artifacts["microphone_audio"], store.artifacts / "display" / "waveform"
                ),
                "reference": waveform_summary(
                    artifacts["current_reference_audio"],
                    store.artifacts / "display" / "waveform",
                ),
            },
            "pitch": pitch_view,
            "notes": [asdict(note) for note in notes],
            "discrepancies": discrepancies,
            "practice_targets": build_practice_targets(
                discrepancies,
                notes,
                mapping,
            ),
            "transport": {
                "mapping": mapping,
                "manual_offset_seconds": float(
                    row.get("playback_offset_seconds") or 0.0
                ),
                "diagnostics": {
                    "system_reference_offset_seconds": analysis["alignment"].get(
                        "global_offset_seconds", 0.0
                    ),
                    "microphone_latency_seconds": analysis["alignment"].get(
                        "microphone_latency_seconds", 0.0
                    ),
                    "microphone_latency_confidence": analysis["alignment"].get(
                        "microphone_latency_confidence", 0.0
                    ),
                    "microphone_latency_method": analysis["alignment"].get(
                        "microphone_latency_method", "unknown"
                    ),
                    "pitch_latency_seconds": analysis["alignment"].get(
                        "pitch_latency_seconds", 0.0
                    ),
                    "pitch_latency_confidence": analysis["alignment"].get(
                        "pitch_latency_confidence", 0.0
                    ),
                    "energy_latency_seconds": analysis["alignment"].get(
                        "energy_latency_seconds", 0.0
                    ),
                    "energy_latency_confidence": analysis["alignment"].get(
                        "energy_latency_confidence", 0.0
                    ),
                    "latency_candidate_disagreement_seconds": analysis[
                        "alignment"
                    ].get("latency_candidate_disagreement_seconds", 0.0),
                    "matched_coverage": analysis["alignment"].get(
                        "matched_coverage", 0.0
                    ),
                    "alignment_confidence": analysis["alignment"].get(
                        "confidence", 0.0
                    ),
                },
            },
        }

    @app.get("/api/projects/{project_id}/takes/{take_id}/scoring")
    def scoring(
        project_id: str,
        take_id: str,
        shift: int | None = Query(default=None, ge=-12, le=12),
    ) -> dict[str, Any]:
        """Recompute inexpensive scoring views without invalidating DSP artifacts."""
        store = library.project(project_id)
        row = store.get_take(take_id)
        analysis = _analysis(row)
        artifacts = {key: Path(value) for key, value in analysis["artifacts"].items()}

        from vocallab.pitch import load_pitch_track

        reference_track = load_pitch_track(artifacts["reference_pitch"])
        user_track = load_pitch_track(artifacts["user_pitch"])
        with np.load(artifacts["alignment"]) as alignment:
            reference_indices = np.asarray(alignment["reference_indices"], dtype=int)
            user_indices = np.asarray(alignment["user_indices"], dtype=int)
        threshold = float(analysis.get("settings", {}).get("voicing_threshold", 0.35))
        reference_values, user_values, confidence, evidence_indices = (
            aligned_pitch_evidence(
                np.asarray(reference_track.smoothed_midi),
                np.asarray(user_track.smoothed_midi),
                np.asarray(reference_track.voicing_probability),
                np.asarray(user_track.voicing_probability),
                reference_indices,
                user_indices,
                threshold,
            )
        )
        detected = TranspositionResult(**analysis["transposition"])
        scoring_payload = build_scoring_modes(
            reference_values,
            user_values,
            confidence,
            detected,
            selected_shift=shift,
        )
        scoring_shift = int(scoring_payload["selected_shift"])
        scoring_transposition = replace(
            detected,
            best_shift=scoring_shift,
            reliable=bool(scoring_payload["transposition_reliable"]),
        )
        baseline = json.loads(
            store.get_baseline(analysis["baseline_id"])["artifact_json"]
        )
        notes = [_note_event(item) for item in baseline["notes"]]
        discrepancy_items = build_discrepancies(
            notes,
            np.asarray(reference_track.time_seconds),
            reference_values,
            user_values,
            evidence_indices,
            scoring_transposition,
            confidence,
            float(baseline.get("reference_confidence", 0.35)),
            float(analysis.get("alignment", {}).get("confidence", 0.0)),
            scoring_reliable=bool(scoring_payload["transposition_reliable"]),
        )
        discrepancies = _map_discrepancy_loops(
            discrepancies_as_dicts(discrepancy_items),
            artifacts["reference_pitch"],
            artifacts["user_pitch"],
            artifacts["alignment"],
        )
        mapping = transport_mapping(
            artifacts["reference_pitch"],
            artifacts["user_pitch"],
            artifacts["alignment"],
        )
        return {
            "scoring": scoring_payload,
            "discrepancies": discrepancies,
            "practice_targets": build_practice_targets(discrepancies, notes, mapping),
        }

    @app.put("/api/projects/{project_id}/takes/{take_id}/playback-offset")
    def save_playback_offset(
        project_id: str, take_id: str, request: PlaybackOffsetRequest
    ) -> dict[str, float]:
        store = library.project(project_id)
        store.save_playback_offset(take_id, request.offset_seconds)
        return {"offset_seconds": request.offset_seconds}

    @app.get("/api/projects/{project_id}/baseline")
    def baseline(project_id: str) -> dict[str, Any]:
        store = library.project(project_id)
        active = store.active_baseline()
        if active is None:
            raise VocalLabError("No active baseline exists.")
        artifact = json.loads(active["artifact_json"])
        return {
            "id": active["id"],
            "version": active["version"],
            "notes": artifact["notes"],
            "versions": [
                _baseline_version_payload(item)
                for item in store.list_baselines()
            ],
        }

    @app.post("/api/projects/{project_id}/baseline/{baseline_id}/activate")
    def activate_baseline(project_id: str, baseline_id: str) -> dict[str, Any]:
        activated = library.project(project_id).activate_baseline(baseline_id)
        return {"id": activated["id"], "version": activated["version"]}

    @app.post("/api/projects/{project_id}/baseline/versions", status_code=201)
    def baseline_version(
        project_id: str, request: BaselineVersionRequest
    ) -> dict[str, Any]:
        return library.save_baseline_version(project_id, request.notes, request.take_id)

    @app.get("/api/projects/{project_id}/compare")
    def compare(project_id: str, first: str, second: str) -> dict[str, Any]:
        store = library.project(project_id)
        first_analysis = _analysis(store.get_take(first))
        second_analysis = _analysis(store.get_take(second))
        comparison = compare_analyses(first_analysis, second_analysis)
        comparison["contours"] = {
            "first": _user_contour(first_analysis),
            "second": _user_contour(second_analysis),
        }
        return comparison

    @app.get("/api/projects/{project_id}/takes/{take_id}/audio/{kind}")
    def artifact_audio(project_id: str, take_id: str, kind: str) -> FileResponse:
        store = library.project(project_id)
        analysis = _analysis(store.get_take(take_id))
        allowed = {
            "user": "microphone_audio",
            "reference": "current_reference_audio",
        }
        if kind not in allowed:
            raise HTTPException(404, "Audio artifact not found.")
        path = Path(analysis["artifacts"][allowed[kind]]).resolve()
        try:
            path.relative_to(store.root)
        except ValueError as exc:
            raise HTTPException(403, "Artifact is outside this project.") from exc
        if not path.exists():
            raise HTTPException(404, "Audio artifact is missing.")
        return FileResponse(path, media_type="audio/wav")

    return app


def _analysis(take: dict[str, Any]) -> dict[str, Any]:
    if not take.get("analysis_json"):
        raise VocalLabError("This take has not been analyzed yet.")
    return json.loads(take["analysis_json"])


def _take_payload(take: dict[str, Any]) -> dict[str, Any]:
    analysis = json.loads(take["analysis_json"]) if take.get("analysis_json") else None
    return {
        "id": take["id"],
        "imported_at": take["imported_at"],
        "status": take["status"],
        "microphone_stream": take["mic_stream"],
        "reference_stream": take["reference_stream"],
        "playback_offset_seconds": float(
            take.get("playback_offset_seconds") or 0.0
        ),
        "analysis": analysis,
    }


def _note_event(payload: dict[str, Any]) -> Any:
    from vocallab.models import NoteEvent, NoteSource

    values = dict(payload)
    values["source"] = NoteSource(values.get("source", "automatic"))
    return NoteEvent(**values)


def _baseline_version_payload(row: dict[str, Any]) -> dict[str, Any]:
    from vocallab.pitch import load_pitch_track

    artifact = json.loads(row["artifact_json"])
    pitch_path = Path(artifact["reference_pitch"])
    preview: dict[str, list[Any]] | None = None
    if pitch_path.exists():
        track = load_pitch_track(pitch_path)
        stride = max(1, len(track.time_seconds) // 500)
        preview = {
            "time": np.asarray(track.time_seconds)[::stride].tolist(),
            "midi": [
                float(value) if np.isfinite(value) else None
                for value in np.asarray(track.smoothed_midi)[::stride]
            ],
        }
    return {
        "id": row["id"],
        "version": row["version"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "engine": artifact.get("separation_engine", "unknown"),
        "reference_confidence": artifact.get("reference_confidence", 0.0),
        "pitch_preview": preview,
    }


def _job_payload(job: Job) -> dict[str, Any]:
    payload = asdict(job)
    if payload["result"]:
        payload["result"] = {
            "take_id": payload["result"]["take_id"],
            "baseline_reused": payload["result"]["baseline_reused"],
        }
    return payload


def _map_discrepancy_loops(
    discrepancies: list[dict[str, Any]],
    reference_path: Path,
    user_path: Path,
    alignment_path: Path,
) -> list[dict[str, Any]]:
    import numpy as np

    from vocallab.pitch import load_pitch_track

    reference = load_pitch_track(reference_path)
    user = load_pitch_track(user_path)
    with np.load(alignment_path) as alignment:
        reference_indices = np.clip(
            alignment["reference_indices"], 0, len(reference.time_seconds) - 1
        )
        user_indices = np.clip(
            alignment["user_indices"], 0, len(user.time_seconds) - 1
        )
    reference_times = np.asarray(reference.time_seconds)[reference_indices]
    user_times = np.asarray(user.time_seconds)[user_indices]
    mapped: list[dict[str, Any]] = []
    for item in discrepancies:
        start = float(item["loop_start_seconds"])
        end = float(item["loop_end_seconds"])
        selected = (reference_times >= start) & (reference_times <= end)
        enriched = dict(item)
        if np.any(selected):
            enriched["loop_current_start_seconds"] = float(np.min(user_times[selected]))
            enriched["loop_current_end_seconds"] = float(np.max(user_times[selected]))
        else:
            enriched["loop_current_start_seconds"] = start
            enriched["loop_current_end_seconds"] = end
        mapped.append(enriched)
    return mapped


def _user_contour(analysis: dict[str, Any]) -> dict[str, Any]:
    artifacts = {key: Path(value) for key, value in analysis["artifacts"].items()}
    view = pitch_visualization(
        artifacts["reference_pitch"],
        artifacts["user_pitch"],
        artifacts["alignment"],
        max_points=1_000,
    )
    return {"time": view["time"], "user_midi": view["user_midi"]}


app = create_app()

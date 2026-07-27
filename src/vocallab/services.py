from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from vocallab.audio import (
    audio_statistics,
    extract_stream,
    inspect_media,
    inspection_dict,
    load_wav,
    validate_stream_selection,
)
from vocallab.errors import VocalLabError
from vocallab.models import NoteEvent, NoteSource
from vocallab.project import ProjectStore


PROJECT_ID = re.compile(r"^[0-9a-f]{32}$")


class LibraryService:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.incoming = self.root / ".incoming"
        self.incoming.mkdir(exist_ok=True)

    def list_projects(self) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        for directory in self.root.iterdir():
            if directory.is_dir() and PROJECT_ID.fullmatch(directory.name):
                try:
                    projects.append(self.project_summary(directory.name))
                except VocalLabError:
                    continue
        return sorted(
            projects,
            key=lambda item: item.get("last_analyzed_at") or item["created_at"],
            reverse=True,
        )

    def create_project(
        self, title: str, artist: str, spotify_url: str | None = None
    ) -> dict[str, Any]:
        project_id = uuid.uuid4().hex
        ProjectStore.create(self.root / project_id, title, artist, spotify_url)
        return self.project_summary(project_id)

    def project(self, project_id: str) -> ProjectStore:
        if not PROJECT_ID.fullmatch(project_id):
            raise VocalLabError("Invalid project identifier.")
        path = (self.root / project_id).resolve()
        if path.parent != self.root:
            raise VocalLabError("Invalid project location.")
        return ProjectStore.open(path)

    def project_summary(self, project_id: str) -> dict[str, Any]:
        store = self.project(project_id)
        song = store.song()
        takes = store.list_takes()
        baseline = store.active_baseline()
        latest_analysis: dict[str, Any] | None = None
        latest_analyzed_at: str | None = None
        for take in reversed(takes):
            if take.get("analysis_json"):
                latest_analysis = json.loads(take["analysis_json"])
                latest_analyzed_at = take["imported_at"]
                break
        return {
            "id": project_id,
            "title": song["title"],
            "artist": song["artist"],
            "spotify_url": song.get("spotify_url"),
            "created_at": song["created_at"],
            "take_count": len(takes),
            "active_baseline_version": int(baseline["version"]) if baseline else None,
            "last_analyzed_at": latest_analyzed_at,
            "detected_transposition": (
                latest_analysis.get("transposition", {}).get("best_shift")
                if latest_analysis
                else None
            ),
            "transposition_reliable": (
                bool(latest_analysis.get("transposition", {}).get("reliable"))
                if latest_analysis
                else False
            ),
            "latest_scoring_mode": (
                latest_analysis.get("scoring", {}).get("default_mode")
                if latest_analysis
                else None
            ),
            "warnings": latest_analysis.get("warnings", []) if latest_analysis else [],
            "latest_metrics": latest_analysis.get("metrics") if latest_analysis else None,
        }

    def delete_project(self, project_id: str, confirmation: str) -> None:
        store = self.project(project_id)
        title = str(store.song()["title"])
        if confirmation != title:
            raise VocalLabError("Project title confirmation did not match.")
        target = store.root.resolve()
        if target.parent != self.root or not PROJECT_ID.fullmatch(target.name):
            raise VocalLabError("Refusing to delete a project outside the library.")
        shutil.rmtree(target)

    def incoming_path(self, token: str) -> Path:
        if not PROJECT_ID.fullmatch(token):
            raise VocalLabError("Invalid recording token.")
        metadata = self.incoming / f"{token}.json"
        if not metadata.exists():
            raise VocalLabError("Recording inspection expired or was not found.")
        payload = json.loads(metadata.read_text(encoding="utf-8"))
        path = Path(payload["path"]).resolve()
        if path.parent != self.incoming or not path.exists():
            raise VocalLabError("Inspected recording is no longer available.")
        return path

    def register_upload(self, temporary_path: Path, original_name: str) -> dict[str, Any]:
        inspection = inspect_media(temporary_path)
        token = temporary_path.stem
        streams: list[dict[str, Any]] = []
        for position, stream in enumerate(inspection.audio_streams):
            preview = self.incoming / f"{token}-stream-{stream.index}.wav"
            extract_stream(
                temporary_path,
                stream.index,
                preview,
                duration_seconds=min(15.0, stream.duration_seconds or 15.0),
            )
            samples, _ = load_wav(preview)
            stats = audio_statistics(samples)
            title = (stream.title or "").lower()
            suggested = (
                "microphone"
                if any(word in title for word in ("mic", "microphone", "voice"))
                else "reference"
                if any(word in title for word in ("desktop", "system", "music", "spotify"))
                else "microphone"
                if position == 0
                else "reference"
                if position == 1
                else "ignore"
            )
            streams.append(
                {
                    **inspection_dict(inspection)["audio_streams"][position],
                    "statistics": stats,
                    "suggested_role": suggested,
                    "preview_url": f"/api/recordings/{token}/preview/{stream.index}",
                }
            )
        metadata = {
            "path": str(temporary_path.resolve()),
            "original_name": Path(original_name).name,
            "inspection": inspection_dict(inspection),
        }
        (self.incoming / f"{token}.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        return {
            "token": token,
            "filename": metadata["original_name"],
            "format_name": inspection.format_name,
            "duration_seconds": inspection.duration_seconds,
            "streams": streams,
        }

    def preview_path(self, token: str, stream_index: int) -> Path:
        self.incoming_path(token)
        preview = (self.incoming / f"{token}-stream-{stream_index}.wav").resolve()
        if preview.parent != self.incoming or not preview.exists():
            raise VocalLabError("Stream preview was not found.")
        return preview

    def import_take(
        self, project_id: str, token: str, mic_stream: int, reference_stream: int
    ) -> str:
        store = self.project(project_id)
        incoming = self.incoming_path(token)
        inspection = inspect_media(incoming)
        validate_stream_selection(inspection, mic_stream, reference_stream)
        metadata = json.loads(
            (self.incoming / f"{token}.json").read_text(encoding="utf-8")
        )
        imports = store.root / "imports"
        imports.mkdir(exist_ok=True)
        source = imports / f"{uuid.uuid4().hex}-{Path(metadata['original_name']).name}"
        shutil.copy2(incoming, source)
        return store.add_take(
            source, mic_stream, reference_stream, inspection_dict(inspection)
        )

    def save_baseline_version(
        self, project_id: str, notes: list[dict[str, Any]], take_id: str
    ) -> dict[str, Any]:
        store = self.project(project_id)
        active = store.active_baseline()
        if active is None:
            raise VocalLabError("Analyze a take before editing its baseline.")
        artifact = json.loads(active["artifact_json"])
        validated: list[dict[str, Any]] = []
        for note in notes:
            event = NoteEvent(
                start_seconds=float(note["start_seconds"]),
                end_seconds=float(note["end_seconds"]),
                attack_end_seconds=float(
                    note.get("attack_end_seconds", note["start_seconds"])
                ),
                release_start_seconds=float(
                    note.get("release_start_seconds", note["end_seconds"])
                ),
                midi_pitch=float(note["midi_pitch"]),
                cents_offset=float(note.get("cents_offset", 0)),
                confidence=float(note.get("confidence", 1)),
                phrase_id=str(note.get("phrase_id", "manual")),
                ornamental=bool(note.get("ornamental", False)),
                scored=bool(note.get("scored", True)),
                source=NoteSource.MANUAL,
            )
            if event.start_seconds < 0 or event.end_seconds <= event.start_seconds:
                raise VocalLabError("Every note must have a non-negative start before its end.")
            if not 0 <= event.midi_pitch <= 127:
                raise VocalLabError("MIDI pitch must be between 0 and 127.")
            payload = event.__dict__.copy()
            payload["source"] = event.source.value
            validated.append(payload)
        artifact["notes"] = sorted(validated, key=lambda item: item["start_seconds"])
        artifact["manual_override"] = {
            "parent_baseline_id": active["id"],
            "edited_note_count": len(validated),
        }
        baseline_id = store.save_baseline(take_id, artifact)
        current = store.active_baseline()
        return {"id": baseline_id, "version": current["version"] if current else None}


def compare_analyses(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    first_items = first.get("discrepancies", [])
    second_items = second.get("discrepancies", [])
    matched_second: set[int] = set()
    improved: list[dict[str, Any]] = []
    worsened: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = []
    for original in first_items:
        candidates = [
            (index, current)
            for index, current in enumerate(second_items)
            if index not in matched_second
            and current["kind"] == original["kind"]
            and _overlap(original, current) > 0
        ]
        if not candidates:
            if float(original.get("confidence", 0)) >= 0.5:
                resolved.append(original)
            continue
        index, current = max(candidates, key=lambda item: _overlap(original, item[1]))
        matched_second.add(index)
        if min(float(original["confidence"]), float(current["confidence"])) < 0.5:
            continue
        delta = float(current["magnitude"]) - float(original["magnitude"])
        item = {"before": original, "after": current, "magnitude_change": delta}
        (improved if delta < 0 else worsened).append(item)
    introduced = [
        item
        for index, item in enumerate(second_items)
        if index not in matched_second and float(item.get("confidence", 0)) >= 0.5
    ]
    metrics_mode, first_metrics, second_metrics = _comparable_metrics(first, second)
    return {
        "first_take_id": first["take_id"],
        "second_take_id": second["take_id"],
        "metrics_mode": metrics_mode,
        "metrics": {"first": first_metrics, "second": second_metrics},
        "improved": improved,
        "worsened": worsened,
        "resolved": resolved,
        "introduced": introduced,
    }


def _comparable_metrics(
    first: dict[str, Any], second: dict[str, Any]
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    first_scoring = first.get("scoring", {})
    second_scoring = second.get("scoring", {})
    first_modes = first_scoring.get("modes", {})
    second_modes = second_scoring.get("modes", {})
    adjusted = (
        bool(first_scoring.get("transposition_reliable"))
        and bool(second_scoring.get("transposition_reliable"))
        and "transposition_adjusted" in first_modes
        and "transposition_adjusted" in second_modes
    )
    mode = "transposition_adjusted" if adjusted else "original_pitch"
    if mode in first_modes and mode in second_modes:
        return (
            mode,
            first_modes[mode]["metrics"],
            second_modes[mode]["metrics"],
        )
    return "legacy", first["metrics"], second["metrics"]


def _overlap(first: dict[str, Any], second: dict[str, Any]) -> float:
    return max(
        0.0,
        min(float(first["end_seconds"]), float(second["end_seconds"]))
        - max(float(first["start_seconds"]), float(second["start_seconds"])),
    )

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from vocallab.cache import file_hash
from vocallab.errors import VocalLabError


SCHEMA_VERSION = 3


class ProjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.database = self.root / "project.sqlite3"
        self.artifacts = self.root / "artifacts"
        self.reports = self.root / "reports"

    @classmethod
    def create(
        cls, root: Path, title: str, artist: str, spotify_url: str | None = None
    ) -> "ProjectStore":
        if (root / "project.sqlite3").exists():
            raise VocalLabError(
                f"A VocalLab project already exists at '{root}'. Open that project or choose "
                "a new project directory."
            )
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise VocalLabError(
                f"Could not create the project directory '{root}'. Choose a writable location "
                "with sufficient disk space, then retry."
            ) from exc
        store = cls(root)
        store.artifacts.mkdir(exist_ok=True)
        store.reports.mkdir(exist_ok=True)
        with store.transaction() as connection:
            store._migrate(connection)
            now = datetime.now(UTC).isoformat()
            connection.execute(
                """
                INSERT INTO song(
                    id, title, artist, spotify_url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), title, artist, spotify_url, now, now),
            )
        return store

    @classmethod
    def open(cls, root: Path) -> "ProjectStore":
        store = cls(root)
        if not store.database.exists():
            raise VocalLabError(
                f"No VocalLab project found at {root}. Create it with 'vocallab create-project'."
            )
        with store.transaction() as connection:
            store._migrate(connection)
        return store

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        # sqlite3.Connection.__exit__ commits or rolls back but does not close.
        # Explicit ownership prevents persistent file locks on Windows.
        with closing(self.connect()) as connection:
            with connection:
                yield connection

    def _migrate(self, connection: sqlite3.Connection) -> None:
        current = connection.execute("PRAGMA user_version").fetchone()[0]
        if current > SCHEMA_VERSION:
            raise VocalLabError(
                f"Project schema {current} is newer than supported schema {SCHEMA_VERSION}."
            )
        if current < 1:
            connection.executescript(
                """
                CREATE TABLE song (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    spotify_url TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE take (
                    id TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    mic_stream INTEGER NOT NULL,
                    reference_stream INTEGER NOT NULL,
                    inspection_json TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'imported',
                    analysis_json TEXT
                );
                CREATE TABLE baseline (
                    id TEXT PRIMARY KEY,
                    source_take_id TEXT NOT NULL REFERENCES take(id),
                    version INTEGER NOT NULL,
                    artifact_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                );
                CREATE INDEX take_imported_at ON take(imported_at);
                PRAGMA user_version = 1;
                """
            )
            current = 1
        if current < 2:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(song)").fetchall()
            }
            if "spotify_url" not in columns:
                connection.execute("ALTER TABLE song ADD COLUMN spotify_url TEXT")
            connection.execute("PRAGMA user_version = 2")
            current = 2
        if current < 3:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(take)").fetchall()
            }
            if "playback_offset_seconds" not in columns:
                connection.execute(
                    "ALTER TABLE take ADD COLUMN playback_offset_seconds "
                    "REAL NOT NULL DEFAULT 0"
                )
            connection.execute("PRAGMA user_version = 3")
        connection.commit()

    def add_take(
        self,
        source: Path,
        mic_stream: int,
        reference_stream: int,
        inspection: dict[str, Any],
    ) -> str:
        source = source.resolve()
        take_id = str(uuid.uuid4())
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO take(
                    id, source_path, source_hash, mic_stream, reference_stream,
                    inspection_json, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    take_id,
                    str(source),
                    file_hash(source),
                    mic_stream,
                    reference_stream,
                    json.dumps(inspection, sort_keys=True),
                    datetime.now(UTC).isoformat(),
                ),
            )
        return take_id

    def get_take(self, selector: str) -> dict[str, Any]:
        with self.transaction() as connection:
            if selector == "latest":
                row = connection.execute(
                    "SELECT * FROM take ORDER BY imported_at DESC LIMIT 1"
                ).fetchone()
            else:
                row = connection.execute("SELECT * FROM take WHERE id = ?", (selector,)).fetchone()
        if row is None:
            raise VocalLabError(f"Take '{selector}' was not found in this project.")
        return dict(row)

    def list_takes(self) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            rows = connection.execute("SELECT * FROM take ORDER BY imported_at").fetchall()
        return [dict(row) for row in rows]

    def song(self) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM song LIMIT 1").fetchone()
        if row is None:
            raise VocalLabError("Project metadata is missing.")
        return dict(row)

    def list_baselines(self) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM baseline ORDER BY version"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_baseline(self, baseline_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM baseline WHERE id = ?", (baseline_id,)
            ).fetchone()
        if row is None:
            raise VocalLabError("Baseline version was not found in this project.")
        return dict(row)

    def activate_baseline(self, baseline_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM baseline WHERE id = ?", (baseline_id,)
            ).fetchone()
            if row is None:
                raise VocalLabError("Baseline version was not found in this project.")
            connection.execute("UPDATE baseline SET active = 0")
            connection.execute(
                "UPDATE baseline SET active = 1 WHERE id = ?", (baseline_id,)
            )
        return dict(row)

    def active_baseline(self) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM baseline WHERE active = 1 ORDER BY version DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def save_baseline(self, take_id: str, artifact: dict[str, Any]) -> str:
        baseline_id = str(uuid.uuid4())
        with self.transaction() as connection:
            row = connection.execute("SELECT MAX(version) FROM baseline").fetchone()
            version = int(row[0] or 0) + 1
            connection.execute("UPDATE baseline SET active = 0")
            connection.execute(
                """
                INSERT INTO baseline(id, source_take_id, version, artifact_json, created_at, active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    baseline_id,
                    take_id,
                    version,
                    json.dumps(artifact, sort_keys=True),
                    datetime.now(UTC).isoformat(),
                ),
            )
        return baseline_id

    def save_analysis(self, take_id: str, analysis: dict[str, Any]) -> None:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE take SET status = 'analyzed', analysis_json = ? WHERE id = ?",
                (json.dumps(analysis, sort_keys=True), take_id),
            )

    def save_playback_offset(self, take_id: str, offset_seconds: float) -> None:
        if not -2.0 <= offset_seconds <= 2.0:
            raise VocalLabError("Playback offset must be between -2.0 and +2.0 seconds.")
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE take SET playback_offset_seconds = ? WHERE id = ?",
                (offset_seconds, take_id),
            )
            if cursor.rowcount != 1:
                raise VocalLabError(f"Take '{take_id}' was not found in this project.")

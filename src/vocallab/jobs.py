from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable


@dataclass
class Job:
    id: str
    project_id: str
    take_id: str
    status: str = "queued"
    stage: str = "queued"
    stages: dict[str, str] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    cancel_requested: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class JobManager:
    def __init__(self, workers: int = 2) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="vocallab")

    def submit(
        self,
        project_id: str,
        take_id: str,
        work: Callable[[Callable[[str, str, dict[str, Any] | None], None]], dict[str, Any]],
    ) -> Job:
        job = Job(str(uuid.uuid4()), project_id, take_id)
        with self._lock:
            self._jobs[job.id] = job

        def run() -> None:
            with self._lock:
                if self._jobs[job.id].status == "cancelled":
                    return
            self._update(job.id, status="running", stage="starting")

            def progress(
                stage: str, status: str, details: dict[str, Any] | None = None
            ) -> None:
                with self._lock:
                    current = self._jobs[job.id]
                    current.stage = stage
                    current.stages[stage] = status
                    if details:
                        current.details[stage] = details
                    current.updated_at = datetime.now(UTC).isoformat()

            try:
                result = work(progress)
            except Exception as exc:
                self._update(job.id, status="failed", error=str(exc))
            else:
                self._update(job.id, status="completed", stage="completed", result=result)

        self._executor.submit(run)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> tuple[bool, str]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False, "Job not found."
            if job.status == "queued":
                job.cancel_requested = True
                job.status = "cancelled"
                return True, "Queued job cancelled."
            if job.status == "running":
                job.cancel_requested = True
                return (
                    False,
                    "The current analysis stage cannot be cancelled safely; "
                    "the request was recorded but processing will finish.",
                )
            return False, f"Job is already {job.status}."

    def _update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in values.items():
                setattr(job, key, value)
            job.updated_at = datetime.now(UTC).isoformat()

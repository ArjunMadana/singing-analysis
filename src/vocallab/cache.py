from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


PIPELINE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "extract": (),
    "separate": ("extract",),
    "pitch-user": ("extract",),
    "pitch-reference": ("separate",),
    "segment": ("pitch-reference",),
    "align": ("pitch-user", "pitch-reference"),
    "score": ("segment", "align"),
    "report": ("score",),
}


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class CacheKey:
    stage: str
    inputs: dict[str, str]
    parameters: dict[str, Any]
    implementation_version: str

    @property
    def digest(self) -> str:
        return stable_hash(
            {
                "stage": self.stage,
                "inputs": self.inputs,
                "parameters": self.parameters,
                "implementation_version": self.implementation_version,
            }
        )


class ArtifactCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: CacheKey, suffix: str) -> Path:
        directory = self.root / key.stage / key.digest
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"artifact{suffix}"

    def manifest_path(self, key: CacheKey) -> Path:
        return self.path(key, ".manifest.json")

    def is_hit(self, key: CacheKey, outputs: Iterable[Path]) -> bool:
        manifest = self.manifest_path(key)
        return manifest.exists() and all(output.exists() for output in outputs)

    def record(self, key: CacheKey, outputs: Iterable[Path], details: dict[str, Any]) -> None:
        payload = {
            "key": key.digest,
            "stage": key.stage,
            "inputs": key.inputs,
            "parameters": key.parameters,
            "implementation_version": key.implementation_version,
            "outputs": [str(path) for path in outputs],
            "details": details,
        }
        self.manifest_path(key).write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )


def invalidated_stages(changed_stage: str) -> set[str]:
    invalidated = {changed_stage}
    changed = True
    while changed:
        changed = False
        for stage, dependencies in PIPELINE_DEPENDENCIES.items():
            if stage not in invalidated and any(dep in invalidated for dep in dependencies):
                invalidated.add(stage)
                changed = True
    return invalidated


from __future__ import annotations

import importlib.util
import importlib.metadata
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vocallab.errors import AnalysisError


@dataclass(frozen=True)
class SeparationResult:
    vocal_path: Path
    instrumental_path: Path | None
    engine: str
    confidence: float
    warnings: tuple[str, ...]


class Separator(Protocol):
    name: str

    def separate(self, source: Path, output_directory: Path) -> SeparationResult: ...


class ReferenceMixFallback:
    name = "reference-mix-fallback-v1"

    def separate(self, source: Path, output_directory: Path) -> SeparationResult:
        return SeparationResult(
            vocal_path=source,
            instrumental_path=None,
            engine=self.name,
            confidence=0.35,
            warnings=(
                "Demucs is unavailable; pitch was tracked from the full reference mix. "
                "Instrumental contamination may reduce accuracy.",
            ),
        )


class DemucsSeparator:
    model = "htdemucs"

    def __init__(self) -> None:
        import torch

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.version = importlib.metadata.version("demucs")
        self.name = f"demucs-{self.version}-{self.model}-{self.device}"

    def separate(self, source: Path, output_directory: Path) -> SeparationResult:
        output_directory.mkdir(parents=True, exist_ok=True)
        command = [
            shutil.which("python") or "python",
            "-m",
            "demucs",
            "--two-stems",
            "vocals",
            "-n",
            self.model,
            "-d",
            self.device,
            "-o",
            str(output_directory),
            str(source),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        stem_root = output_directory / self.model / source.stem
        vocal = stem_root / "vocals.wav"
        accompaniment = stem_root / "no_vocals.wav"
        if result.returncode or not vocal.exists():
            reason = result.stderr.strip() or "Demucs did not create the expected vocal stem."
            raise AnalysisError(
                f"Reference-vocal separation failed. Check the Demucs model installation, "
                f"disk space, and input audio, then retry. Demucs said: {reason}"
            )
        return SeparationResult(
            vocal_path=vocal,
            instrumental_path=accompaniment if accompaniment.exists() else None,
            engine=self.name,
            confidence=0.8,
            warnings=(),
        )


def choose_separator(mode: str = "auto") -> Separator:
    available = importlib.util.find_spec("demucs") is not None
    if mode == "demucs":
        if not available:
            raise AnalysisError(
                "Demucs separation was requested but the 'demucs' package is not installed. "
                "Install it and its model locally, or use '--separator fallback'."
            )
        version = importlib.metadata.version("demucs")
        if version != "4.1.0":
            raise AnalysisError(
                f"Demucs {version} is installed, but VocalLab requires 4.1.0 for "
                "reproducible separation. Install the pinned 'models' extra explicitly."
            )
        return DemucsSeparator()
    if mode == "fallback":
        return ReferenceMixFallback()
    # Auto mode never triggers an implicit model download. Neural separation is
    # enabled only by the user's explicit `--separator demucs` choice.
    return ReferenceMixFallback()


def demucs_capability() -> dict[str, object]:
    available = importlib.util.find_spec("demucs") is not None
    version = importlib.metadata.version("demucs") if available else None
    return {
        "installed": available,
        "version": version,
        "compatible": version == "4.1.0",
        "model": DemucsSeparator.model,
        "device": "selected at analysis time (CUDA when available, otherwise CPU)",
        "model_download_required": (
            "install Demucs first"
            if not available
            else "unknown; the first explicit Demucs run may download htdemucs"
        ),
        "estimated_storage": "not reported by the installed adapter",
        "install_command": 'python -m pip install --no-cache-dir -e ".[models]"',
        "automatic_download": False,
    }

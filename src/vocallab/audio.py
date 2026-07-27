from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

import numpy as np

from vocallab.errors import DependencyError, MediaError
from vocallab.models import AudioStream, MediaInspection


SUPPORTED_EXTENSIONS = {".mkv", ".mp4", ".mov", ".wav", ".flac", ".mp3", ".m4a"}


def require_ffmpeg() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise DependencyError(
            "FFmpeg and FFprobe are required but were not found on PATH. "
            "Install FFmpeg, restart the terminal, and retry."
        )
    return ffmpeg, ffprobe


def inspect_media(path: Path) -> MediaInspection:
    path = path.resolve()
    if not path.exists() or not path.is_file():
        raise MediaError(f"Input file does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise MediaError(
            f"Unsupported input extension '{path.suffix}'. Supported: "
            f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        )
    _, ffprobe = require_ffmpeg()
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        reason = result.stderr.strip() or "FFprobe returned an unknown error."
        raise MediaError(
            f"Could not inspect '{path.name}'. The file may be corrupt or use an "
            f"unsupported codec. FFprobe said: {reason}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError(
            "FFprobe returned malformed metadata; retry with a valid media file."
        ) from exc

    format_payload = payload.get("format", {})
    format_duration = _optional_float(format_payload.get("duration"))
    streams: list[AudioStream] = []
    for stream in payload.get("streams", []):
        if stream.get("codec_type") != "audio":
            continue
        tags = {str(k): str(v) for k, v in stream.get("tags", {}).items()}
        streams.append(
            AudioStream(
                index=int(stream["index"]),
                codec=str(stream.get("codec_name", "unknown")),
                sample_rate=_optional_int(stream.get("sample_rate")),
                channels=_optional_int(stream.get("channels")),
                duration_seconds=_optional_float(stream.get("duration")) or format_duration,
                title=tags.get("title") or tags.get("handler_name"),
                metadata=tags,
            )
        )
    if not streams:
        raise MediaError(
            "The recording contains no audio streams. Confirm OBS recorded the selected "
            "audio tracks."
        )
    return MediaInspection(
        path=str(path),
        duration_seconds=format_duration,
        format_name=str(format_payload.get("format_name", path.suffix.lstrip("."))),
        audio_streams=tuple(streams),
    )


def extract_stream(
    source: Path,
    stream_index: int,
    output: Path,
    sample_rate: int = 48_000,
    start_seconds: float | None = None,
    duration_seconds: float | None = None,
) -> None:
    ffmpeg, _ = require_ffmpeg()
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-v", "error", "-nostdin", "-y"]
    if start_seconds is not None:
        command.extend(["-ss", f"{start_seconds:.6f}"])
    command.extend(["-i", str(source.resolve())])
    if duration_seconds is not None:
        command.extend(["-t", f"{duration_seconds:.6f}"])
    command.extend(
        [
            "-map",
            f"0:{stream_index}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            str(output),
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        reason = result.stderr.strip() or "FFmpeg returned an unknown error."
        raise MediaError(
            f"Could not extract audio stream {stream_index}. Confirm the stream assignment "
            f"and codec. FFmpeg said: {reason}"
        )


def load_wav(path: Path) -> tuple[np.ndarray, int]:
    try:
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except (wave.Error, OSError) as exc:
        raise MediaError(f"Could not read extracted working audio '{path}': {exc}") from exc
    if sample_width != 2:
        raise MediaError(f"Expected 16-bit working WAV but found {sample_width * 8}-bit audio.")
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1, dtype=np.float32)
    return samples, sample_rate


def audio_statistics(samples: np.ndarray) -> dict[str, float]:
    if samples.size == 0:
        return {"peak": 0.0, "rms": 0.0, "silence_ratio": 1.0, "clipped_ratio": 0.0}
    absolute = np.abs(samples)
    return {
        "peak": float(np.max(absolute)),
        "rms": float(np.sqrt(np.mean(np.square(samples, dtype=np.float64)))),
        "silence_ratio": float(np.mean(absolute < 10 ** (-60 / 20))),
        "clipped_ratio": float(np.mean(absolute >= 0.999)),
    }


def frame_rms(
    samples: np.ndarray, sample_rate: int, frame_seconds: float, hop_seconds: float
) -> np.ndarray:
    frame_length = max(1, int(round(frame_seconds * sample_rate)))
    hop_length = max(1, int(round(hop_seconds * sample_rate)))
    if samples.size < frame_length:
        samples = np.pad(samples, (0, frame_length - samples.size))
    frame_count = 1 + (samples.size - frame_length) // hop_length
    values = np.empty(frame_count, dtype=np.float64)
    for index in range(frame_count):
        frame = samples[index * hop_length : index * hop_length + frame_length]
        values[index] = np.sqrt(np.mean(np.square(frame, dtype=np.float64)))
    return values


def inspection_dict(inspection: MediaInspection) -> dict[str, Any]:
    return {
        "path": inspection.path,
        "duration_seconds": inspection.duration_seconds,
        "format_name": inspection.format_name,
        "audio_streams": [
            {
                "index": stream.index,
                "codec": stream.codec,
                "sample_rate": stream.sample_rate,
                "channels": stream.channels,
                "duration_seconds": stream.duration_seconds,
                "title": stream.title,
                "metadata": stream.metadata,
            }
            for stream in inspection.audio_streams
        ],
    }


def validate_stream_selection(
    inspection: MediaInspection, mic_stream: int, reference_stream: int
) -> None:
    indexes = {stream.index for stream in inspection.audio_streams}
    missing = {mic_stream, reference_stream} - indexes
    if missing:
        raise MediaError(
            f"Selected stream index(es) {sorted(missing)} are not audio streams in this recording."
        )
    if mic_stream == reference_stream:
        raise MediaError(
            "Microphone and reference must use different streams. Inspect the recording and "
            "select the isolated OBS tracks explicitly."
        )


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "N/A") else None
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "N/A") else None
    except (TypeError, ValueError):
        return None

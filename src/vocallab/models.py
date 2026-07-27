from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class StreamRole(StrEnum):
    MICROPHONE = "microphone"
    REFERENCE = "reference"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class NoteSource(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    MIDI = "midi"


class ScoringMode(StrEnum):
    ORIGINAL_PITCH = "original_pitch"
    TRANSPOSITION_ADJUSTED = "transposition_adjusted"
    OCTAVE_INVARIANT = "octave_invariant"
    INTERVAL_CONTOUR = "interval_contour"


@dataclass(frozen=True)
class AudioStream:
    index: int
    codec: str
    sample_rate: int | None
    channels: int | None
    duration_seconds: float | None
    title: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MediaInspection:
    path: str
    duration_seconds: float | None
    format_name: str
    audio_streams: tuple[AudioStream, ...]


@dataclass(frozen=True)
class PitchSettings:
    sample_rate: int = 48_000
    hop_seconds: float = 0.01
    frame_seconds: float = 0.04
    min_hz: float = 65.406
    max_hz: float = 2_093.005
    voicing_threshold: float = 0.35
    engine: str = "autocorrelation-v1"


@dataclass(frozen=True)
class PitchTrack:
    time_seconds: Any
    frequency_hz: Any
    raw_midi: Any
    corrected_midi: Any
    smoothed_midi: Any
    cents: Any
    voicing_probability: Any
    confidence: Any
    rms: Any
    tracker: str


@dataclass(frozen=True)
class NoteEvent:
    start_seconds: float
    end_seconds: float
    attack_end_seconds: float
    release_start_seconds: float
    midi_pitch: float
    cents_offset: float
    confidence: float
    phrase_id: str
    ornamental: bool = False
    scored: bool = True
    source: NoteSource = NoteSource.AUTOMATIC


@dataclass(frozen=True)
class AlignmentResult:
    global_offset_seconds: float
    reference_indices: Any
    user_indices: Any
    confidence: float
    profile: str


@dataclass(frozen=True)
class TranspositionResult:
    best_shift: int
    second_best_shift: int
    confidence_margin_cents: float
    support_percentage: float
    octave_shift: int
    pitch_class_shift: int
    support_margin_percentage: float = 0.0
    reliable: bool = False
    method: str = "modal-semitone-support-v2"


@dataclass(frozen=True)
class Discrepancy:
    kind: str
    start_seconds: float
    end_seconds: float
    magnitude: float
    confidence: float
    explanation: str
    loop_start_seconds: float
    loop_end_seconds: float
    target_midi: float | None = None
    user_midi: float | None = None
    provisional: bool = False
    reliability_reason: str | None = None


def jsonable(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value

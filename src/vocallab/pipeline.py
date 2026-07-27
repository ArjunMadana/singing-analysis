from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from vocallab import __version__
from vocallab.alignment import (
    calibrated_alignment_confidence,
    constrained_alignment,
    estimate_global_offset,
    estimate_microphone_latency,
    reconcile_latency_estimates,
)
from vocallab.audio import (
    audio_statistics,
    extract_stream,
    frame_rms,
    load_wav,
)
from vocallab.cache import ArtifactCache, CacheKey, file_hash
from vocallab.errors import AnalysisError
from vocallab.logging_utils import event
from vocallab.models import NoteEvent, NoteSource, PitchSettings
from vocallab.pitch import load_pitch_track, save_pitch_track, track_file
from vocallab.project import ProjectStore
from vocallab.scoring import (
    aligned_pitch_evidence,
    build_discrepancies,
    build_scoring_modes,
    discrepancies_as_dicts,
)
from vocallab.segmentation import segment_notes
from vocallab.separation import SeparationResult, choose_separator
from vocallab.transposition import detect_transposition


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisConfig:
    sample_rate: int = 48_000
    start_seconds: float | None = None
    duration_seconds: float | None = None
    alignment_profile: str = "performance"
    separator: str = "auto"
    refresh_reference: bool = False
    voicing_threshold: float = 0.35

    def pitch_settings(self) -> PitchSettings:
        return PitchSettings(
            sample_rate=self.sample_rate,
            voicing_threshold=self.voicing_threshold,
        )


def analyze_take(
    project: ProjectStore,
    take_selector: str,
    config: AnalysisConfig,
    progress: Callable[[str, str, dict[str, Any] | None], None] | None = None,
) -> dict[str, Any]:
    notify = progress or (lambda stage, status, details=None: None)
    take = project.get_take(take_selector)
    source = Path(take["source_path"])
    if not source.exists():
        raise AnalysisError(
            f"The original recording is no longer available at '{source}'. Restore it or "
            "re-import the take; VocalLab never copies or modifies originals automatically."
        )
    if file_hash(source) != take["source_hash"]:
        raise AnalysisError(
            "The source recording changed after import. Re-import it as a new take so cached "
            "artifacts cannot be associated with the wrong audio."
        )
    cache = ArtifactCache(project.artifacts / "cache")
    pitch_settings = config.pitch_settings()
    cache_events: list[dict[str, str]] = []

    notify("extraction", "running", None)
    mic_path = _extract_cached(
        cache,
        source,
        take["source_hash"],
        int(take["mic_stream"]),
        "microphone",
        config,
        cache_events,
    )
    notify("extraction", "completed", {"cache_events": list(cache_events)})
    current_reference_path = _extract_cached(
        cache,
        source,
        take["source_hash"],
        int(take["reference_stream"]),
        "reference",
        config,
        cache_events,
    )
    mic_samples, mic_rate = load_wav(mic_path)
    reference_samples, reference_rate = load_wav(current_reference_path)
    mic_stats = audio_statistics(mic_samples)
    reference_stats = audio_statistics(reference_samples)
    _validate_audio(mic_stats, "microphone")
    _validate_audio(reference_stats, "reference")

    notify("pitch_tracking", "running", None)
    user_pitch_path = _pitch_cached(
        cache,
        mic_path,
        "pitch-user",
        pitch_settings,
        cache_events,
    )
    user_pitch = load_pitch_track(user_pitch_path)

    active_baseline = project.active_baseline()
    build_reference = active_baseline is None or config.refresh_reference
    if build_reference:
        notify("reference_preparation", "running", None)
        separation = _separate_cached(
            cache, current_reference_path, config.separator, cache_events
        )
        reference_pitch_path = _pitch_cached(
            cache,
            separation.vocal_path,
            "pitch-reference",
            pitch_settings,
            cache_events,
        )
        reference_pitch = load_pitch_track(reference_pitch_path)
        notify("note_generation", "running", None)
        notes = segment_notes(reference_pitch, config.voicing_threshold)
        notify("note_generation", "completed", {"note_count": len(notes)})
        baseline_artifact = {
            "application_version": __version__,
            "reference_working_audio": str(current_reference_path),
            "vocal_audio": str(separation.vocal_path),
            "instrumental_audio": (
                str(separation.instrumental_path) if separation.instrumental_path else None
            ),
            "reference_pitch": str(reference_pitch_path),
            "separation_engine": separation.engine,
            "reference_confidence": separation.confidence,
            "warnings": list(separation.warnings),
            "pitch_settings": asdict(pitch_settings),
            "notes": [_note_dict(note) for note in notes],
        }
        baseline_id = project.save_baseline(take["id"], baseline_artifact)
        baseline_version = (
            int(project.active_baseline()["version"]) if project.active_baseline() else 1
        )
        baseline_reused = False
        notify(
            "reference_preparation",
            "completed",
            {"engine": separation.engine, "warnings": list(separation.warnings)},
        )
    else:
        assert active_baseline is not None
        baseline_artifact = json.loads(active_baseline["artifact_json"])
        baseline_id = str(active_baseline["id"])
        baseline_version = int(active_baseline["version"])
        reference_pitch_path = Path(baseline_artifact["reference_pitch"])
        if not reference_pitch_path.exists():
            raise AnalysisError(
                "The saved baseline pitch artifact is missing. Rerun with '--refresh-reference' "
                "to rebuild it from the current assigned reference stream."
            )
        reference_pitch = load_pitch_track(reference_pitch_path)
        notes = [_note_from_dict(item) for item in baseline_artifact["notes"]]
        notify("note_generation", "reused", {"note_count": len(notes)})
        baseline_reused = True
        cache_events.append({"stage": "baseline", "status": "reused"})
        notify("reference_preparation", "reused", {"baseline_version": baseline_version})
    notify("pitch_tracking", "completed", {"cache_events": list(cache_events)})

    baseline_reference_path = Path(baseline_artifact["reference_working_audio"])
    if not baseline_reference_path.exists():
        raise AnalysisError(
            "The saved baseline synchronization audio is missing. Rerun with "
            "'--refresh-reference' to rebuild the baseline."
        )
    baseline_samples, baseline_rate = load_wav(baseline_reference_path)
    baseline_envelope = frame_rms(
        baseline_samples,
        baseline_rate,
        pitch_settings.frame_seconds,
        pitch_settings.hop_seconds,
    )
    current_envelope = frame_rms(
        reference_samples,
        reference_rate,
        pitch_settings.frame_seconds,
        pitch_settings.hop_seconds,
    )
    microphone_envelope = frame_rms(
        mic_samples,
        mic_rate,
        pitch_settings.frame_seconds,
        pitch_settings.hop_seconds,
    )
    notify("synchronization", "running", None)
    offset, global_confidence = estimate_global_offset(
        baseline_envelope,
        current_envelope,
        pitch_settings.hop_seconds,
    )
    notify("synchronization", "completed", {"offset_seconds": offset})
    notify("alignment", "running", None)
    alignment = constrained_alignment(
        baseline_envelope,
        current_envelope,
        pitch_settings.hop_seconds,
        offset,
        config.alignment_profile,
    )
    current_reference_indices = np.asarray(alignment.user_indices).copy()
    pitch_latency, pitch_latency_confidence = estimate_microphone_latency(
        np.asarray(reference_pitch.smoothed_midi),
        np.asarray(user_pitch.smoothed_midi),
        np.asarray(alignment.reference_indices),
        np.asarray(alignment.user_indices),
        pitch_settings.hop_seconds,
    )
    energy_latency, energy_latency_confidence = estimate_global_offset(
        current_envelope,
        microphone_envelope,
        pitch_settings.hop_seconds,
        max_offset_seconds=2.5,
    )
    microphone_latency, microphone_latency_confidence, microphone_latency_method = (
        reconcile_latency_estimates(
            pitch_latency,
            pitch_latency_confidence,
            energy_latency,
            energy_latency_confidence,
            float(baseline_artifact.get("reference_confidence", 0.35)),
        )
    )
    event(
        LOGGER,
        "microphone_latency_estimated",
        selected_seconds=microphone_latency,
        selected_confidence=microphone_latency_confidence,
        method=microphone_latency_method,
        pitch_seconds=pitch_latency,
        pitch_confidence=pitch_latency_confidence,
        energy_seconds=energy_latency,
        energy_confidence=energy_latency_confidence,
    )
    microphone_latency_frames = int(
        round(microphone_latency / pitch_settings.hop_seconds)
    )
    alignment = type(alignment)(
        global_offset_seconds=alignment.global_offset_seconds,
        reference_indices=alignment.reference_indices,
        user_indices=alignment.user_indices + microphone_latency_frames,
        confidence=alignment.confidence,
        profile=alignment.profile,
    )
    alignment_confidence, matched_coverage = calibrated_alignment_confidence(
        global_confidence,
        alignment.confidence,
        microphone_latency_confidence,
        np.asarray(alignment.reference_indices),
        np.asarray(alignment.user_indices),
        len(reference_pitch.time_seconds),
        len(user_pitch.time_seconds),
    )
    notify("alignment", "completed", {"confidence": alignment_confidence})

    alignment_directory = project.artifacts / "analysis" / take["id"]
    alignment_directory.mkdir(parents=True, exist_ok=True)
    alignment_path = alignment_directory / "alignment.npz"
    np.savez_compressed(
        alignment_path,
        reference_indices=alignment.reference_indices,
        current_reference_indices=current_reference_indices,
        user_indices=alignment.user_indices,
        global_offset_seconds=np.asarray(alignment.global_offset_seconds),
        microphone_latency_seconds=np.asarray(microphone_latency),
        confidence=np.asarray(alignment.confidence),
    )

    notify("transposition", "running", None)
    reference_values, user_values, evidence_confidence, evidence_indices = (
        aligned_pitch_evidence(
            np.asarray(reference_pitch.smoothed_midi),
            np.asarray(user_pitch.smoothed_midi),
            np.asarray(reference_pitch.voicing_probability),
            np.asarray(user_pitch.voicing_probability),
            np.asarray(alignment.reference_indices),
            np.asarray(alignment.user_indices),
            config.voicing_threshold,
        )
    )
    transposition = detect_transposition(
        reference_values, user_values, evidence_confidence
    )
    notify("transposition", "completed", asdict(transposition))
    notify("scoring", "running", None)
    scoring = build_scoring_modes(
        reference_values,
        user_values,
        evidence_confidence,
        transposition,
    )
    metrics = scoring["modes"][scoring["default_mode"]]["metrics"]
    discrepancies = build_discrepancies(
        notes,
        np.asarray(reference_pitch.time_seconds),
        reference_values,
        user_values,
        evidence_indices,
        transposition,
        evidence_confidence,
        float(baseline_artifact.get("reference_confidence", 0.35)),
        alignment_confidence,
        scoring_reliable=bool(scoring["transposition_reliable"]),
    )
    prior_comparison = _prior_take_comparison(project, take["id"], scoring)
    analysis = {
        "application_version": __version__,
        "take_id": take["id"],
        "baseline_id": baseline_id,
        "baseline_version": baseline_version,
        "baseline_reused": baseline_reused,
        "source_hash": take["source_hash"],
        "settings": asdict(config),
        "artifacts": {
            "microphone_audio": str(mic_path),
            "current_reference_audio": str(current_reference_path),
            "reference_pitch": str(reference_pitch_path),
            "user_pitch": str(user_pitch_path),
            "alignment": str(alignment_path),
        },
        "audio_statistics": {
            "microphone": mic_stats,
            "reference": reference_stats,
        },
        "alignment": {
            "profile": alignment.profile,
            "global_offset_seconds": alignment.global_offset_seconds,
            "global_confidence": global_confidence,
            "microphone_latency_seconds": microphone_latency,
            "microphone_latency_confidence": microphone_latency_confidence,
            "microphone_latency_method": microphone_latency_method,
            "pitch_latency_seconds": pitch_latency,
            "pitch_latency_confidence": pitch_latency_confidence,
            "energy_latency_seconds": energy_latency,
            "energy_latency_confidence": energy_latency_confidence,
            "latency_candidate_disagreement_seconds": abs(
                pitch_latency - energy_latency
            ),
            "total_user_offset_seconds": (
                alignment.global_offset_seconds + microphone_latency
            ),
            "local_confidence": alignment.confidence,
            "matched_coverage": matched_coverage,
            "confidence": alignment_confidence,
            "path_points": int(len(alignment.reference_indices)),
        },
        "transposition": asdict(transposition),
        "scoring": scoring,
        "metrics": metrics,
        "discrepancies": discrepancies_as_dicts(discrepancies),
        "comparison_with_previous": prior_comparison,
        "warnings": list(baseline_artifact.get("warnings", [])),
        "reference_processing": {
            "engine": baseline_artifact.get("separation_engine", "unknown"),
            "confidence": baseline_artifact.get("reference_confidence", 0.0),
            "provisional": float(baseline_artifact.get("reference_confidence", 0.0))
            < 0.6,
        },
        "cache_events": cache_events,
    }
    project.save_analysis(take["id"], analysis)
    notify("scoring", "completed", {"discrepancy_count": len(discrepancies)})
    notify("visualization", "running", None)
    from vocallab.report import write_report

    report_path = write_report(
        project, take, analysis, reference_pitch, user_pitch, notes, alignment
    )
    analysis["report_path"] = str(report_path)
    project.save_analysis(take["id"], analysis)
    notify("visualization", "completed", {"report_path": str(report_path)})
    event(
        LOGGER,
        "analysis_complete",
        take_id=take["id"],
        baseline_reused=baseline_reused,
        report=str(report_path),
    )
    return analysis


def _extract_cached(
    cache: ArtifactCache,
    source: Path,
    source_hash: str,
    stream_index: int,
    role: str,
    config: AnalysisConfig,
    cache_events: list[dict[str, str]],
) -> Path:
    parameters = {
        "stream_index": stream_index,
        "role": role,
        "sample_rate": config.sample_rate,
        "start_seconds": config.start_seconds,
        "duration_seconds": config.duration_seconds,
        "channels": 1,
        "codec": "pcm_s16le",
    }
    key = CacheKey("extract", {"source": source_hash}, parameters, "ffmpeg-extract-v1")
    output = cache.path(key, ".wav")
    if cache.is_hit(key, [output]):
        cache_events.append({"stage": f"extract-{role}", "status": "hit"})
        return output
    extract_stream(
        source,
        stream_index,
        output,
        config.sample_rate,
        config.start_seconds,
        config.duration_seconds,
    )
    cache.record(key, [output], {"role": role})
    cache_events.append({"stage": f"extract-{role}", "status": "miss"})
    return output


def _pitch_cached(
    cache: ArtifactCache,
    audio_path: Path,
    stage: str,
    settings: PitchSettings,
    cache_events: list[dict[str, str]],
) -> Path:
    key = CacheKey(
        stage,
        {"audio": file_hash(audio_path)},
        asdict(settings),
        settings.engine,
    )
    output = cache.path(key, ".npz")
    if cache.is_hit(key, [output]):
        cache_events.append({"stage": stage, "status": "hit"})
        return output
    track = track_file(audio_path, settings)
    save_pitch_track(output, track, settings)
    cache.record(key, [output], {"tracker": track.tracker})
    cache_events.append({"stage": stage, "status": "miss"})
    return output


def _separate_cached(
    cache: ArtifactCache,
    reference_path: Path,
    mode: str,
    cache_events: list[dict[str, str]],
) -> SeparationResult:
    separator = choose_separator(mode)
    key = CacheKey(
        "separate",
        {"reference_audio": file_hash(reference_path)},
        {"separator": separator.name, "sample_rate": 48_000},
        separator.name,
    )
    manifest = cache.manifest_path(key)
    if manifest.exists():
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        details = payload["details"]
        vocal = Path(details["vocal_path"])
        instrumental = (
            Path(details["instrumental_path"]) if details.get("instrumental_path") else None
        )
        if vocal.exists() and (instrumental is None or instrumental.exists()):
            cache_events.append({"stage": "separate", "status": "hit"})
            return SeparationResult(
                vocal,
                instrumental,
                details["engine"],
                float(details["confidence"]),
                tuple(details["warnings"]),
            )
    output_directory = manifest.parent / "stems"
    result = separator.separate(reference_path, output_directory)
    outputs = [result.vocal_path]
    if result.instrumental_path:
        outputs.append(result.instrumental_path)
    cache.record(
        key,
        outputs,
        {
            "vocal_path": str(result.vocal_path),
            "instrumental_path": (
                str(result.instrumental_path) if result.instrumental_path else None
            ),
            "engine": result.engine,
            "confidence": result.confidence,
            "warnings": list(result.warnings),
        },
    )
    cache_events.append({"stage": "separate", "status": "miss"})
    return result


def _validate_audio(statistics: dict[str, float], role: str) -> None:
    if statistics["rms"] < 1e-5:
        raise AnalysisError(
            f"The selected {role} stream is silent or extremely quiet. Inspect the OBS track "
            "assignment and import the take again with the correct stream index."
        )
    if statistics["clipped_ratio"] > 0.01:
        event(
            LOGGER,
            "audio_clipping_detected",
            role=role,
            clipped_ratio=statistics["clipped_ratio"],
        )


def _note_dict(note: NoteEvent) -> dict[str, Any]:
    payload = asdict(note)
    payload["source"] = note.source.value
    return payload


def _note_from_dict(payload: dict[str, Any]) -> NoteEvent:
    values = dict(payload)
    values["source"] = NoteSource(values["source"])
    return NoteEvent(**values)


def _prior_take_comparison(
    project: ProjectStore, current_take_id: str, current_scoring: dict[str, Any]
) -> dict[str, Any] | None:
    analyzed = [
        take
        for take in project.list_takes()
        if take["id"] != current_take_id and take.get("analysis_json")
    ]
    if not analyzed:
        return None
    previous = analyzed[-1]
    previous_analysis = json.loads(previous["analysis_json"])
    previous_scoring = previous_analysis.get("scoring", {})
    use_adjusted = (
        bool(current_scoring.get("transposition_reliable"))
        and bool(previous_scoring.get("transposition_reliable"))
    )
    mode = "transposition_adjusted" if use_adjusted else "original_pitch"
    current_metrics = current_scoring.get("modes", {}).get(mode, {}).get("metrics", {})
    prior_metrics = previous_scoring.get("modes", {}).get(mode, {}).get("metrics", {})
    current_value = current_metrics.get("median_absolute_cents")
    prior_value = prior_metrics.get("median_absolute_cents")
    if current_value is None or prior_value is None:
        return None
    delta = float(current_value) - float(prior_value)
    label = (
        "Key-adjusted median pitch error"
        if use_adjusted
        else "Original-key median pitch difference"
    )
    return {
        "take_id": previous["id"],
        "scoring_mode": mode,
        "median_absolute_cents_change": delta,
        "summary": (
            f"{label} improved by {abs(delta):.1f} cents."
            if delta < 0
            else f"{label} worsened by {delta:.1f} cents."
            if delta > 0
            else f"{label} was unchanged."
        ),
    }

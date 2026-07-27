from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from vocallab.models import AlignmentResult, NoteEvent, PitchTrack
from vocallab.project import ProjectStore


def write_report(
    project: ProjectStore,
    take: dict[str, Any],
    analysis: dict[str, Any],
    reference_pitch: PitchTrack,
    user_pitch: PitchTrack,
    notes: list[NoteEvent],
    alignment: AlignmentResult,
) -> Path:
    output = project.reports / f"{take['id']}.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    mic_audio = _relative(output.parent, Path(analysis["artifacts"]["microphone_audio"]))
    ref_audio = _relative(output.parent, Path(analysis["artifacts"]["current_reference_audio"]))
    scoring = analysis.get("scoring", {})
    selected_shift = int(
        scoring.get("selected_shift", analysis["transposition"]["best_shift"])
    )
    chart = _pitch_svg(
        reference_pitch,
        user_pitch,
        notes,
        alignment,
        selected_shift,
    )
    scoring_sections = _scoring_html(scoring, analysis["metrics"])
    discrepancy_items = _discrepancy_html(
        analysis["discrepancies"], reference_pitch, user_pitch, alignment
    )
    warnings = "".join(
        f"<li>{html.escape(str(warning))}</li>" for warning in analysis.get("warnings", [])
    )
    warning_section = (
        f'<section class="panel warning"><h2>Quality warnings</h2>'
        f"<ul>{warnings}</ul></section>"
        if warnings
        else ""
    )
    transposition = analysis["transposition"]
    content = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VocalLab take report</title>
<style>
:root {{ color-scheme: dark; font-family: system-ui, sans-serif; }}
body {{ max-width: 1180px; margin: 2rem auto; padding: 0 1rem; background:#10141c; color:#e7edf7; }}
.panel {{ background:#18202c; border:1px solid #2b394b; border-radius:12px;
padding:1rem; margin:1rem 0; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:1rem; }}
table {{ border-collapse:collapse; width:100%; }}
th,td {{ text-align:left; padding:.4rem; border-bottom:1px solid #2b394b; }}
th {{ color:#9fb1c7; font-weight:500; }} audio {{ width:100%; }} button {{ cursor:pointer; }}
.warning {{ border-color:#a66b28; }} small {{ color:#aebbd0; }}
svg {{ width:100%; height:auto; background:#0e1219; border-radius:8px; }}
.legend span {{ margin-right:1rem; }} .ref {{ color:#77bdfb; }}
.shifted {{ color:#7ce2c7; }} .user {{ color:#ff9e64; }}
</style>
</head>
<body>
<h1>VocalLab take analysis</h1>
<p>Take <code>{html.escape(take['id'])}</code> · baseline version {analysis['baseline_version']}
· {'reused baseline' if analysis['baseline_reused'] else 'new baseline'}</p>
<div class="grid">
  <section class="panel"><h2>User microphone</h2>
  <audio id="user-audio" controls src="{html.escape(mic_audio)}"></audio></section>
  <section class="panel"><h2>Synchronization reference</h2>
  <audio id="ref-audio" controls src="{html.escape(ref_audio)}"></audio>
  <small>Local derived audio; not embedded in the HTML file.</small></section>
</div>
<section class="panel">
<h2>Pitch comparison</h2>
<p class="legend"><span class="ref">Original artist</span>
<span class="shifted">Reference shifted {selected_shift:+d} st</span>
<span class="user">User (aligned)</span></p>
{chart}
</section>
<div class="grid">
<section class="panel"><h2>Transposition</h2>
<p>Best shift: <strong>{transposition['best_shift']:+d} semitones</strong></p>
<p>Pitch-class shift {transposition['pitch_class_shift']:+d}; octave displacement
{transposition['octave_shift']:+d}; support {transposition['support_percentage']:.1f}%.</p>
<p>Runner-up {transposition['second_best_shift']:+d}; confidence margin
{transposition['confidence_margin_cents']:.1f} cents.</p>
<p>Coherent detection: <strong>{'yes' if transposition.get('reliable') else 'no'}</strong>;
support margin {transposition.get('support_margin_percentage', 0.0):.1f} points.</p>
</section>
<section class="panel"><h2>Alignment</h2>
<p>System-audio offset {analysis['alignment']['global_offset_seconds']:+.3f}s · microphone
latency {analysis['alignment'].get('microphone_latency_seconds', 0.0):+.3f}s · confidence
{analysis['alignment']['confidence']:.2f} · profile
{html.escape(analysis['alignment']['profile'])}</p>
</section>
</div>
{scoring_sections}
<section class="panel"><h2>Prioritized discrepancies</h2><ol>{discrepancy_items}</ol></section>
{warning_section}
<section class="panel"><h2>Provenance</h2><details><summary>Analysis manifest</summary>
<pre>{html.escape(json.dumps(analysis, indent=2, sort_keys=True))}</pre></details></section>
<script>
for (const button of document.querySelectorAll('button[data-start]')) {{
  button.addEventListener('click', () => {{
    const start = Number(button.dataset.start), end = Number(button.dataset.end);
    for (const player of document.querySelectorAll('audio')) {{
      player.currentTime = start;
      player.play();
    }}
    const timer = setInterval(() => {{
      const player = document.getElementById('user-audio');
      if (player.currentTime >= end) {{
        for (const audio of document.querySelectorAll('audio')) audio.currentTime = start;
      }}
    }}, 50);
    button.textContent = 'Looping';
  }});
}}
</script>
</body></html>"""
    output.write_text(content, encoding="utf-8")
    return output


def _pitch_svg(
    reference: PitchTrack,
    user: PitchTrack,
    notes: list[NoteEvent],
    alignment: AlignmentResult,
    reference_shift_semitones: int = 0,
) -> str:
    width, height = 1100, 380
    reference_time = np.asarray(reference.time_seconds)
    reference_midi = np.asarray(reference.smoothed_midi)
    duration = max(float(reference_time[-1]) if reference_time.size else 1.0, 1.0)
    shifted_reference_midi = reference_midi + reference_shift_semitones
    finite_values = np.concatenate(
        [
            reference_midi[np.isfinite(reference_midi)],
            shifted_reference_midi[np.isfinite(shifted_reference_midi)],
        ]
    )
    user_midi = np.asarray(user.smoothed_midi)
    finite_user = user_midi[np.isfinite(user_midi)]
    combined = np.concatenate([finite_values, finite_user])
    low = float(np.percentile(combined, 2) - 2) if combined.size else 48.0
    high = float(np.percentile(combined, 98) + 2) if combined.size else 72.0
    if high - low < 12:
        high = low + 12

    def point(time: float, midi: float) -> str:
        x = time / duration * width
        y = height - (midi - low) / (high - low) * height
        return f"{x:.1f},{y:.1f}"

    reference_segments = _segments(reference_time, reference_midi, point)
    shifted_segments = _segments(reference_time, shifted_reference_midi, point)
    if len(alignment.reference_indices):
        ref_indexes = np.clip(alignment.reference_indices, 0, reference_time.size - 1)
        user_indexes = np.clip(alignment.user_indices, 0, user_midi.size - 1)
        aligned_time = reference_time[ref_indexes]
        aligned_user = user_midi[user_indexes]
    else:
        aligned_time = np.asarray(user.time_seconds)
        aligned_user = user_midi
    user_segments = _segments(aligned_time, aligned_user, point)
    note_rectangles = "".join(
        (
            f"<rect x='{note.start_seconds / duration * width:.1f}' "
            f"width='{max(1.0, (note.end_seconds - note.start_seconds) / duration * width):.1f}' "
            f"y='{height - (note.midi_pitch + .5 - low) / (high - low) * height:.1f}' "
            f"height='{height / (high - low):.1f}' fill='#77bdfb' opacity='.13'/>"
        )
        for note in notes
    )
    ref_lines = "".join(
        f"<polyline points='{segment}' fill='none' stroke='#77bdfb' "
        f"stroke-width='1' stroke-dasharray='5 4'/>"
        for segment in reference_segments
    )
    shifted_lines = "".join(
        f"<polyline points='{segment}' fill='none' stroke='#7ce2c7' stroke-width='1.8'/>"
        for segment in shifted_segments
    )
    user_lines = "".join(
        f"<polyline points='{segment}' fill='none' stroke='#ff9e64' stroke-width='1.5'/>"
        for segment in user_segments
    )
    return (
        f"<svg viewBox='0 0 {width} {height}' role='img' "
        f"aria-label='Aligned reference and user pitch contours'>"
        f"{note_rectangles}{ref_lines}{shifted_lines}{user_lines}</svg>"
    )


def _scoring_html(
    scoring: dict[str, Any], legacy_metrics: dict[str, Any]
) -> str:
    modes = scoring.get("modes")
    if not isinstance(modes, dict):
        modes = {
            "legacy": {
                "title": "Legacy score",
                "description": "This report predates explicit scoring modes.",
                "metrics": legacy_metrics,
            }
        }
    default_mode = scoring.get("default_mode", "legacy")
    sections: list[str] = []
    for key, mode in modes.items():
        metrics = mode.get("metrics", {})
        rows = "".join(
            f"<tr><th>{html.escape(str(name).replace('_', ' '))}</th>"
            f"<td>{_format_value(value)}</td></tr>"
            for name, value in metrics.items()
        )
        marker = " · default accuracy view" if key == default_mode else ""
        if mode.get("available") is False:
            marker += " · unavailable until key selection"
        sections.append(
            f"<section class='panel'><h2>{html.escape(str(mode.get('title', key)))}"
            f"{marker}</h2><p>{html.escape(str(mode.get('description', '')))}</p>"
            f"<table>{rows}</table></section>"
        )
    return "".join(sections)


def _segments(
    times: np.ndarray, values: np.ndarray, point: Any
) -> list[str]:
    valid = np.isfinite(values)
    indexes = np.flatnonzero(valid)
    if indexes.size == 0:
        return []
    splits = np.flatnonzero(np.diff(indexes) > 1) + 1
    return [
        " ".join(point(float(times[index]), float(values[index])) for index in group)
        for group in np.split(indexes, splits)
        if group.size >= 2
    ]


def _discrepancy_html(
    discrepancies: list[dict[str, Any]],
    reference: PitchTrack,
    user: PitchTrack,
    alignment: AlignmentResult,
) -> str:
    items: list[str] = []
    for item in discrepancies:
        loop_start, loop_end = _mapped_loop_range(
            float(item["loop_start_seconds"]),
            float(item["loop_end_seconds"]),
            reference,
            user,
            alignment,
        )
        items.append(
            "<li>"
            f"<button data-start='{loop_start:.4f}' data-end='{loop_end:.4f}'>Loop</button> "
            f"<strong>{html.escape(str(item['kind']))}</strong> "
            f"{float(item['start_seconds']):.2f}–{float(item['end_seconds']):.2f}s "
            f"(baseline timeline) — {html.escape(str(item['explanation']))} "
            f"<small>confidence {float(item['confidence']):.2f}</small></li>"
        )
    return "".join(items) or (
        "<li>No high-confidence note discrepancies exceeded the current thresholds.</li>"
    )


def _mapped_loop_range(
    start_seconds: float,
    end_seconds: float,
    reference: PitchTrack,
    user: PitchTrack,
    alignment: AlignmentResult,
) -> tuple[float, float]:
    reference_times = np.asarray(reference.time_seconds)
    user_times = np.asarray(user.time_seconds)
    if not len(alignment.reference_indices) or not reference_times.size or not user_times.size:
        return start_seconds, end_seconds
    reference_indexes = np.clip(
        np.asarray(alignment.reference_indices), 0, reference_times.size - 1
    )
    user_indexes = np.clip(np.asarray(alignment.user_indices), 0, user_times.size - 1)
    mapped_reference_times = reference_times[reference_indexes]
    mapped_user_times = user_times[user_indexes]
    selected = (mapped_reference_times >= start_seconds) & (
        mapped_reference_times <= end_seconds
    )
    if np.any(selected):
        return (
            max(0.0, float(np.min(mapped_user_times[selected]))),
            float(np.max(mapped_user_times[selected])),
        )
    start_index = int(np.argmin(np.abs(mapped_reference_times - start_seconds)))
    end_index = int(np.argmin(np.abs(mapped_reference_times - end_seconds)))
    mapped_start = float(mapped_user_times[min(start_index, end_index)])
    mapped_end = float(mapped_user_times[max(start_index, end_index)])
    return max(0.0, mapped_start), max(mapped_start, mapped_end)


def _relative(base: Path, target: Path) -> str:
    return Path(os.path.relpath(target, base)).as_posix()


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return html.escape(str(value))

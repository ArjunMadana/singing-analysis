from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path
from typing import Any, Sequence

from vocallab.audio import (
    inspect_media,
    inspection_dict,
    require_ffmpeg,
    validate_stream_selection,
)
from vocallab.errors import VocalLabError
from vocallab.logging_utils import configure_logging
from vocallab.pipeline import AnalysisConfig, analyze_take
from vocallab.project import ProjectStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vocallab",
        description="Local-first singing accuracy analysis",
    )
    parser.add_argument("--verbose", action="store_true", help="emit debug logs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="list media audio streams")
    inspect_parser.add_argument("recording", type=Path)
    inspect_parser.add_argument("--json", action="store_true", help="print machine-readable JSON")

    create = subparsers.add_parser("create-project", help="create a song project")
    create.add_argument("--title", required=True)
    create.add_argument("--artist", required=True)
    create.add_argument("--project-dir", required=True, type=Path)

    import_take = subparsers.add_parser("import-take", help="register a recording and streams")
    import_take.add_argument("--project", required=True, type=Path)
    import_take.add_argument("--input", required=True, type=Path)
    import_take.add_argument("--mic-stream", required=True, type=int)
    import_take.add_argument("--reference-stream", required=True, type=int)

    analyze = subparsers.add_parser("analyze", help="run the local analysis pipeline")
    analyze.add_argument("--project", required=True, type=Path)
    analyze.add_argument("--take", default="latest")
    analyze.add_argument("--start", type=float, default=None, help="section start in seconds")
    analyze.add_argument("--duration", type=float, default=None, help="section duration in seconds")
    analyze.add_argument(
        "--separator", choices=("auto", "demucs", "fallback"), default="auto"
    )
    analyze.add_argument("--refresh-reference", action="store_true")

    report = subparsers.add_parser("report", help="locate an existing take report")
    report.add_argument("--project", required=True, type=Path)
    report.add_argument("--take", default="latest")
    report.add_argument("--open", action="store_true", dest="open_report")

    serve = subparsers.add_parser("serve", help="run the local application API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)
    serve.add_argument("--library", default=Path("projects"), type=Path)

    subparsers.add_parser("doctor", help="check required local dependencies")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    configure_logging(arguments.verbose)
    try:
        return _dispatch(arguments)
    except VocalLabError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _dispatch(arguments: argparse.Namespace) -> int:
    if arguments.command == "inspect":
        inspection = inspect_media(arguments.recording)
        payload = inspection_dict(inspection)
        if arguments.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"{inspection.path} ({inspection.duration_seconds or 0:.2f}s)")
            for stream in inspection.audio_streams:
                title = f" — {stream.title}" if stream.title else ""
                print(
                    f"[{stream.index}] {stream.codec}, {stream.sample_rate or '?'} Hz, "
                    f"{stream.channels or '?'} channel(s){title}"
                )
        return 0
    if arguments.command == "create-project":
        store = ProjectStore.create(arguments.project_dir, arguments.title, arguments.artist)
        print(store.root)
        return 0
    if arguments.command == "import-take":
        store = ProjectStore.open(arguments.project)
        inspection = inspect_media(arguments.input)
        validate_stream_selection(
            inspection, arguments.mic_stream, arguments.reference_stream
        )
        take_id = store.add_take(
            arguments.input,
            arguments.mic_stream,
            arguments.reference_stream,
            inspection_dict(inspection),
        )
        print(take_id)
        return 0
    if arguments.command == "analyze":
        if arguments.start is not None and arguments.start < 0:
            raise VocalLabError("--start must be zero or greater.")
        if arguments.duration is not None and arguments.duration <= 0:
            raise VocalLabError("--duration must be greater than zero.")
        store = ProjectStore.open(arguments.project)
        result = analyze_take(
            store,
            arguments.take,
            AnalysisConfig(
                start_seconds=arguments.start,
                duration_seconds=arguments.duration,
                separator=arguments.separator,
                refresh_reference=arguments.refresh_reference,
            ),
        )
        print(json.dumps(_summary(result), indent=2, sort_keys=True))
        return 0
    if arguments.command == "report":
        store = ProjectStore.open(arguments.project)
        take = store.get_take(arguments.take)
        if not take.get("analysis_json"):
            raise VocalLabError("This take has not been analyzed. Run 'vocallab analyze' first.")
        analysis = json.loads(take["analysis_json"])
        report_path = Path(analysis["report_path"])
        if not report_path.exists():
            raise VocalLabError(
                "The report artifact is missing. Rerun 'vocallab analyze' to regenerate it."
            )
        print(report_path)
        if arguments.open_report:
            webbrowser.open(report_path.resolve().as_uri())
        return 0
    if arguments.command == "doctor":
        ffmpeg, ffprobe = require_ffmpeg()
        print(json.dumps({"ffmpeg": ffmpeg, "ffprobe": ffprobe}, indent=2))
        return 0
    if arguments.command == "serve":
        import uvicorn

        from vocallab.api import create_app

        uvicorn.run(
            create_app(arguments.library),
            host=arguments.host,
            port=arguments.port,
            log_level="debug" if arguments.verbose else "info",
        )
        return 0
    raise AssertionError(f"Unhandled command: {arguments.command}")


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "take_id": result["take_id"],
        "baseline_version": result["baseline_version"],
        "baseline_reused": result["baseline_reused"],
        "alignment": result["alignment"],
        "transposition": result["transposition"],
        "metrics": result["metrics"],
        "discrepancy_count": len(result["discrepancies"]),
        "comparison_with_previous": result["comparison_with_previous"],
        "warnings": result["warnings"],
        "cache_events": result["cache_events"],
        "report_path": result["report_path"],
    }

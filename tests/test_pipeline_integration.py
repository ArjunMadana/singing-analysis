import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from vocallab.audio import inspect_media, inspection_dict
from vocallab.pipeline import AnalysisConfig, analyze_take
from vocallab.project import ProjectStore


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg unavailable")
class PipelineIntegrationTests(unittest.TestCase):
    def _recording(self, path: Path, mic_frequency: float) -> None:
        subprocess.run(
            [
                shutil.which("ffmpeg") or "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={mic_frequency}:duration=1.2:sample_rate=48000",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=1.2:sample_rate=48000",
                "-map",
                "0:a",
                "-map",
                "1:a",
                "-c:a",
                "pcm_s16le",
                str(path),
            ],
            check=True,
        )

    def test_second_take_reuses_baseline_and_reports_improvement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ProjectStore.create(root / "project", "Synthetic", "Test")
            first_file = root / "first.mkv"
            self._recording(first_file, 466.16)
            first_inspection = inspect_media(first_file)
            streams = [stream.index for stream in first_inspection.audio_streams]
            first_id = store.add_take(
                first_file, streams[0], streams[1], inspection_dict(first_inspection)
            )
            first = analyze_take(
                store, first_id, AnalysisConfig(separator="fallback")
            )
            self.assertFalse(first["baseline_reused"])
            report_path = Path(first["report_path"])
            self.assertTrue(report_path.exists())
            report_html = report_path.read_text(encoding="utf-8")
            self.assertIn("microphone", report_html)
            self.assertIn("latency", report_html)

            second_file = root / "second.mkv"
            self._recording(second_file, 440.0)
            second_inspection = inspect_media(second_file)
            second_streams = [stream.index for stream in second_inspection.audio_streams]
            second_id = store.add_take(
                second_file,
                second_streams[0],
                second_streams[1],
                inspection_dict(second_inspection),
            )
            second = analyze_take(
                store, second_id, AnalysisConfig(separator="fallback")
            )
            self.assertTrue(second["baseline_reused"])
            self.assertTrue(any(e["stage"] == "baseline" for e in second["cache_events"]))
            self.assertIsNotNone(second["comparison_with_previous"])
            stored = store.get_take(second_id)
            stored_baseline = json.loads(stored["analysis_json"])["baseline_id"]
            self.assertEqual(stored_baseline, first["baseline_id"])


if __name__ == "__main__":
    unittest.main()

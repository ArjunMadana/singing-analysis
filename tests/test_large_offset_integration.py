import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from vocallab.api import _map_discrepancy_loops
from vocallab.audio import inspect_media, inspection_dict
from vocallab.pipeline import AnalysisConfig, analyze_take
from vocallab.project import ProjectStore


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg unavailable")
class LargeOffsetIntegrationTests(unittest.TestCase):
    def _write_melody(
        self, path: Path, delay_seconds: float = 0.0, cents_shift: float = 0.0
    ) -> None:
        sample_rate = 48_000
        notes = [220.0, 277.18, 246.94, 329.63, 293.66]
        chunks = [np.zeros(int(delay_seconds * sample_rate))]
        for frequency in notes:
            frequency *= 2 ** (cents_shift / 1200)
            time = np.arange(int(0.35 * sample_rate)) / sample_rate
            envelope = np.minimum(1, time / 0.02) * np.minimum(
                1, (0.35 - time) / 0.02
            )
            chunks.append(
                0.45 * envelope * np.sin(2 * np.pi * frequency * time)
                + 0.12 * envelope * np.sin(4 * np.pi * frequency * time)
            )
        samples = np.concatenate(chunks)
        pcm = np.clip(samples * 32767, -32768, 32767).astype("<i2")
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(pcm.tobytes())

    def test_one_second_device_delay_is_removed_before_pitch_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference_wav = root / "reference.wav"
            microphone_wav = root / "microphone.wav"
            recording = root / "delayed.mkv"
            self._write_melody(reference_wav)
            self._write_melody(microphone_wav, delay_seconds=1.0)
            subprocess.run(
                [
                    shutil.which("ffmpeg") or "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    str(microphone_wav),
                    "-i",
                    str(reference_wav),
                    "-map",
                    "0:a",
                    "-map",
                    "1:a",
                    "-c:a",
                    "pcm_s16le",
                    str(recording),
                ],
                check=True,
            )
            inspection = inspect_media(recording)
            streams = [stream.index for stream in inspection.audio_streams]
            project = ProjectStore.create(root / "project", "Delay", "Fixture")
            take_id = project.add_take(
                recording, streams[0], streams[1], inspection_dict(inspection)
            )
            analysis = analyze_take(
                project, take_id, AnalysisConfig(separator="fallback")
            )
            self.assertAlmostEqual(
                analysis["alignment"]["microphone_latency_seconds"], 1.0, delta=0.08
            )
            self.assertLess(analysis["metrics"]["median_absolute_cents"], 15)
            fake = [
                {
                    "loop_start_seconds": 0.1,
                    "loop_end_seconds": 0.5,
                }
            ]
            artifacts = {
                key: Path(value) for key, value in analysis["artifacts"].items()
            }
            mapped = _map_discrepancy_loops(
                fake,
                artifacts["reference_pitch"],
                artifacts["user_pitch"],
                artifacts["alignment"],
            )
            self.assertAlmostEqual(
                mapped[0]["loop_current_start_seconds"], 1.1, delta=0.08
            )


if __name__ == "__main__":
    unittest.main()

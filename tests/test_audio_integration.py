import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from vocallab.audio import extract_stream, inspect_media, load_wav, validate_stream_selection


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg unavailable")
class AudioIntegrationTests(unittest.TestCase):
    def test_inspects_and_extracts_two_audio_streams(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recording = root / "two-tracks.mkv"
            subprocess.run(
                [
                    shutil.which("ffmpeg") or "ffmpeg",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=0.5:sample_rate=48000",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=554.37:duration=0.5:sample_rate=48000",
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
            self.assertEqual(len(inspection.audio_streams), 2)
            first, second = [stream.index for stream in inspection.audio_streams]
            validate_stream_selection(inspection, first, second)
            output = root / "first.wav"
            extract_stream(recording, first, output)
            samples, sample_rate = load_wav(output)
            self.assertEqual(sample_rate, 48_000)
            self.assertGreater(samples.size, 20_000)


if __name__ == "__main__":
    unittest.main()


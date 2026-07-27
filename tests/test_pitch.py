import unittest

import numpy as np

from vocallab.models import PitchSettings
from vocallab.pitch import AutocorrelationPitchEngine


class SyntheticPitchTests(unittest.TestCase):
    def test_tracks_vocal_like_a4(self) -> None:
        sample_rate = 48_000
        duration = 1.0
        time = np.arange(int(sample_rate * duration)) / sample_rate
        fundamental = 440.0
        samples = (
            0.45 * np.sin(2 * np.pi * fundamental * time)
            + 0.2 * np.sin(2 * np.pi * fundamental * 2 * time)
            + 0.08 * np.sin(2 * np.pi * fundamental * 3 * time)
        ).astype(np.float32)
        settings = PitchSettings()
        track = AutocorrelationPitchEngine().track(samples, sample_rate, settings)
        voiced = track.voicing_probability >= settings.voicing_threshold
        self.assertGreater(np.mean(voiced), 0.9)
        self.assertAlmostEqual(float(np.median(track.smoothed_midi[voiced])), 69.0, delta=0.15)

    def test_silence_is_unvoiced(self) -> None:
        samples = np.zeros(48_000, dtype=np.float32)
        track = AutocorrelationPitchEngine().track(samples, 48_000, PitchSettings())
        self.assertEqual(np.count_nonzero(track.voicing_probability), 0)
        self.assertTrue(np.all(np.isnan(track.smoothed_midi)))


if __name__ == "__main__":
    unittest.main()


import unittest

import numpy as np

from vocallab.music import cents_error, decompose_shift, hz_to_midi, midi_to_hz


class MusicConversionTests(unittest.TestCase):
    def test_frequency_and_midi_round_trip(self) -> None:
        frequencies = np.array([65.406391, 220.0, 440.0, 880.0])
        np.testing.assert_allclose(
            midi_to_hz(hz_to_midi(frequencies)), frequencies, rtol=1e-7
        )

    def test_cents_error_is_signed(self) -> None:
        np.testing.assert_allclose(
            cents_error(np.array([69.25, 68.5]), np.array([69.0, 69.0])),
            [25.0, -50.0],
        )

    def test_octave_decomposition_is_separate(self) -> None:
        self.assertEqual(decompose_shift(-12), (0, -12))
        self.assertEqual(decompose_shift(10), (-2, 12))


if __name__ == "__main__":
    unittest.main()


import unittest

import numpy as np

from vocallab.transposition import detect_transposition


class TranspositionTests(unittest.TestCase):
    def test_detects_integer_shift_with_outlier(self) -> None:
        reference = np.array([60, 62, 64, 65, 67, 69], dtype=float)
        user = reference - 5
        user[-1] += 2
        result = detect_transposition(reference, user)
        self.assertEqual(result.best_shift, -5)
        self.assertGreater(result.support_percentage, 80)
        self.assertGreater(result.confidence_margin_cents, 50)

    def test_reports_octave_separately(self) -> None:
        reference = np.array([60, 64, 67, 72], dtype=float)
        result = detect_transposition(reference, reference - 12)
        self.assertEqual(result.best_shift, -12)
        self.assertEqual(result.pitch_class_shift, 0)
        self.assertEqual(result.octave_shift, -12)

    def test_no_evidence_is_low_confidence(self) -> None:
        result = detect_transposition(np.array([np.nan]), np.array([np.nan]))
        self.assertEqual(result.support_percentage, 0)

    def test_multimodal_evidence_does_not_invent_midpoint_shift(self) -> None:
        reference = np.full(10, 60.0)
        user = np.concatenate([np.full(5, 60.0), np.full(5, 48.0)])
        result = detect_transposition(reference, user)
        self.assertIn(result.best_shift, {0, -12})
        self.assertNotEqual(result.best_shift, -6)
        self.assertFalse(result.reliable)
        self.assertEqual(result.support_margin_percentage, 0)

    def test_coherent_shift_is_reliable(self) -> None:
        reference = np.array([60, 62, 64, 65, 67], dtype=float)
        result = detect_transposition(reference, reference - 6)
        self.assertEqual(result.best_shift, -6)
        self.assertTrue(result.reliable)
        self.assertEqual(result.support_percentage, 100)


if __name__ == "__main__":
    unittest.main()

import unittest

import numpy as np

from vocallab.scoring import build_scoring_modes
from vocallab.transposition import detect_transposition


class ScoringModeTests(unittest.TestCase):
    def test_coherent_key_shift_defaults_to_adjusted_accuracy(self) -> None:
        reference = np.array([60, 62, 64, 65, 67], dtype=float)
        user = reference - 6
        confidence = np.ones(reference.shape)
        scoring = build_scoring_modes(
            reference,
            user,
            confidence,
            detect_transposition(reference, user, confidence),
        )
        self.assertEqual(scoring["default_mode"], "transposition_adjusted")
        self.assertEqual(
            scoring["modes"]["original_pitch"]["metrics"][
                "median_absolute_cents"
            ],
            600,
        )
        self.assertEqual(
            scoring["modes"]["transposition_adjusted"]["metrics"][
                "median_absolute_cents"
            ],
            0,
        )

    def test_octave_invariant_mode_reports_placement_separately(self) -> None:
        reference = np.array([60, 62, 64, 65, 67], dtype=float)
        user = reference - 12
        scoring = build_scoring_modes(
            reference,
            user,
            np.ones(reference.shape),
            detect_transposition(reference, user),
        )
        metrics = scoring["modes"]["octave_invariant"]["metrics"]
        self.assertEqual(metrics["median_absolute_cents"], 0)
        self.assertEqual(metrics["median_octave_displacement"], -1)

    def test_interval_contour_ignores_starting_key(self) -> None:
        reference = np.array([60, 62, 64, 65, 67], dtype=float)
        user = reference + 4
        scoring = build_scoring_modes(
            reference,
            user,
            np.ones(reference.shape),
            detect_transposition(reference, user),
        )
        metrics = scoring["modes"]["interval_contour"]["metrics"]
        self.assertEqual(metrics["median_absolute_interval_error_cents"], 0)
        self.assertEqual(metrics["contour_direction_agreement_percentage"], 100)

    def test_unreliable_detection_does_not_default_to_adjusted_score(self) -> None:
        reference = np.full(10, 60.0)
        user = np.concatenate([np.full(5, 60.0), np.full(5, 48.0)])
        detected = detect_transposition(reference, user)
        scoring = build_scoring_modes(
            reference,
            user,
            np.ones(reference.shape),
            detected,
        )
        self.assertFalse(scoring["transposition_reliable"])
        self.assertEqual(scoring["default_mode"], "original_pitch")
        self.assertFalse(
            scoring["modes"]["transposition_adjusted"]["available"]
        )

    def test_manual_shift_enables_adjusted_scoring_without_reanalysis(self) -> None:
        reference = np.full(10, 60.0)
        user = np.concatenate([np.full(5, 60.0), np.full(5, 48.0)])
        scoring = build_scoring_modes(
            reference,
            user,
            np.ones(reference.shape),
            detect_transposition(reference, user),
            selected_shift=-12,
        )
        self.assertEqual(scoring["shift_source"], "manual")
        self.assertTrue(scoring["transposition_reliable"])
        self.assertEqual(scoring["default_mode"], "transposition_adjusted")


if __name__ == "__main__":
    unittest.main()

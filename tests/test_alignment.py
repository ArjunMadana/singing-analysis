import unittest

import numpy as np

from vocallab.alignment import (
    calibrated_alignment_confidence,
    constant_offset_alignment,
    estimate_global_offset,
    estimate_microphone_latency,
    reconcile_latency_estimates,
)


class AlignmentTests(unittest.TestCase):
    def test_global_offset_finds_delayed_user(self) -> None:
        reference = np.zeros(300)
        reference[[30, 80, 150, 220]] = [1.0, 0.8, 1.0, 0.7]
        user = np.pad(reference, (12, 0))[: reference.size]
        offset, confidence = estimate_global_offset(reference, user, 0.01, 1.0)
        self.assertAlmostEqual(offset, 0.12, places=2)
        self.assertGreater(confidence, 0.8)

    def test_constant_path_never_invents_local_speed_changes(self) -> None:
        x = np.linspace(0, 8 * np.pi, 400)
        reference = np.square(np.sin(x)) + 0.1
        user = np.interp(np.linspace(0, 399, 420), np.arange(400), reference)
        alignment = constant_offset_alignment(reference, user, 0.01, 0.0)
        self.assertTrue(
            np.array_equal(
                np.diff(alignment.reference_indices),
                np.diff(alignment.user_indices),
            )
        )
        self.assertEqual(alignment.profile, "constant-offset")
        self.assertGreater(alignment.confidence, 0.0)
        self.assertLess(
            alignment.confidence,
            0.5,
            "A tempo mismatch must reduce confidence instead of being warped away.",
        )

    def test_partial_reference_aligns_only_shared_overlap(self) -> None:
        reference = np.sin(np.linspace(0, 20, 450))
        user = np.concatenate(
            [
                np.zeros(30),
                reference,
                np.cos(np.linspace(0, 20, 550)),
            ]
        )
        alignment = constant_offset_alignment(
            reference,
            user,
            hop_seconds=0.01,
            global_offset_seconds=0.3,
        )
        self.assertEqual(alignment.reference_indices[-1], 449)
        self.assertGreater(alignment.user_indices[-1], 450)
        self.assertLessEqual(alignment.user_indices[-1], 480)

    def test_microphone_latency_ignores_global_transposition(self) -> None:
        reference = np.repeat([60.0, 64.0, 62.0, 67.0, 65.0], 40)
        user = np.concatenate([np.full(100, np.nan), reference + 3])
        indexes = np.arange(reference.size)
        latency, confidence = estimate_microphone_latency(
            reference, user, indexes, indexes, 0.01
        )
        self.assertAlmostEqual(latency, 1.0, delta=0.03)
        self.assertGreater(confidence, 0.1)

    def test_calibrated_confidence_does_not_equate_a_path_with_certainty(self) -> None:
        confidence, coverage = calibrated_alignment_confidence(
            1.0,
            1.0,
            0.2,
            np.arange(80),
            np.arange(80),
            100,
            100,
        )
        self.assertAlmostEqual(coverage, 0.8)
        self.assertLess(confidence, 0.8)

    def test_contaminated_reference_can_prefer_stronger_energy_latency(self) -> None:
        latency, confidence, method = reconcile_latency_estimates(
            pitch_seconds=0.39,
            pitch_confidence=0.45,
            energy_seconds=0.98,
            energy_confidence=0.85,
            reference_quality=0.35,
        )
        self.assertAlmostEqual(latency, 0.98)
        self.assertEqual(method, "energy-envelope")
        self.assertGreater(confidence, 0.3)


if __name__ == "__main__":
    unittest.main()

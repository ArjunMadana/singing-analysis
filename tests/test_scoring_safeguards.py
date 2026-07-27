import unittest

import numpy as np

from vocallab.models import NoteEvent, TranspositionResult
from vocallab.scoring import build_discrepancies


class ScoringSafeguardTests(unittest.TestCase):
    def test_full_mix_octave_error_is_not_presented_as_authoritative(self) -> None:
        note = NoteEvent(0.0, 1.0, 0.1, 0.9, 60, 0, 0.9, "phrase-1")
        times = np.arange(0.1, 0.9, 0.1)
        reference = np.full(times.shape, 60.0)
        user = np.full(times.shape, 72.0)
        shift = TranspositionResult(0, 1, 0, 100, 0, 0)
        discrepancies = build_discrepancies(
            [note],
            np.arange(0.0, 1.1, 0.1),
            reference,
            user,
            np.arange(1, 9),
            shift,
            np.ones(times.shape),
            reference_quality=0.35,
            alignment_quality=0.8,
        )
        self.assertEqual(discrepancies[0].kind, "low-confidence reference")
        self.assertTrue(discrepancies[0].provisional)
        self.assertLessEqual(discrepancies[0].confidence, 0.2)
        self.assertNotIn("1200", discrepancies[0].explanation)


if __name__ == "__main__":
    unittest.main()

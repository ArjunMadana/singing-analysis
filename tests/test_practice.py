import unittest

from vocallab.models import NoteEvent
from vocallab.practice import build_practice_targets


class PracticeTargetTests(unittest.TestCase):
    def test_groups_adjacent_measurements_and_builds_musical_loop(self) -> None:
        notes = [
            NoteEvent(30.8, 31.4, 30.9, 31.3, 60, 0, 0.9, "phrase-1"),
            NoteEvent(31.5, 32.1, 31.6, 32.0, 62, 0, 0.9, "phrase-1"),
            NoteEvent(32.17, 32.76, 32.25, 32.65, 64, 0, 0.9, "phrase-1"),
        ]
        discrepancies = [
            {
                "id": "d1",
                "kind": "consistently flat",
                "start_seconds": 31.5,
                "end_seconds": 32.09,
                "confidence": 0.8,
                "provisional": False,
            },
            {
                "id": "d2",
                "kind": "consistently flat",
                "start_seconds": 32.17,
                "end_seconds": 32.76,
                "confidence": 0.7,
                "provisional": False,
            },
        ]
        mapping = {
            "canonical_time": [30.0, 34.0],
            "reference_time": [30.0, 34.0],
            "user_time": [31.0, 35.0],
        }
        targets = build_practice_targets(discrepancies, notes, mapping)
        self.assertEqual(len(targets), 1)
        target = targets[0]
        self.assertEqual(target["discrepancy_ids"], ["d1", "d2"])
        self.assertGreaterEqual(
            target["loop_end_seconds"] - target["loop_start_seconds"], 2.5
        )
        self.assertLessEqual(
            target["loop_end_seconds"] - target["loop_start_seconds"], 6.0
        )
        self.assertAlmostEqual(
            target["mapped_user_loop_start_seconds"],
            target["loop_start_seconds"] + 1.0,
        )


if __name__ == "__main__":
    unittest.main()

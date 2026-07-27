import unittest

import numpy as np

from vocallab.models import AlignmentResult, PitchTrack
from vocallab.report import _mapped_loop_range


def _track(times: np.ndarray) -> PitchTrack:
    values = np.full(times.shape, 60.0)
    return PitchTrack(
        time_seconds=times,
        frequency_hz=values,
        raw_midi=values,
        corrected_midi=values,
        smoothed_midi=values,
        cents=np.zeros(times.shape),
        voicing_probability=np.ones(times.shape),
        confidence=np.ones(times.shape),
        rms=np.ones(times.shape),
        tracker="test",
    )


class ReportLoopTests(unittest.TestCase):
    def test_loop_range_maps_to_current_take_timeline(self) -> None:
        reference = _track(np.arange(10, dtype=float))
        user = _track(np.arange(10, dtype=float))
        alignment = AlignmentResult(
            global_offset_seconds=2.0,
            reference_indices=np.arange(8),
            user_indices=np.arange(2, 10),
            confidence=1.0,
            profile="performance",
        )
        start, end = _mapped_loop_range(2.0, 4.0, reference, user, alignment)
        self.assertEqual((start, end), (4.0, 6.0))


if __name__ == "__main__":
    unittest.main()

import unittest

import numpy as np

from vocallab.visualization import playback_mapping_quality


class PlaybackMappingQualityTests(unittest.TestCase):
    def test_constant_offset_partial_overlap_is_safe(self) -> None:
        canonical = np.arange(0.0, 45.5, 0.5)
        mapping = {
            "canonical_time": canonical.tolist(),
            "reference_time": (canonical + 3.25).tolist(),
            "user_time": (canonical + 3.55).tolist(),
        }
        quality = playback_mapping_quality(mapping)
        self.assertTrue(quality["full_alignment_safe"])

    def test_forced_short_to_long_alignment_is_unsafe(self) -> None:
        canonical = np.arange(0.0, 45.5, 0.5)
        forced = np.linspace(3.25, 102.0, canonical.size)
        mapping = {
            "canonical_time": canonical.tolist(),
            "reference_time": forced.tolist(),
            "user_time": (forced + 0.3).tolist(),
        }
        quality = playback_mapping_quality(mapping)
        self.assertFalse(quality["full_alignment_safe"])
        self.assertGreater(
            quality["sources"]["reference_time"]["maximum_rate"],
            quality["maximum_allowed_rate"],
        )


if __name__ == "__main__":
    unittest.main()

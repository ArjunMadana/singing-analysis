import tempfile
import unittest
from pathlib import Path

from vocallab.cache import ArtifactCache, CacheKey, invalidated_stages


class CacheTests(unittest.TestCase):
    def test_key_changes_for_output_affecting_parameter(self) -> None:
        first = CacheKey("score", {"pitch": "abc"}, {"tolerance": 25}, "v1")
        second = CacheKey("score", {"pitch": "abc"}, {"tolerance": 50}, "v1")
        self.assertNotEqual(first.digest, second.digest)

    def test_scoring_change_does_not_invalidate_pitch(self) -> None:
        invalidated = invalidated_stages("score")
        self.assertIn("report", invalidated)
        self.assertNotIn("pitch-user", invalidated)
        self.assertNotIn("separate", invalidated)

    def test_tracker_change_invalidates_downstream_only(self) -> None:
        invalidated = invalidated_stages("pitch-reference")
        self.assertIn("segment", invalidated)
        self.assertIn("align", invalidated)
        self.assertIn("score", invalidated)
        self.assertNotIn("extract", invalidated)

    def test_manifest_requires_all_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = ArtifactCache(Path(directory))
            key = CacheKey("extract", {"source": "abc"}, {}, "v1")
            output = cache.path(key, ".wav")
            output.write_bytes(b"data")
            cache.record(key, [output], {})
            self.assertTrue(cache.is_hit(key, [output]))
            output.unlink()
            self.assertFalse(cache.is_hit(key, [output]))


if __name__ == "__main__":
    unittest.main()


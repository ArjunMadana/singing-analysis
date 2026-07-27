import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vocallab.errors import VocalLabError
from vocallab.project import ProjectStore, SCHEMA_VERSION


class ProjectTests(unittest.TestCase):
    def test_creation_applies_schema_and_reopens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "song"
            store = ProjectStore.create(root, "Synthetic", "Test")
            with store.transaction() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, SCHEMA_VERSION)
            self.assertEqual(ProjectStore.open(root).root, root.resolve())

    def test_creation_reports_unwritable_location(self) -> None:
        with patch.object(Path, "mkdir", side_effect=PermissionError):
            with self.assertRaisesRegex(VocalLabError, "writable location"):
                ProjectStore.create(Path("denied"), "Synthetic", "Test")

    def test_playback_offset_is_bounded_and_persisted_per_take(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "take.bin"
            source.write_bytes(b"fixture")
            store = ProjectStore.create(root / "song", "Synthetic", "Test")
            take_id = store.add_take(source, 0, 1, {"audio_streams": []})
            self.assertEqual(store.get_take(take_id)["playback_offset_seconds"], 0.0)
            store.save_playback_offset(take_id, 0.61)
            self.assertAlmostEqual(
                store.get_take(take_id)["playback_offset_seconds"], 0.61
            )
            with self.assertRaisesRegex(VocalLabError, "between"):
                store.save_playback_offset(take_id, 2.01)


if __name__ == "__main__":
    unittest.main()

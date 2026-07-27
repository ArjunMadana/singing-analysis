import unittest
from unittest.mock import patch

from vocallab.errors import AnalysisError
from vocallab.separation import ReferenceMixFallback, choose_separator


class SeparationTests(unittest.TestCase):
    def test_auto_mode_uses_safe_fallback_without_downloading_models(self) -> None:
        separator = choose_separator("auto")

        self.assertIsInstance(separator, ReferenceMixFallback)

    def test_explicit_demucs_mode_requires_the_pinned_installation(self) -> None:
        with patch("vocallab.separation.importlib.util.find_spec", return_value=None):
            with self.assertRaises(AnalysisError):
                choose_separator("demucs")


if __name__ == "__main__":
    unittest.main()

import json
import unittest
import tempfile
from pathlib import Path
from core.atomic_write import atomic_write_text, atomic_write_json


class TestAtomicWrite(unittest.TestCase):
    """Unit tests verifying atomic write utilities and data safety."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_atomic_write_text(self):
        """Tests that text is atomically written and readable without temp file remnants."""
        target_file = self.temp_path / "subfolder" / "report.md"
        content = "# Atomic Write Report\n\nContent is safe."

        self.assertTrue(atomic_write_text(target_file, content))
        self.assertTrue(target_file.exists())
        self.assertEqual(target_file.read_text(encoding="utf-8"), content)

        # Ensure no temp files remained
        sibling_files = list(target_file.parent.iterdir())
        self.assertEqual(len(sibling_files), 1)

    def test_atomic_write_json(self):
        """Tests that JSON is atomically serialized and formatted properly."""
        target_file = self.temp_path / "project_state.json"
        data = {
            "name": "BoxAlpha",
            "loot": [{"id": "loot_1", "title": "Cred"}],
            "clipboard_history": []
        }

        self.assertTrue(atomic_write_json(target_file, data))
        self.assertTrue(target_file.exists())

        with open(target_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        self.assertEqual(loaded, data)

        # Overwrite atomically
        data["name"] = "BoxAlphaModified"
        self.assertTrue(atomic_write_json(target_file, data))
        with open(target_file, "r", encoding="utf-8") as f:
            reloaded = json.load(f)
        self.assertEqual(reloaded["name"], "BoxAlphaModified")


if __name__ == "__main__":
    unittest.main()

import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
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

    def test_restrictive_permissions_posix(self):
        """Tests that written files have 0o600 permissions on POSIX systems."""
        import os
        import stat
        target_file = self.temp_path / "secret.json"
        atomic_write_json(target_file, {"key": "val"})
        if os.name == 'posix':
            file_stat = target_file.stat().st_mode
            self.assertEqual(stat.S_IMODE(file_stat), 0o600)

    def test_interrupted_write_keeps_previous_project_state_readable(self):
        """An abrupt stop before replace must never leave a partially written state file."""
        target_file = self.temp_path / "project_state.json"
        previous_state = {"name": "BoxAlpha", "loot": [{"id": "loot_old"}]}
        interrupted_state = {"name": "BoxAlpha", "loot": [{"id": "loot_new"}]}
        atomic_write_json(target_file, previous_state)

        with patch("core.atomic_write._replace_file_with_retry", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                atomic_write_json(target_file, interrupted_state)

        # This mirrors the next application launch: the committed file remains
        # valid and contains either the old complete state or, after a real
        # completed replace, the new complete state—never a partial JSON blob.
        with target_file.open("r", encoding="utf-8") as state_file:
            self.assertEqual(json.load(state_file), previous_state)


if __name__ == "__main__":
    unittest.main()

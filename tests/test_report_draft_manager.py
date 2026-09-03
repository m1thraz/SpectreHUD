"""Tests for core/reporting/draft_manager.py (Tier 0 pure logic)."""

import tempfile
import unittest
from pathlib import Path

from core.reporting.draft_manager import (
    discard_draft,
    get_draft,
    get_draft_path,
    has_recoverable_draft,
    save_draft,
)


class TestReportDraftManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_get_draft(self):
        content = "# In-flight Notes\nDiscovered open port 8080."
        ok = save_draft(self.project_dir, content)
        self.assertTrue(ok)
        self.assertTrue(get_draft_path(self.project_dir).exists())

        res = get_draft(self.project_dir)
        self.assertIsNotNone(res)
        draft_text, mtime = res
        self.assertEqual(draft_text, content)
        self.assertIsNotNone(mtime)

    def test_has_recoverable_draft_different_content(self):
        saved = "# Saved Report\nOnly port 22 found."
        draft = "# Saved Report\nOnly port 22 found.\nAlso port 80 found!"

        save_draft(self.project_dir, draft)
        self.assertTrue(has_recoverable_draft(self.project_dir, saved))

    def test_has_recoverable_draft_identical_content(self):
        saved = "# Saved Report\nIdentical content."
        save_draft(self.project_dir, saved)
        self.assertFalse(has_recoverable_draft(self.project_dir, saved))

    def test_discard_draft(self):
        save_draft(self.project_dir, "Draft content")
        self.assertTrue(get_draft_path(self.project_dir).exists())

        removed = discard_draft(self.project_dir)
        self.assertTrue(removed)
        self.assertFalse(get_draft_path(self.project_dir).exists())

        # Second discard is safe no-op
        removed_again = discard_draft(self.project_dir)
        self.assertFalse(removed_again)


if __name__ == "__main__":
    unittest.main()

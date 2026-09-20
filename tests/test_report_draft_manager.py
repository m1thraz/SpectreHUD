"""Tests for core/reporting/draft_manager.py (Tier 0 pure logic)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.reporting import (
    DraftDiscardStatus,
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
        self.assertIs(removed.status, DraftDiscardStatus.REMOVED)
        self.assertFalse(get_draft_path(self.project_dir).exists())

        # Second discard is safe no-op
        removed_again = discard_draft(self.project_dir)
        self.assertIs(removed_again.status, DraftDiscardStatus.NOT_FOUND)

    def test_discard_draft_reports_cleanup_failure(self):
        save_draft(self.project_dir, "Draft content")

        with patch.object(Path, "unlink", side_effect=PermissionError("access denied")):
            result = discard_draft(self.project_dir)

        self.assertIs(result.status, DraftDiscardStatus.FAILED)
        self.assertIn("access denied", result.detail)
        self.assertTrue(get_draft_path(self.project_dir).exists())

    def test_draft_older_than_saved_report_is_not_recoverable(self):
        draft_path = get_draft_path(self.project_dir)
        report_path = self.project_dir / "report.md"
        save_draft(self.project_dir, "# Stale Draft")
        report_path.write_text("# Newer Report", encoding="utf-8")
        os.utime(draft_path, ns=(1_000_000_000, 1_000_000_000))
        os.utime(report_path, ns=(2_000_000_000, 2_000_000_000))

        self.assertFalse(has_recoverable_draft(self.project_dir, "# Newer Report"))


if __name__ == "__main__":
    unittest.main()

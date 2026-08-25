import os
import unittest
import tempfile
from pathlib import Path
from core.project_manager import ProjectManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.report_file_manager import ReportFileManager

class TestReportFileManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path / "config")
        os.environ["SPECTRE_PROJECTS_DIR"] = str(self.temp_path / "projects")

        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.loot_mgr = LootManager(storage_file=self.temp_path / "config" / "loot.json")
        self.clip_watcher = ClipboardWatcher(storage_file=self.temp_path / "config" / "clip.json")
        self.report_mgr = ReportFileManager(self.project_mgr)

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        os.environ.pop("SPECTRE_PROJECTS_DIR", None)
        self.temp_dir.cleanup()

    def test_paths(self):
        self.project_mgr.create_project("BoxBeta")
        rep_path = self.report_mgr.get_report_path("BoxBeta")
        bak_path = self.report_mgr.get_backup_path("BoxBeta")

        self.assertEqual(rep_path.name, "report.md")
        self.assertEqual(bak_path.name, "report.md.bak")
        self.assertFalse(self.report_mgr.exists("BoxBeta"))

    def test_save_and_load(self):
        self.project_mgr.create_project("BoxBeta")
        content = "# Custom Report Content"
        ok = self.report_mgr.save(content, "BoxBeta")
        self.assertTrue(ok)
        self.assertTrue(self.report_mgr.exists("BoxBeta"))

        loaded = self.report_mgr.load("BoxBeta")
        self.assertEqual(loaded, content)

    def test_backup(self):
        self.project_mgr.create_project("BoxBeta")
        self.report_mgr.save("# Version 1", "BoxBeta")
        
        ok = self.report_mgr.backup("BoxBeta")
        self.assertTrue(ok)
        
        bak_path = self.report_mgr.get_backup_path("BoxBeta")
        self.assertTrue(bak_path.exists())
        self.assertEqual(bak_path.read_text(encoding="utf-8"), "# Version 1")

    def test_regenerate_with_existing_content_creates_backup(self):
        self.project_mgr.create_project("BoxBeta")
        self.report_mgr.save("# Existing Manual Content", "BoxBeta")
        self.loot_mgr.add_entry("flag", "User Flag", "THM{flag_123}", category="access")

        new_content = self.report_mgr.regenerate(self.loot_mgr, self.clip_watcher, "BoxBeta")
        self.assertIn("THM{flag_123}", new_content)

        # Check that backup was created
        bak_path = self.report_mgr.get_backup_path("BoxBeta")
        self.assertTrue(bak_path.exists())
        self.assertEqual(bak_path.read_text(encoding="utf-8"), "# Existing Manual Content")

    def test_regenerate_without_existing_content_creates_no_backup(self):
        self.project_mgr.create_project("FreshBox")
        self.assertFalse(self.report_mgr.exists("FreshBox"))

        new_content = self.report_mgr.regenerate(self.loot_mgr, self.clip_watcher, "FreshBox")
        self.assertIn("## 🔍 1. Reconnaissance & Enumeration", new_content)

        # No backup should have been created
        bak_path = self.report_mgr.get_backup_path("FreshBox")
        self.assertFalse(bak_path.exists())

if __name__ == "__main__":
    unittest.main()

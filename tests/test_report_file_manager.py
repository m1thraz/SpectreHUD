import os
import sys
import unittest
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.project_manager import ProjectManager
from core.loot_manager import LootManager
from core.report_file_manager import ReportFileManager


class FakeClipboardWatcher:
    """Minimal PyQt6-free stub for ClipboardWatcher."""
    def __init__(self, history: Optional[List[Dict[str, Any]]] = None):
        self.history = history or []

    def get_history(self, target_ip: Optional[str] = None, filter_type: str = "all", search_query: str = "") -> List[Dict[str, Any]]:
        return self.history


class TestReportFileManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path / "config")
        os.environ["SPECTRE_PROJECTS_DIR"] = str(self.temp_path / "projects")

        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.loot_mgr = LootManager(storage_file=self.temp_path / "config" / "loot.json")
        self.clip_watcher = FakeClipboardWatcher()
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
        self.assertIn("## 1. Reconnaissance & Enumeration", new_content)

        # No backup should have been created
        bak_path = self.report_mgr.get_backup_path("FreshBox")
        self.assertFalse(bak_path.exists())

    def test_regenerate_fails_closed_if_backup_fails(self):
        """Invariant: If backup fails, regenerate MUST raise ReportBackupError and NOT overwrite report.md."""
        from unittest.mock import patch
        from core.report_file_manager import ReportBackupError

        self.project_mgr.create_project("ProtectedBox")
        original_text = "# Critical Handcrafted Report"
        self.report_mgr.save(original_text, "ProtectedBox")

        # Mock backup to simulate a disk failure
        with patch.object(self.report_mgr, "backup", return_value=False):
            with self.assertRaises(ReportBackupError):
                self.report_mgr.regenerate(self.loot_mgr, self.clip_watcher, "ProtectedBox")

        # Invariant check: report.md MUST NOT be modified or destroyed
        self.assertEqual(self.report_mgr.load("ProtectedBox"), original_text)

    def test_regenerate_fails_closed_if_save_fails(self):
        """Invariant: If save fails after build, regenerate MUST raise ReportSaveError and not return false-success."""
        from unittest.mock import patch
        from core.report_file_manager import ReportSaveError

        self.project_mgr.create_project("SaveFailBox")
        
        # Mock save to simulate disk write failure during regenerate
        with patch.object(self.report_mgr, "save", return_value=False):
            with self.assertRaises(ReportSaveError):
                self.report_mgr.regenerate(self.loot_mgr, self.clip_watcher, "SaveFailBox")

    def test_report_builder_atomic_export(self):
        """Tests that ReportBuilder.export writes report atomically to output_path."""
        from core.report_builder import ReportBuilder

        builder = ReportBuilder(loot_manager=self.loot_mgr, clipboard_watcher=self.clip_watcher)
        export_file = self.temp_path / "custom_export.md"
        msg = builder.export(export_file, project_name="ExportTest")

        self.assertIn("erfolgreich", msg)
        self.assertTrue(export_file.exists())
        self.assertIn("Pentest Report: ExportTest", export_file.read_text(encoding="utf-8"))

    def test_report_document_resolves_loot_images(self):
        """Tests that ReportDocument successfully resolves project-relative loot screenshots."""
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QImage, QTextDocument, QColor
        from ui.report_editor_tab import ReportDocument

        self.project_mgr.create_project("BoxImageTest")
        proj_dir = self.project_mgr.get_project_dir("BoxImageTest")
        loot_dir = proj_dir / "loot"
        loot_dir.mkdir(exist_ok=True)
        img_file = loot_dir / "screenshot_20260826_120000.png"

        test_img = QImage(200, 100, QImage.Format.Format_RGB32)
        test_img.fill(QColor("blue"))
        self.assertTrue(test_img.save(str(img_file), "PNG"))

        doc = ReportDocument(project_dir=proj_dir)
        doc.setMarkdown("![Screenshot](loot/screenshot_20260826_120000.png)")

        loaded = doc.loadResource(int(QTextDocument.ResourceType.ImageResource), QUrl("loot/screenshot_20260826_120000.png"))
        self.assertIsNotNone(loaded)
        self.assertIsInstance(loaded, QImage)
        self.assertEqual(loaded.width(), 200)
        self.assertEqual(loaded.height(), 100)


if __name__ == "__main__":
    unittest.main()

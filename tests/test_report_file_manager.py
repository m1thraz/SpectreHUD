import os
import sys
import unittest
import pytest
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.project import ProjectManager
from core.loot.manager import LootManager
from core.reporting.file_manager import ReportFileManager
from core.validators import MAX_REPORT_FILE_SIZE


class FakeClipboardHistory:
    """Minimal stub for clipboard history."""

    def __init__(self, history: Optional[List[Dict[str, Any]]] = None):
        self.history = history or []

    def get_history(
        self, target_ip: Optional[str] = None, filter_type: str = "all", search_query: str = ""
    ) -> List[Dict[str, Any]]:
        return self.history


class TestReportFileManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path / "config")
        os.environ["SPECTRE_PROJECTS_DIR"] = str(self.temp_path / "projects")

        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.loot_mgr = LootManager(storage_file=self.temp_path / "config" / "loot.json")
        self.clip_watcher = FakeClipboardHistory()
        self.report_mgr = ReportFileManager(self.project_mgr)

    def tearDown(self):
        import logging
        import gc

        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        os.environ.pop("SPECTRE_PROJECTS_DIR", None)
        for name in list(logging.Logger.manager.loggerDict.keys()) + ["spectrehud", ""]:
            log_obj = logging.getLogger(name)
            for h in list(log_obj.handlers):
                try:
                    log_obj.removeHandler(h)
                    h.close()
                except Exception:
                    pass
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

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

    def test_save_rejects_report_larger_than_its_read_limit(self):
        """The configured report-size product limit applies consistently to writes."""
        self.project_mgr.create_project("OversizedReport")
        content = "x" * (MAX_REPORT_FILE_SIZE + 1)

        self.assertFalse(self.report_mgr.save(content, "OversizedReport"))
        self.assertFalse(self.report_mgr.exists("OversizedReport"))

    def test_failed_save_preserves_previous_report(self):
        """A rejected replacement must leave the last committed report intact."""
        self.project_mgr.create_project("ProtectedReport")
        previous_content = "# Important report\nThis content must survive."
        self.assertTrue(self.report_mgr.save(previous_content, "ProtectedReport"))

        self.assertFalse(self.report_mgr.save("x" * (MAX_REPORT_FILE_SIZE + 1), "ProtectedReport"))
        self.assertEqual(self.report_mgr.load("ProtectedReport"), previous_content)

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
        from core.reporting.file_manager import ReportBackupError

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
        from core.reporting.file_manager import ReportSaveError

        self.project_mgr.create_project("SaveFailBox")

        # Mock save to simulate disk write failure during regenerate
        with patch.object(self.report_mgr, "save", return_value=False):
            with self.assertRaises(ReportSaveError):
                self.report_mgr.regenerate(self.loot_mgr, self.clip_watcher, "SaveFailBox")

    def test_report_builder_atomic_export(self):
        """Tests that ReportBuilder.export writes report atomically to output_path."""
        from core.reporting.builder import ReportBuilder

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
        from ui.report.preview import ReportDocument

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

        loaded = doc.loadResource(
            int(QTextDocument.ResourceType.ImageResource),
            QUrl("loot/screenshot_20260826_120000.png"),
        )
        self.assertIsNotNone(loaded)
        self.assertIsInstance(loaded, QImage)
        self.assertEqual(loaded.width(), 200)
        self.assertEqual(loaded.height(), 100)

    def test_append_missing_loot_creates_backup_and_preserves_existing_text(self):
        """Ticket 19 & 31: append_missing_loot creates a backup and injects missing loot."""
        self.project_mgr.create_project("SyncBox")
        initial_text = "# Pentest Report\n\n## 1. Reconnaissance & Enumeration\n\n*Keine Einträge in dieser Phase.*\n\n_Eigene Anmerkungen zu dieser Phase:_\n\n> User note\n"
        self.report_mgr.save(initial_text, "SyncBox")
        self.loot_mgr.add_entry("note", "Port Scan", "Found port 22 open", category="recon")

        result = self.report_mgr.append_missing_loot(self.loot_mgr, "SyncBox")
        self.assertEqual(result.added_count, 1)
        self.assertFalse(result.used_fallback)

        # Backup was created containing initial_text
        bak_path = self.report_mgr.get_backup_path("SyncBox")
        self.assertTrue(bak_path.exists())
        self.assertEqual(bak_path.read_text(encoding="utf-8"), initial_text)

        # Loaded text contains both user note and new loot entry
        loaded = self.report_mgr.load("SyncBox")
        self.assertIn("> User note", loaded)
        self.assertIn("Port Scan", loaded)

    def test_append_missing_loot_noop_creates_no_backup(self):
        """Ticket 23: When nothing is missing, no backup is created and no disk write occurs."""
        self.project_mgr.create_project("NoopBox")
        self.report_mgr.save("# Existing Report", "NoopBox")

        # No loot in loot_mgr
        result = self.report_mgr.append_missing_loot(self.loot_mgr, "NoopBox")
        self.assertEqual(result.added_count, 0)
        self.assertFalse(self.report_mgr.get_backup_path("NoopBox").exists())

    def test_append_missing_loot_fails_closed_if_backup_fails(self):
        """Ticket 21: If backup fails, append_missing_loot raises ReportBackupError and leaves file intact."""
        from unittest.mock import patch
        from core.reporting.file_manager import ReportBackupError

        self.project_mgr.create_project("BackupFailBox")
        original_text = "# Original Protected Text"
        self.report_mgr.save(original_text, "BackupFailBox")
        self.loot_mgr.add_entry("flag", "Root Flag", "THM{root_flag}", category="access")

        with patch.object(self.report_mgr, "backup", return_value=False):
            with self.assertRaises(ReportBackupError):
                self.report_mgr.append_missing_loot(self.loot_mgr, "BackupFailBox")

        # File was NOT modified
        self.assertEqual(self.report_mgr.load("BackupFailBox"), original_text)

    def test_append_missing_loot_fails_closed_if_save_fails(self):
        """Ticket 22: If saving fails, append_missing_loot raises ReportSaveError."""
        from unittest.mock import patch
        from core.reporting.file_manager import ReportSaveError

        self.project_mgr.create_project("SaveFailBox")
        original_text = "# Original Text"
        self.report_mgr.save(original_text, "SaveFailBox")
        self.loot_mgr.add_entry("flag", "User Flag", "THM{user_flag}", category="access")

        with patch.object(self.report_mgr, "save", return_value=False):
            with self.assertRaises(ReportSaveError):
                self.report_mgr.append_missing_loot(self.loot_mgr, "SaveFailBox")

    @pytest.mark.integration
    def test_report_editor_export_button_dispatches_html_export(self):
        """Tests that the unified Export button can dispatch to HTML export."""
        from unittest.mock import MagicMock, patch
        from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
        from ui.coordinators.export_coordinator import ExportCoordinator
        from ui.report_editor_tab import ReportEditorTab

        app = QApplication.instance() or QApplication([])
        self.project_mgr.create_project("BoxHtmlTest")
        tab = ReportEditorTab(
            report_file_manager=self.report_mgr,
            loot_manager=self.loot_mgr,
            clipboard_history=self.clip_watcher,
            export_coordinator=ExportCoordinator(
                project_manager=self.project_mgr,
                loot_manager=self.loot_mgr,
                history_ctrl=MagicMock(),
                target_provider=lambda: "",
                config_manager=MagicMock(),
            ),
        )
        tab.load_project("BoxHtmlTest")
        tab.editor.setPlainText("# HTML Export Test\nContent goes here.")

        self.assertTrue(hasattr(tab, "btn_export"))
        self.assertEqual(tab.btn_export.text(), "Export...")

        out_html = self.temp_path / "exported_test.html"
        with (
            patch.object(
                QFileDialog, "getSaveFileName", return_value=(str(out_html), "HTML (*.html)")
            ),
            patch.object(tab, "_select_export_type", return_value="html"),
            patch.object(tab, "_select_html_export_theme", return_value="light"),
            patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.No),
        ):
            tab.btn_export.click()

        self.assertTrue(out_html.exists())
        content = out_html.read_text(encoding="utf-8")
        self.assertIn("<h1>HTML Export Test</h1>", content)
        self.assertIn("BoxHtmlTest", content)
        self.assertIn("Light export theme", content)

        tab.deleteLater()

    def test_import_image_inside_and_outside_project(self):
        self.project_mgr.create_project("ImgTest")
        proj_dir = self.project_mgr.get_project_dir("ImgTest")

        # 1. Image already inside project directory
        screenshots_dir = proj_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        local_img = screenshots_dir / "local.png"
        local_img.write_bytes(b"dummy")

        rel_path = self.report_mgr.import_image(local_img, "ImgTest")
        self.assertEqual(rel_path, "screenshots/local.png")

        # 2. Image outside project directory
        outside_dir = self.temp_path / "downloads"
        outside_dir.mkdir(parents=True, exist_ok=True)
        external_img = outside_dir / "external.png"
        external_img.write_bytes(b"payload")

        rel_path_imported = self.report_mgr.import_image(external_img, "ImgTest")
        self.assertEqual(rel_path_imported, "screenshots/external.png")
        self.assertTrue((screenshots_dir / "external.png").exists())
        self.assertEqual((screenshots_dir / "external.png").read_bytes(), b"payload")



if __name__ == "__main__":
    unittest.main()

import os
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QMimeData, QUrl

from core.project_manager import ProjectManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.report_file_manager import ReportFileManager
from core.i18n import t
from ui.report_editor_tab import AUTOSAVE_INTERVAL_MS, ReportEditorTab, ViewMode, ReportPreviewEdit, ReportGenerationDialog

app = QApplication.instance() or QApplication(sys.argv)


class TestReportEditorTab(unittest.TestCase):
    """Tests ReportEditorTab ViewModes, editable live preview, commit, and safety guards."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path / "config")
        os.environ["SPECTRE_PROJECTS_DIR"] = str(self.temp_path / "projects")

        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.project_mgr.create_project("TestBox", target_ip="10.10.10.42")
        self.loot_mgr = LootManager(storage_file=self.temp_path / "config" / "loot.json")
        self.clip_watcher = ClipboardWatcher(storage_file=self.temp_path / "config" / "clip.json")
        self.report_file_mgr = ReportFileManager(self.project_mgr)

        self.tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        self.tab.load_project("TestBox")
        self.tab.show()

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        os.environ.pop("SPECTRE_PROJECTS_DIR", None)
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_initial_view_mode_is_split(self):
        """Default view mode must be SPLIT with preview read-only."""
        self.assertEqual(self.tab._view_mode, ViewMode.SPLIT)
        self.assertTrue(self.tab.editor.isVisible())
        self.assertTrue(self.tab.preview.isVisible())
        self.assertTrue(self.tab.preview.isReadOnly())
        self.assertIn("Split", self.tab.lbl_status.text())

    def test_template_selection_is_in_report_generation_dialog(self):
        """Templates are selected immediately before report generation, not in the toolbar."""
        self.assertFalse(hasattr(self.tab, "combo_templates"))

        dialog = ReportGenerationDialog(
            template_repo=self.tab.template_repo,
            selected_template=self.tab.active_template,
            has_existing_report=True,
            parent=self.tab,
        )
        self.assertGreater(dialog.combo_templates.count(), 0)
        self.assertEqual(dialog.windowTitle(), t("report.generate_title", "Generate Report from Loot"))

    def test_view_mode_switching(self):
        """Tests switching between EDITOR, PREVIEW, and SPLIT modes."""
        # 1. Switch to EDITOR mode
        self.tab._set_view_mode(ViewMode.EDITOR)
        self.assertEqual(self.tab._view_mode, ViewMode.EDITOR)
        self.assertTrue(self.tab.editor.isVisible())
        self.assertFalse(self.tab.preview.isVisible())
        self.assertTrue(self.tab.preview.isReadOnly())
        self.assertIn("Editor", self.tab.lbl_status.text())

        # 2. Switch to PREVIEW mode (editable)
        self.tab._set_view_mode(ViewMode.PREVIEW)
        self.assertEqual(self.tab._view_mode, ViewMode.PREVIEW)
        self.assertFalse(self.tab.editor.isVisible())
        self.assertTrue(self.tab.preview.isVisible())
        self.assertFalse(self.tab.preview.isReadOnly())
        self.assertIn("Live-Ansicht", self.tab.lbl_status.text())

        # 3. Cycle view mode back to EDITOR
        self.tab._cycle_view_mode()
        self.assertEqual(self.tab._view_mode, ViewMode.EDITOR)

    def test_live_preview_commit_to_markdown(self):
        """Tests that editing in PREVIEW mode commits markdown back to editor on mode switch."""
        self.tab.editor.setPlainText("# Initial Heading\n\nSome initial content.")
        self.tab.save()
        self.assertFalse(self.tab.is_dirty())

        # Enter preview mode
        self.tab._set_view_mode(ViewMode.PREVIEW)
        self.assertFalse(self.tab.preview.isReadOnly())

        # Edit rich text document directly
        cursor = self.tab.preview.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText("\n\nAppended live text.")

        # Switch to SPLIT mode -> triggers _commit_preview_to_markdown
        self.tab._set_view_mode(ViewMode.SPLIT)
        self.assertTrue(self.tab.is_dirty())
        self.assertIn("Appended live text", self.tab.editor.toPlainText())
        self.assertTrue(self.tab.preview.isReadOnly())

    def test_preview_commit_on_save(self):
        """Tests that save() automatically commits pending preview edits."""
        self.tab.editor.setPlainText("# Base Report")
        self.tab.save()

        self.tab._set_view_mode(ViewMode.PREVIEW)
        cursor = self.tab.preview.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText("\n\nSaved via preview.")

        saved = self.tab.save()
        self.assertTrue(saved)
        self.assertFalse(self.tab.is_dirty())
        self.assertIn("Saved via preview", self.tab.editor.toPlainText())

    def test_sanity_check_guard_against_truncation(self):
        """Tests that extreme content loss prompts warning and can be aborted/reverted."""
        long_content = "# Section\n\n" + ("Important pentest findings line.\n" * 20)
        self.tab.editor.setPlainText(long_content)
        self.tab.save()

        self.tab._set_view_mode(ViewMode.PREVIEW)

        # Clear almost everything in preview document (drastic reduction)
        self.tab.preview.setPlainText("Short")

        # User chooses "No" on warning dialog
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.No):
            self.tab._set_view_mode(ViewMode.SPLIT)

        # Content should be restored from baseline snapshot
        self.assertIn("Important pentest findings line", self.tab.editor.toPlainText())

    def test_report_preview_edit_blocks_image_mime_drops(self):
        """Tests that ReportPreviewEdit blocks image mime data drops."""
        edit = ReportPreviewEdit()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile("malicious.png")])
        edit.insertFromMimeData(mime)
        # Text should remain empty because image drop was rejected
        self.assertEqual(edit.toPlainText().strip(), "")

    def test_find_replace_and_autosave(self):
        self.tab.editor.setPlainText("alpha beta alpha")
        self.tab.editor.setFocus()
        self.tab._open_find_bar()
        self.tab.find_input.setText("alpha")
        self.assertTrue(self.tab.find_bar.isVisible())
        self.assertEqual(self.tab.find_count_label.text(), "2 Treffer")
        self.tab.replace_input.setText("omega")
        self.tab._replace_all()
        self.assertEqual(self.tab.editor.toPlainText(), "omega beta omega")
        self.tab._close_find_bar()
        self.assertFalse(self.tab.find_bar.isVisible())

        self.tab.report_file_manager.save = MagicMock(return_value=True)
        self.tab._set_dirty(False)
        self.tab._autosave()
        self.tab.report_file_manager.save.assert_not_called()
        self.tab._set_dirty(True)
        self.tab._autosave()
        self.tab.report_file_manager.save.assert_called_once()
        self.assertEqual(self.tab._autosave_timer.interval(), AUTOSAVE_INTERVAL_MS)

    def test_autosave_failure_is_non_modal(self):
        self.tab._set_dirty(True)
        self.tab.report_file_manager.save = MagicMock(return_value=False)
        with patch.object(QMessageBox, "exec") as message_exec:
            self.tab._autosave()
        message_exec.assert_not_called()
        self.assertTrue(self.tab.is_dirty())


if __name__ == "__main__":
    unittest.main()

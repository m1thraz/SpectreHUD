"""Tests for report crash recovery and draft snapshot mechanism in UI."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.report_file_manager import ReportFileManager
from core.reporting.draft_manager import get_draft_path, save_draft
from ui.report_editor_tab import ReportEditorTab

app = QApplication.instance() or QApplication([])


class TestReportRecoveryUI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)

        self.mock_rfm = MagicMock(spec=ReportFileManager)
        self.mock_rfm.load.return_value = "# Saved Report Content\nInitial text."
        self.mock_rfm.save.return_value = True
        self.mock_rfm.project_manager = MagicMock()
        self.mock_rfm.project_manager.get_project_dir.return_value = self.project_dir

        self.tab = ReportEditorTab(
            report_file_manager=self.mock_rfm,
            loot_manager=MagicMock(),
            clipboard_history=MagicMock(),
        )

    def tearDown(self):
        self.tab.deleteLater()
        self.temp_dir.cleanup()

    def test_load_project_with_no_draft(self):
        """When no draft exists, load_project loads disk content directly without prompt."""
        with patch.object(QMessageBox, "exec") as mock_exec:
            self.tab.load_project("TestBox")
            mock_exec.assert_not_called()
        self.assertEqual(self.tab.editor.toPlainText(), "# Saved Report Content\nInitial text.")
        self.assertFalse(self.tab.is_dirty())

    def test_load_project_prompts_and_restores_draft(self):
        """When a recoverable draft exists and user accepts, draft is restored and marked dirty."""
        draft_content = "# Saved Report Content\nInitial text.\nUnsaved finding discovered before crash!"
        save_draft(self.project_dir, draft_content)

        with patch.object(QMessageBox, "exec") as mock_exec, \
             patch.object(QMessageBox, "clickedButton") as mock_btn:
            # Fake clicking the restore button (the default button)
            def side_effect():
                # Let clickedButton return the default restore button
                mock_btn.return_value = self.tab.sender()
                return 0
            mock_exec.side_effect = side_effect

            # Simulate dialog where clickedButton matches default button
            with patch("ui.report_editor_tab.QMessageBox") as mock_mb_cls:
                instance = MagicMock()
                mock_mb_cls.return_value = instance
                # The first button added is btn_restore
                btn_restore_mock = MagicMock()
                instance.addButton.side_effect = [btn_restore_mock, MagicMock()]
                instance.clickedButton.return_value = btn_restore_mock

                self.tab.load_project("TestBox")
                instance.exec.assert_called_once()

        self.assertEqual(self.tab.editor.toPlainText(), draft_content)
        self.assertTrue(self.tab.is_dirty())

    def test_load_project_prompts_and_discards_draft(self):
        """When user declines recovery, draft is discarded and saved file is loaded."""
        draft_content = "# Old Draft\nDifferent text."
        save_draft(self.project_dir, draft_content)
        self.assertTrue(get_draft_path(self.project_dir).exists())

        with patch("ui.report_editor_tab.QMessageBox") as mock_mb_cls:
            instance = MagicMock()
            mock_mb_cls.return_value = instance
            btn_restore = MagicMock()
            btn_discard = MagicMock()
            instance.addButton.side_effect = [btn_restore, btn_discard]
            instance.clickedButton.return_value = btn_discard

            self.tab.load_project("TestBox")
            instance.exec.assert_called_once()

        self.assertEqual(self.tab.editor.toPlainText(), "# Saved Report Content\nInitial text.")
        self.assertFalse(self.tab.is_dirty())
        self.assertFalse(get_draft_path(self.project_dir).exists())

    def test_save_cleans_up_draft_file(self):
        """A successful manual save should remove the draft file and stop draft timer."""
        self.tab.current_project = "TestBox"
        save_draft(self.project_dir, "Temporary in-flight text")
        self.assertTrue(get_draft_path(self.project_dir).exists())

        self.tab._draft_timer.start()
        self.tab._set_dirty(True)
        self.tab.save()

        self.assertFalse(get_draft_path(self.project_dir).exists())
        self.assertFalse(self.tab._draft_timer.isActive())


if __name__ == "__main__":
    unittest.main()

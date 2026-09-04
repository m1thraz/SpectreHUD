"""
Unit tests for NewProjectDialog and ProjectUnlockDialog.
Validates input fields, validation error dialogs, directory browsing,
Pentest-Mode password confirmation, and path preview generation.
"""

import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication([])

from core.project import ProjectManager
from ui.project_dialog import NewProjectDialog, ProjectUnlockDialog


class TestProjectDialogs(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path)

        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.project_mgr.create_project("ExistingBox", target_ip="10.10.10.50")

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        self.temp_dir.cleanup()

    def test_project_unlock_dialog(self):
        """ProjectUnlockDialog warns if empty and accepts on password entry."""
        dlg = ProjectUnlockDialog("SecretBox")

        # 1. Empty password -> warning
        with patch("ui.project_dialog.QMessageBox.warning") as mock_warn:
            dlg._on_unlock()
            mock_warn.assert_called_once()
            self.assertEqual(dlg.result(), 0)

        # 2. Entered password -> accept
        dlg.txt_password.setText("SuperSecret123")
        dlg._on_unlock()
        self.assertEqual(dlg.get_password(), "SuperSecret123")
        dlg.deleteLater()

    def test_new_project_dialog_empty_name(self):
        """NewProjectDialog shows warning when project name is empty."""
        dlg = NewProjectDialog(project_manager=self.project_mgr)
        dlg.txt_name.setText("   ")
        with patch("ui.project_dialog.QMessageBox.warning") as mock_warn:
            dlg._on_create()
            mock_warn.assert_called_once()
            self.assertEqual(dlg.result(), 0)
        dlg.deleteLater()

    def test_new_project_dialog_project_exists(self):
        """NewProjectDialog shows warning when project already exists in workspace."""
        dlg = NewProjectDialog(project_manager=self.project_mgr)
        dlg.txt_name.setText("ExistingBox")
        with patch("ui.project_dialog.QMessageBox.warning") as mock_warn:
            dlg._on_create()
            mock_warn.assert_called_once()
            self.assertEqual(dlg.result(), 0)
        dlg.deleteLater()

    def test_new_project_dialog_pentest_mode_validation(self):
        """NewProjectDialog validates pentest mode password presence and match."""
        dlg = NewProjectDialog(project_manager=self.project_mgr)
        dlg.txt_name.setText("SecureBox")
        dlg.chk_pentest_mode.setChecked(True)

        self.assertFalse(dlg.txt_pentest_password.isHidden())
        self.assertFalse(dlg.txt_pentest_password_confirm.isHidden())

        # 1. Missing password
        with patch("ui.project_dialog.QMessageBox.warning") as mock_warn:
            dlg._on_create()
            mock_warn.assert_called_once()
            self.assertIn("Password Required", mock_warn.call_args[0][1])

        # 2. Password mismatch
        dlg.txt_pentest_password.setText("passA")
        dlg.txt_pentest_password_confirm.setText("passB")
        with patch("ui.project_dialog.QMessageBox.warning") as mock_warn:
            dlg._on_create()
            mock_warn.assert_called_once()
            self.assertIn("Do Not Match", mock_warn.call_args[0][1])

        # 3. Passwords match -> accepts
        dlg.txt_pentest_password_confirm.setText("passA")
        dlg._on_create()
        data = dlg.get_data()
        self.assertEqual(data["name"], "SecureBox")
        self.assertTrue(data["pentest_mode"])
        self.assertEqual(data["pentest_password"], "passA")

        # Disable pentest mode clears fields
        dlg.chk_pentest_mode.setChecked(False)
        self.assertFalse(dlg.txt_pentest_password.isVisible())
        self.assertEqual(dlg.txt_pentest_password.text(), "")
        dlg.deleteLater()

    def test_new_project_dialog_browse_directory(self):
        """NewProjectDialog browse button sets txt_dir."""
        dlg = NewProjectDialog(project_manager=self.project_mgr)
        chosen_dir = str(self.temp_path / "custom_base")
        with patch("ui.project_dialog.QFileDialog.getExistingDirectory", return_value=chosen_dir):
            dlg._on_browse_directory()
            self.assertEqual(dlg.txt_dir.text(), chosen_dir)
        dlg.deleteLater()

    def test_new_project_dialog_path_preview(self):
        """NewProjectDialog dynamically updates destination path preview."""
        dlg = NewProjectDialog(project_manager=self.project_mgr)

        # Normal preview
        dlg.txt_name.setText("FreshBox")
        self.assertIn("FreshBox", dlg.lbl_path_preview.text())
        self.assertNotIn("⚠️", dlg.lbl_path_preview.text())

        # Existing preview shows warning badge
        dlg.txt_name.setText("ExistingBox")
        self.assertIn("⚠️", dlg.lbl_path_preview.text())
        dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()

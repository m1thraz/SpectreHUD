import os
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
from core.reporting.template_engine import TemplateSection
from core.reporting.template_repository import TemplateRepository
from ui.template_editor_dialog import TemplateEditorDialog, SectionEditDialog
from ui.template_manager_dialog import TemplateManagerDialog
from ui.styles import APP_THEME

app = QApplication.instance() or QApplication(sys.argv)


class TestTemplateDialogs(unittest.TestCase):
    """Unit tests for TemplateEditorDialog, SectionEditDialog, and TemplateManagerDialog."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.temp_path = Path(self.temp_dir.name)
        self.repo = TemplateRepository(user_templates_dir=self.temp_path / "user_templates")

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_section_edit_dialog_creation(self):
        """Tests section configuration dialog."""
        dlg = SectionEditDialog()
        # Default is header_metadata
        sec = dlg.get_section()
        self.assertEqual(sec.type, "header_metadata")
        self.assertIsNone(sec.title)

        # Set phase_section with custom category and title
        idx = dlg.combo_type.findData("phase_section")
        dlg.combo_type.setCurrentIndex(idx)
        dlg.txt_title.setText("Special Recon")
        cat_idx = dlg.combo_category.findData("recon")
        dlg.combo_category.setCurrentIndex(cat_idx)

        configured = dlg.get_section()
        self.assertEqual(configured.type, "phase_section")
        self.assertEqual(configured.title, "Special Recon")
        self.assertEqual(configured.category_id, "recon")

    def test_template_editor_inherits_theme_control_styles(self):
        """The editor uses the app theme instead of blocking user themes locally."""
        dlg = TemplateEditorDialog()

        self.assertEqual(dlg.objectName(), "TemplateEditorDialog")
        self.assertEqual(dlg.list_sections.objectName(), "TemplateSectionList")
        self.assertEqual(dlg.styleSheet(), "")
        self.assertIn("QListWidget#TemplateSectionList", APP_THEME)

    def test_template_editor_dialog_validation_and_save(self):
        """Tests template editor validation and output creation."""
        dlg = TemplateEditorDialog()
        dlg.show()

        # Validation fails if ID/Name are missing
        with patch.object(QMessageBox, "warning") as mock_warn:
            dlg._on_save()
            self.assertTrue(mock_warn.called)

        dlg.txt_id.setText("valid_custom_id")
        dlg.txt_name.setText("Custom Pentest Workflow")

        # Add a section
        dlg._add_section_to_list(TemplateSection(type="header_metadata"))
        dlg._add_section_to_list(TemplateSection(type="executive_summary"))
        self.assertEqual(dlg.list_sections.count(), 2)

        # Reorder sections
        dlg.list_sections.setCurrentRow(1)
        dlg._on_move_up()
        item0 = dlg.list_sections.item(0).data(0x0100)  # Qt.ItemDataRole.UserRole
        self.assertEqual(item0.type, "executive_summary")

        dlg._on_save()
        self.assertIsNotNone(dlg.result_template)
        self.assertEqual(dlg.result_template.id, "valid_custom_id")
        self.assertEqual(dlg.result_template.name, "Custom Pentest Workflow")
        self.assertEqual(len(dlg.result_template.sections), 2)

    def test_template_manager_dialog_workflow(self):
        """Tests template manager dialog listing, duplicate, edit, delete, select."""
        dlg = TemplateManagerDialog(repository=self.repo)
        dlg.show()

        self.assertGreater(dlg.table.rowCount(), 0)

        # Select first template and duplicate
        dlg.table.selectRow(0)

        def mock_exec_save(dialog_self):
            dialog_self._on_save()
            return QDialog.DialogCode.Accepted

        with patch("PyQt6.QtWidgets.QInputDialog.getText", return_value=("dup_test_1", True)):
            with patch.object(TemplateEditorDialog, "exec", mock_exec_save):
                dlg._on_duplicate()

        # Check that duplicated template is in repository
        saved_t = self.repo.get_template("dup_test_1")
        self.assertIsNotNone(saved_t)
        self.assertTrue(saved_t.name.endswith("(Kopie)"))

        # Delete the duplicated template
        # Find row of dup_test_1
        for row in range(dlg.table.rowCount()):
            if dlg.table.item(row, 1).text() == "dup_test_1":
                dlg.table.selectRow(row)
                break

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dlg._on_delete()

        self.assertIsNone(self.repo.get_template("dup_test_1"))

    def test_template_manager_inherits_theme_table_styles(self):
        dlg = TemplateManagerDialog(repository=self.repo)
        self.assertEqual(dlg.objectName(), "TemplateManagerDialog")
        self.assertEqual(dlg.table.objectName(), "TemplateTable")
        self.assertEqual(dlg.styleSheet(), "")
        self.assertIn("QTableWidget#TemplateTable", APP_THEME)


if __name__ == "__main__":
    unittest.main()

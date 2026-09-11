"""Unit tests for ReportFormatActions."""

from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QDialog, QPlainTextEdit, QWidget

from ui.report.format_actions import ReportFormatActions
from ui.report.icon_assets import ReportIconDefinition

pytestmark = pytest.mark.integration


class TestReportFormatActions(unittest.TestCase):
    def setUp(self):
        self.editor = QPlainTextEdit()
        self.parent = QWidget()
        self.loot_manager = MagicMock()
        self.rfm = MagicMock()
        self.current_project = "ProjectAlpha"

        self.actions = ReportFormatActions(
            editor=self.editor,
            parent_widget=self.parent,
            loot_manager_provider=lambda: self.loot_manager,
            report_file_manager_provider=lambda: self.rfm,
            current_project_provider=lambda: self.current_project,
        )

    def test_cursor_formatting_operations(self):
        # Heading
        self.editor.setPlainText("Title Line")
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        self.editor.setTextCursor(cursor)
        self.actions.format_heading(2)
        self.assertIn("## Title Line", self.editor.toPlainText())

        # Wrap
        self.editor.setPlainText("bold text")
        cursor = self.editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self.editor.setTextCursor(cursor)
        self.actions.format_wrap("**", "**")
        self.assertEqual(self.editor.toPlainText(), "**bold text**")

        # Code block
        self.editor.setPlainText("code line")
        cursor = self.editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self.editor.setTextCursor(cursor)
        self.actions.format_code_block()
        self.assertIn("```\n\n```", self.editor.toPlainText())

        # List
        self.editor.setPlainText("item1\nitem2")
        cursor = self.editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self.editor.setTextCursor(cursor)
        self.actions.format_list(False)
        self.assertIn("- item1\n- item2", self.editor.toPlainText())

        # Quote
        self.editor.setPlainText("quoted")
        cursor = self.editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self.editor.setTextCursor(cursor)
        self.actions.format_quote()
        self.assertIn("> quoted", self.editor.toPlainText())

        # Horizontal rule
        self.editor.setPlainText("")
        self.actions.format_horizontal_rule()
        self.assertIn("---", self.editor.toPlainText())

        # Page break
        self.editor.setPlainText("")
        self.actions.format_page_break()
        self.assertIn("<!-- spectre:pagebreak -->", self.editor.toPlainText())

        # Spacer
        self.editor.setPlainText("")
        self.actions.format_spacer("medium")
        self.assertIn("<!-- spectre:spacer:medium -->", self.editor.toPlainText())

    def test_format_table(self):
        with patch("ui.report.format_actions.MarkdownTableDialog") as mock_table_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
            mock_dlg.rows.value.return_value = 2
            mock_dlg.columns.value.return_value = 3
            mock_table_cls.return_value = mock_dlg

            self.editor.clear()
            self.actions.format_table()
            text = self.editor.toPlainText()
            self.assertIn("|---|---|---|", text)

    def test_insert_loot_entry_image(self):
        # Plain relative path
        self.editor.clear()
        self.actions.insert_loot_entry_image({"title": "Proof", "content": "loot/proof.png"})
        self.assertIn("![Proof](loot/proof.png)", self.editor.toPlainText())

        # Pre-formatted markdown image
        self.editor.clear()
        self.actions.insert_loot_entry_image({"title": "Proof", "content": "![Existing](loot/img.png)"})
        self.assertEqual(self.editor.toPlainText(), "![Existing](loot/img.png)")

    def test_open_loot_image_picker(self):
        with patch("ui.report.format_actions.LootImagePickerDialog") as mock_picker_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
            mock_dlg.selected_entry = {"title": "Loot Pic", "content": "loot/pic.png"}
            mock_picker_cls.return_value = mock_dlg

            self.editor.clear()
            self.actions.open_loot_image_picker([{"title": "Loot Pic", "content": "loot/pic.png"}])
            self.assertIn("![Loot Pic](loot/pic.png)", self.editor.toPlainText())

    def test_browse_and_insert_image(self, tmp_path=None):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            img_path = Path(tmp_dir) / "test.png"
            img_path.write_bytes(b"dummy")

            with patch("ui.report.format_actions.QFileDialog.getOpenFileName", return_value=(str(img_path), "Images (*.png)")):
                self.rfm.import_image.return_value = "screenshots/test.png"
                self.editor.clear()
                self.actions.browse_and_insert_image()
                self.assertIn("![test](screenshots/test.png)", self.editor.toPlainText())

    def test_format_icon_success(self):
        with (
            patch("ui.report.format_actions.ReportIconPickerDialog") as mock_icon_picker,
            patch("ui.report.format_actions.render_report_icon", return_value="assets/warning.png"),
        ):
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
            mock_dlg.selected_icon = ReportIconDefinition(
                key="warning",
                label_key="report.icon_warning",
                icon_name="fa5s.exclamation-triangle",
                category="status",
            )
            mock_icon_picker.return_value = mock_dlg

            self.editor.clear()
            self.actions.format_icon()
            self.assertIn("assets/warning.png", self.editor.toPlainText())

    def test_format_icon_error(self):
        with (
            patch("ui.report.format_actions.ReportIconPickerDialog") as mock_icon_picker,
            patch("ui.report.format_actions.render_report_icon", side_effect=RuntimeError("Font missing")),
            patch("ui.report.format_actions.show_error_dialog") as mock_err,
        ):
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
            mock_dlg.selected_icon = ReportIconDefinition(
                key="warning",
                label_key="report.icon_warning",
                icon_name="fa5s.exclamation-triangle",
                category="status",
            )
            mock_icon_picker.return_value = mock_dlg

            self.actions.format_icon()
            mock_err.assert_called_once()

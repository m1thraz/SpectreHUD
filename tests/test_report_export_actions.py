"""Unit tests for ReportExportActions."""

from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QMessageBox, QPlainTextEdit, QWidget

from core.reporting import ExportArtifact, ExportResult, ExportStatus
from ui.coordinators.export_coordinator import ReportExportError
from ui.report.export_actions import ReportExportActions

pytestmark = pytest.mark.integration


class TestReportExportActions(unittest.TestCase):
    def setUp(self):
        self.editor = QPlainTextEdit()
        self.parent = QWidget()
        self.rfm = MagicMock()
        self.coordinator = MagicMock()
        self.current_project = "ProjectBeta"
        self.template = MagicMock()
        self.template.language = "en"

        self.actions = ReportExportActions(
            parent_widget=self.parent,
            editor=self.editor,
            report_file_manager_provider=lambda: self.rfm,
            export_coordinator_provider=lambda: self.coordinator,
            current_project_provider=lambda: self.current_project,
            active_template_provider=lambda: self.template,
            report_font_key_provider=lambda: "default",
        )

    def test_require_export_coordinator(self):
        # When coordinator exists
        self.assertEqual(self.actions.require_export_coordinator(), self.coordinator)

        # When missing
        no_coord_actions = ReportExportActions(
            parent_widget=self.parent,
            editor=self.editor,
            report_file_manager_provider=lambda: self.rfm,
            export_coordinator_provider=lambda: None,
            current_project_provider=lambda: self.current_project,
            active_template_provider=lambda: self.template,
            report_font_key_provider=lambda: "default",
        )
        with patch("ui.report.export_actions.show_error_dialog") as mock_err:
            self.assertIsNone(no_coord_actions.require_export_coordinator())
            mock_err.assert_called_once()

    def test_on_export_copy_clicked(self, tmp_path=None):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "copy.md"

            # 1. Cancelled file dialog
            with patch("ui.report.export_actions.QFileDialog.getSaveFileName", return_value=("", "")):
                self.actions.on_export_copy_clicked()
                self.coordinator.export_report_markdown.assert_not_called()

            # 2. Successful export
            self.editor.setPlainText("# Content")
            with (
                patch("ui.report.export_actions.QFileDialog.getSaveFileName", return_value=(str(out_file), "Markdown (*.md)")),
                patch("ui.report.export_actions.show_information_dialog") as mock_info,
            ):
                mock_res = ExportResult(status=ExportStatus.SUCCESS, artifacts=[MagicMock(path=out_file, format="markdown")])
                self.coordinator.export_report_markdown.return_value = mock_res
                self.actions.on_export_copy_clicked()
                self.coordinator.export_report_markdown.assert_called_once_with(out_file, "# Content")
                mock_info.assert_called_once()

            # 3. Export error
            self.coordinator.export_report_markdown.side_effect = ReportExportError("Write error")
            with (
                patch("ui.report.export_actions.QFileDialog.getSaveFileName", return_value=(str(out_file), "Markdown (*.md)")),
                patch("ui.report.export_actions.show_error_dialog") as mock_err,
            ):
                self.actions.on_export_copy_clicked()
                mock_err.assert_called_once()

    def test_on_export_html_clicked(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_html = Path(tmp_dir) / "report.html"

            # 1. Cancelled options
            with patch.object(self.actions, "select_html_export_options", return_value=None):
                self.actions.on_export_html_clicked()
                self.coordinator.export_report_html.assert_not_called()

            # 2. Successful export asking to open in browser
            self.editor.setPlainText("# HTML Content")
            mock_res = ExportResult(
                status=ExportStatus.SUCCESS,
                artifacts=(ExportArtifact(path=out_html, format="html"),),
            )
            self.coordinator.export_report_html.return_value = mock_res

            with (
                patch.object(self.actions, "select_html_export_options", return_value=("light", "professional_print")),
                patch("ui.report.export_actions.QFileDialog.getSaveFileName", return_value=(str(out_html), "HTML (*.html)")),
                patch("ui.report.export_actions.ask_confirmation", return_value=QMessageBox.StandardButton.No),
            ):
                self.actions.on_export_html_clicked()
                self.coordinator.export_report_html.assert_called_once()

    def test_on_export_obsidian_clicked(self):
        self.editor.setPlainText("# Obsidian Content")
        self.actions.on_export_obsidian_clicked()
        self.coordinator.export_report_to_obsidian.assert_called_once_with(
            self.parent,
            "ProjectBeta",
            "# Obsidian Content",
        )

    def test_on_export_cherrytree_clicked(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            dest_dir = Path(tmp_dir) / "ct_export"
            dest_dir.mkdir()

            self.rfm.project_manager.get_project_dir.return_value = Path(tmp_dir)
            self.editor.setPlainText("# CT Content")
            mock_res = ExportResult(status=ExportStatus.SUCCESS, artifacts=[MagicMock(path=dest_dir / "report.html", format="html")])
            self.coordinator.export_report_to_cherrytree.return_value = mock_res

            with (
                patch("ui.report.export_actions.QFileDialog.getExistingDirectory", return_value=str(dest_dir)),
                patch("ui.report.export_actions.show_information_dialog") as mock_info,
            ):
                self.actions.on_export_cherrytree_clicked()
                self.coordinator.export_report_to_cherrytree.assert_called_once()
                mock_info.assert_called_once()

    def test_present_export_result_variants(self):
        # Cancelled
        cancelled_res = ExportResult(status=ExportStatus.CANCELLED)
        with patch("ui.report.export_actions.show_information_dialog") as mock_info:
            self.actions.present_export_result(cancelled_res, title="Cancelled")
            mock_info.assert_not_called()

        # Failed
        failed_res = ExportResult(status=ExportStatus.FAILED, error=MagicMock(message="Failed", details="Disk full"))
        with patch("ui.report.export_actions.show_error_dialog") as mock_err:
            self.actions.present_export_result(failed_res, title="Error")
            mock_err.assert_called_once()

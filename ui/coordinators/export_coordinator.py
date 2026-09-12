"""
Export Coordinator for SpectreHUD.

Coordinates report and loot export operations (Markdown, HTML, ZIP archives).
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QWidget

from core.config import ConfigManager
from core.atomic_write import atomic_write_text
from core.exporters import (
    CherryTreeExporter,
    ExportArtifact,
    ExportResult,
    ExportStatus,
    ExternalExportError,
    ObsidianExporter,
)
from core.reporting import HtmlReportExporter
from core.reporting import ReportExportProfile
from core.i18n import t
from ui.message_boxes import ask_confirmation, show_error_dialog, show_information_dialog
from core.platform import open_path
from core.project import ProjectManager
from core.loot import LootManager
from core.logger import get_logger
from ui.controllers.history_controller import HistoryController

logger = get_logger(__name__)


class ReportExportError(RuntimeError):
    """Raised when a concrete report export operation cannot be completed."""


class ExportCoordinator(QObject):
    """Coordinates reporting and loot export actions across the application."""

    def __init__(
        self,
        project_manager: ProjectManager,
        loot_manager: LootManager,
        history_ctrl: HistoryController,
        target_provider: Callable[[], str],
        config_manager: ConfigManager,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.project_manager = project_manager
        self.loot_manager = loot_manager
        self.history_ctrl = history_ctrl
        self.target_provider = target_provider
        self.config = config_manager

    def export_loot(self, window: QWidget) -> None:
        """Exports session loot / report copy."""
        self.export_report(window)

    def export_report(self, window: QWidget) -> None:
        """Exports report copy using HistoryController."""
        target_ip = self.target_provider()
        active_proj = self.project_manager.get_active_project()
        self.history_ctrl.export_report_dialog(window, target_ip, active_proj)

    def export_report_markdown(self, target: Path, markdown: str) -> ExportResult:
        """Write an explicit Markdown copy of the current editor document."""
        from core.reporting import strip_report_markers

        target = Path(target)
        clean_markdown = strip_report_markers(markdown)
        if not atomic_write_text(target, clean_markdown):
            raise ReportExportError(f"Could not write Markdown report: {target}")

        bytes_written = (
            target.stat().st_size if target.exists() else len(clean_markdown.encode("utf-8"))
        )
        return ExportResult.success(
            artifacts=(
                ExportArtifact(path=target, format="markdown", bytes_written=bytes_written),
            )
        )

    def export_report_html(
        self,
        *,
        target: Path,
        project_name: str,
        markdown: str,
        theme: str,
        report_font: str,
        language: str = "en",
        profile: ReportExportProfile | str = ReportExportProfile.INTERACTIVE,
        category: Optional[str] = None,
    ) -> ExportResult:
        """Render the current editor document as a standalone HTML report."""
        project_dir = self.project_manager.get_project_dir(project_name)
        target = Path(target)
        res = HtmlReportExporter.export_to_file(
            markdown_content=markdown,
            output_path=target,
            project_dir=project_dir,
            project_name=project_name,
            target_ip="",
            theme=theme,
            report_font=report_font,
            language=language,
            profile=profile,
            category=category,
        )
        if not res:
            err_msg = (
                res.error.message
                if isinstance(res, ExportResult) and res.error
                else f"Could not write HTML report: {target}"
            )
            raise ReportExportError(err_msg)

        if isinstance(res, ExportResult):
            return res
        bytes_written = target.stat().st_size if target.exists() else 0
        return ExportResult.success(
            artifacts=(
                ExportArtifact(path=target, format="html", bytes_written=bytes_written),
            )
        )

    def export_report_to_cherrytree(
        self,
        *,
        destination: Path,
        project_name: str,
        markdown: str,
        report_font: str,
    ) -> ExportResult:
        """Create a portable CherryTree-compatible HTML package."""
        project_dir = self.project_manager.get_project_dir(project_name)
        try:
            return CherryTreeExporter(destination).export_package(
                project_name=project_name,
                project_dir=project_dir,
                report_markdown=markdown,
                loot_entries=self.loot_manager.get_all_entries(),
                report_font=report_font,
            )
        except (ExternalExportError, OSError, RuntimeError) as exc:
            raise ReportExportError(str(exc)) from exc

    def export_loot_to_obsidian(self, window: QWidget) -> None:
        """Append active-session loot without rewriting a user's report note."""
        self.append_loot_entries_to_obsidian(window, self.loot_manager.get_all_entries())

    def _configured_obsidian_exporter(
        self,
        window: QWidget,
        *,
        scope: str,
    ) -> Optional[ObsidianExporter]:
        """Return the shared configured exporter or explain the missing setup."""
        is_loot = scope == "loot"
        vault_path = str(self.config.get("obsidian_vault_path", "") or "").strip()
        if not vault_path:
            show_information_dialog(
                window,
                t(f"{scope}.obsidian_not_configured_title", "Obsidian is not configured"),
                t(
                    f"{scope}.obsidian_not_configured",
                    "Choose an existing Obsidian vault in Settings before exporting loot."
                    if is_loot
                    else "Choose an existing Obsidian vault in Settings before exporting.",
                ),
            )
            return None
        try:
            return ObsidianExporter(
                vault_path,
                self.config.get("obsidian_export_folder", "CTF/SpectreHUD"),
            )
        except ExternalExportError as exc:
            logger.warning("Invalid Obsidian export configuration: %s", exc)
            show_error_dialog(
                window,
                t(f"{scope}.obsidian_export_failed_title", "Obsidian export failed"),
                t(
                    f"{scope}.obsidian_export_failed",
                    "Loot could not be sent to Obsidian:\n{error}"
                    if is_loot
                    else "The report could not be exported to Obsidian:\n{error}",
                    error=str(exc),
                ),
            )
            return None

    def export_report_to_obsidian(
        self,
        window: QWidget,
        project_name: str,
        markdown: str,
    ) -> None:
        """Export the current editor document through the shared Obsidian workflow."""
        exporter = self._configured_obsidian_exporter(
            window,
            scope="report",
        )
        if exporter is None:
            return

        try:
            project_dir = self.project_manager.get_project_dir(project_name)
            project_state = self.project_manager.load_project_state(project_name)
            result = exporter.export_report(
                project_name=project_name,
                project_dir=project_dir,
                markdown=markdown,
                project_state=project_state.to_dict(),
                overwrite="copy",
            )
        except (ExternalExportError, OSError, RuntimeError) as exc:
            logger.error("Obsidian report export failed: %s", exc, exc_info=True)
            show_error_dialog(
                window,
                t("report.obsidian_export_failed_title", "Obsidian export failed"),
                t(
                    "report.obsidian_export_failed",
                    "The report could not be exported to Obsidian:\n{error}",
                    error=str(exc),
                ),
            )
            return

        message = t(
            "report.obsidian_exported",
            "Exported to Obsidian:\n{path}",
            path=str(result.note_path),
        )
        if result.warnings:
            message += "\n\n" + t(
                "report.obsidian_attachment_warning",
                "Some attachments could not be copied.",
            )
        show_information_dialog(
            window,
            t("report.obsidian_exported_title", "Obsidian export complete"),
            message,
        )
        if self.config.get("obsidian_open_after_export", False):
            if not QDesktopServices.openUrl(QUrl(result.obsidian_uri)):
                logger.warning("Obsidian could not open export URI: %s", result.obsidian_uri)

    def append_loot_entries_to_obsidian(
        self, window: QWidget, entries: List[Dict[str, Any]]
    ) -> None:
        """Append selected entries to the current project note with deduplication."""
        exporter = self._configured_obsidian_exporter(
            window,
            scope="loot",
        )
        if exporter is None:
            return
        project_name = self.project_manager.get_active_project()
        try:
            note_path = exporter.note_path_for(project_name)
            if not note_path.exists():
                raise ExternalExportError(
                    "Export the report to Obsidian first so SpectreHUD can append loot without creating an incomplete note."
                )
            result = exporter.append_loot(
                project_name=project_name, entries=entries, note_path=note_path
            )
        except ExternalExportError as exc:
            logger.warning("Obsidian loot export failed: %s", exc)
            show_error_dialog(
                window,
                t("loot.obsidian_export_failed_title", "Obsidian export failed"),
                t(
                    "loot.obsidian_export_failed",
                    "Loot could not be sent to Obsidian:\n{error}",
                    error=str(exc),
                ),
            )
            return

        if result.skipped_entry_ids:
            message = t(
                "loot.obsidian_exported_duplicates",
                "Loot is already up to date in Obsidian ({count} duplicate entries skipped).",
                count=len(result.skipped_entry_ids),
            )
        else:
            message = t(
                "loot.obsidian_exported",
                "Loot appended to Obsidian:\n{path}",
                path=str(result.note_path),
            )
        show_information_dialog(
            window, t("loot.obsidian_exported_title", "Obsidian updated"), message
        )
        if self.config.get("obsidian_open_after_export", False):
            if not QDesktopServices.openUrl(QUrl(result.obsidian_uri)):
                logger.warning("Obsidian could not open loot export URI: %s", result.obsidian_uri)

    def export_single_loot_to_obsidian(self, window: QWidget, entry_id: str) -> None:
        entry = next(
            (item for item in self.loot_manager.get_all_entries() if item.get("id") == entry_id),
            None,
        )
        if entry is not None:
            self.append_loot_entries_to_obsidian(window, [entry])

    def present_export_result(
        self,
        window: Optional[QWidget],
        result: ExportResult,
        *,
        title: str,
        success_message: Optional[str] = None,
        ask_open_file: Optional[Path] = None,
    ) -> None:
        """Present any ExportResult to the user in a consistent, UI-standard way."""
        status = getattr(result, "status", None)
        if status is ExportStatus.CANCELLED:
            return

        if status is ExportStatus.FAILED:
            err = getattr(result, "error", None)
            err_msg = (
                getattr(err, "message", None)
                if err
                else "Export failed"
            )
            details = getattr(err, "details", None) if err else None
            show_error_dialog(window, title, str(err_msg), details=details)
            return

        msg = success_message
        if not msg:
            if result.artifacts:
                first = result.artifacts[0].path
                if any(a.format == "image" for a in result.artifacts):
                    msg = t(
                        "report.cherrytree_exported",
                        "CherryTree HTML package created:\n{path}",
                        path=str(first.parent),
                    )
                else:
                    msg = t(
                        "report.export_saved_msg",
                        "Kopie gespeichert: {filename}",
                        filename=first.name,
                    )
            else:
                msg = t("report.export_saved_title", "Exportiert")

        if result.warnings:
            msg += "\n\n" + t(
                "report.cherrytree_attachment_warning",
                "Some images could not be copied.",
            )

        if ask_open_file:
            from PyQt6.QtWidgets import QMessageBox

            reply = ask_confirmation(
                window,
                title,
                t(
                    "report.export_html_success_msg",
                    "HTML-Report gespeichert:\n{filename}\n\nIm Standard-Browser öffnen?",
                    filename=ask_open_file.name,
                ),
                default_button=QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if not open_path(ask_open_file):
                    show_error_dialog(
                        window,
                        t("report.open_html_error_title", "Report unavailable"),
                        t(
                            "report.open_html_error_message",
                            "The exported HTML report could not be opened:\n{path}",
                            path=str(ask_open_file),
                        ),
                    )
        else:
            show_information_dialog(window, title, msg)

        if result.obsidian_uri and self.config.get("obsidian_open_after_export", False):
            if not QDesktopServices.openUrl(QUrl(result.obsidian_uri)):
                logger.warning("Obsidian could not open export URI: %s", result.obsidian_uri)

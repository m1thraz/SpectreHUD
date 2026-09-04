"""
Export Coordinator for SpectreHUD.

Coordinates report and loot export operations (Markdown, HTML, ZIP archives).
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QMessageBox, QWidget

from core.config import ConfigManager
from core.atomic_write import atomic_write_text
from core.exporters import CherryTreeExporter, ExportResult, ExternalExportError, ObsidianExporter
from core.reporting import HtmlReportExporter
from core.i18n import t
from core.project import ProjectManager
from core.loot_manager import LootManager
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

    def export_report_markdown(self, target: Path, markdown: str) -> None:
        """Write an explicit Markdown copy of the current editor document."""
        from core.reporting.loot_sync import strip_report_markers

        clean_markdown = strip_report_markers(markdown)
        if not atomic_write_text(target, clean_markdown):
            raise ReportExportError(f"Could not write Markdown report: {target}")

    def export_report_html(
        self,
        *,
        target: Path,
        project_name: str,
        markdown: str,
        theme: str,
        report_font: str,
        language: str = "en",
    ) -> None:
        """Render the current editor document as a standalone HTML report."""
        project_dir = self.project_manager.get_project_dir(project_name)
        if not HtmlReportExporter.export_to_file(
            markdown_content=markdown,
            output_path=target,
            project_dir=project_dir,
            project_name=project_name,
            target_ip="",
            theme=theme,
            report_font=report_font,
            language=language,
        ):
            raise ReportExportError(f"Could not write HTML report: {target}")

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
            QMessageBox.information(
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
            QMessageBox.warning(
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
                project_state=project_state,
                overwrite="copy",
            )
        except (ExternalExportError, OSError, RuntimeError) as exc:
            logger.error("Obsidian report export failed: %s", exc, exc_info=True)
            QMessageBox.warning(
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
        QMessageBox.information(
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
            QMessageBox.warning(
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
        QMessageBox.information(
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

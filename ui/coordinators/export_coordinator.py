"""
Export Coordinator for SpectreHUD.

Coordinates report and loot export operations (Markdown, HTML, ZIP archives).
"""

from typing import Any, Callable, Dict, List, Optional
from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QMessageBox, QWidget

from core.config import ConfigManager
from core.exporters import ExternalExportError, ObsidianExporter
from core.i18n import t
from core.project import ProjectManager
from core.loot_manager import LootManager
from core.logger import get_logger
from ui.controllers.history_controller import HistoryController

logger = get_logger(__name__)

EXPORT_COPY_TOOLTIP = (
    "Erstellt eine neue Kopie basierend auf dem aktuellen Loot. "
    "Für die bearbeitbare Version siehe Report-Tab."
)


class ExportCoordinator(QObject):
    """Coordinates reporting and loot export actions across the application."""

    def __init__(
        self,
        project_manager: ProjectManager,
        loot_manager: LootManager,
        history_ctrl: HistoryController,
        target_provider: Callable[[], str],
        config_manager: ConfigManager,
        parent: Optional[QObject] = None
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
        self.history_ctrl.export_report(window, target_ip, active_proj)

    def export_loot_to_obsidian(self, window: QWidget) -> None:
        """Append active-session loot without rewriting a user's report note."""
        self.append_loot_entries_to_obsidian(window, self.loot_manager.get_all_entries())

    def append_loot_entries_to_obsidian(self, window: QWidget, entries: List[Dict[str, Any]]) -> None:
        """Append selected entries to the current project note with deduplication."""
        vault_path = str(self.config.get("obsidian_vault_path", "") or "").strip()
        if not vault_path:
            QMessageBox.information(
                window,
                t("loot.obsidian_not_configured_title", "Obsidian is not configured"),
                t("loot.obsidian_not_configured", "Choose an existing Obsidian vault in Settings before exporting loot."),
            )
            return
        project_name = self.project_manager.get_active_project()
        try:
            exporter = ObsidianExporter(vault_path, self.config.get("obsidian_export_folder", "CTF/SpectreHUD"))
            note_path = exporter.note_path_for(project_name)
            if not note_path.exists():
                raise ExternalExportError(
                    "Export the report to Obsidian first so SpectreHUD can append loot without creating an incomplete note."
                )
            result = exporter.append_loot(project_name=project_name, entries=entries, note_path=note_path)
        except ExternalExportError as exc:
            logger.warning("Obsidian loot export failed: %s", exc)
            QMessageBox.warning(
                window,
                t("loot.obsidian_export_failed_title", "Obsidian export failed"),
                t("loot.obsidian_export_failed", "Loot could not be sent to Obsidian:\n{error}", error=str(exc)),
            )
            return

        if result.skipped_entry_ids:
            message = t(
                "loot.obsidian_exported_duplicates",
                "Loot is already up to date in Obsidian ({count} duplicate entries skipped).",
                count=len(result.skipped_entry_ids),
            )
        else:
            message = t("loot.obsidian_exported", "Loot appended to Obsidian:\n{path}", path=str(result.note_path))
        QMessageBox.information(window, t("loot.obsidian_exported_title", "Obsidian updated"), message)
        if self.config.get("obsidian_open_after_export", False):
            if not QDesktopServices.openUrl(QUrl(result.obsidian_uri)):
                logger.warning("Obsidian could not open loot export URI: %s", result.obsidian_uri)

    def export_single_loot_to_obsidian(self, window: QWidget, entry_id: str) -> None:
        entry = next((item for item in self.loot_manager.get_all_entries() if item.get("id") == entry_id), None)
        if entry is not None:
            self.append_loot_entries_to_obsidian(window, [entry])

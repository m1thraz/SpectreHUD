"""
Export Coordinator for SpectreHUD.

Coordinates report and loot export operations (Markdown, HTML, ZIP archives).
"""

from typing import Optional, Callable
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QWidget

from core.project_manager import ProjectManager
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
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.project_manager = project_manager
        self.loot_manager = loot_manager
        self.history_ctrl = history_ctrl
        self.target_provider = target_provider

    def export_loot(self, window: QWidget) -> None:
        """Exports session loot / report copy."""
        self.export_report(window)

    def export_report(self, window: QWidget) -> None:
        """Exports report copy using HistoryController."""
        target_ip = self.target_provider()
        active_proj = self.project_manager.get_active_project()
        self.history_ctrl.export_report(window, target_ip, active_proj)

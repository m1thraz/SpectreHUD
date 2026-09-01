from typing import Optional, List, TYPE_CHECKING
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from core.project import ProjectManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.report_file_manager import ReportFileManager
from core.config import ConfigManager

if TYPE_CHECKING:
    from ui.coordinators.export_coordinator import ExportCoordinator
    from ui.report_editor_tab import ReportEditorTab


class ReportController(QObject):
    """Controller managing the ReportEditorTab and report file operations."""

    def __init__(
        self,
        project_manager: ProjectManager,
        loot_manager: LootManager,
        clipboard_watcher: ClipboardWatcher,
        parent_widget: Optional[QWidget] = None,
        config_manager: Optional[ConfigManager] = None,
        export_coordinator: Optional["ExportCoordinator"] = None,
    ):
        super().__init__(parent_widget)
        self.project_manager = project_manager
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher
        self.config_manager = config_manager
        self.export_coordinator = export_coordinator

        self.report_file_manager = ReportFileManager(self.project_manager)
        self.parent_widget = parent_widget
        self.report_editor_tab: Optional["ReportEditorTab"] = None

    def _ensure_tab_widget(self) -> "ReportEditorTab":
        """Create the expensive report editor only when the user opens it."""
        if self.report_editor_tab is None:
            # Importing and constructing the rich editor is deliberately lazy:
            # SpectreHUD starts in Cheatsheet mode, where no report UI is needed.
            from ui.report_editor_tab import ReportEditorTab

            self.report_editor_tab = ReportEditorTab(
                self.report_file_manager,
                self.loot_manager,
                self.clipboard_watcher,
                parent=self.parent_widget,
                config_manager=self.config_manager,
                export_coordinator=self.export_coordinator,
            )
            self.report_editor_tab.load_project(self.project_manager.get_active_project())
        return self.report_editor_tab

    def set_export_coordinator(
        self,
        coordinator: "ExportCoordinator",
    ) -> None:
        """Inject the shared export operations into the lazy editor."""
        self.export_coordinator = coordinator
        if self.report_editor_tab is not None:
            self.report_editor_tab.export_coordinator = coordinator

    def load_project(self, project_name: str) -> None:
        if self.report_editor_tab is not None:
            self.report_editor_tab.load_project(project_name)

    def confirm_discard_if_dirty(self) -> bool:
        return (
            self.report_editor_tab.confirm_discard_if_dirty()
            if self.report_editor_tab is not None
            else True
        )

    def get_tab_widget(self) -> "ReportEditorTab":
        return self._ensure_tab_widget()

    def render_content(self, content_layout: QVBoxLayout) -> List[QWidget]:
        report_editor_tab = self._ensure_tab_widget()
        while content_layout.count():
            child = content_layout.takeAt(0)
            if child.widget() and child.widget() != report_editor_tab:
                child.widget().deleteLater()
        content_layout.addWidget(report_editor_tab)
        return [report_editor_tab]

    def detach_tab_if_needed(self, content_layout: QVBoxLayout) -> None:
        if self.report_editor_tab is not None and self.report_editor_tab.parent() is not None:
            content_layout.removeWidget(self.report_editor_tab)
            self.report_editor_tab.setParent(None)

    def refresh_font_configuration(self) -> None:
        if self.report_editor_tab is not None:
            self.report_editor_tab.refresh_font_configuration()

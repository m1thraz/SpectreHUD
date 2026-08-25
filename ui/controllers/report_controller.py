from typing import Optional, List
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from core.project_manager import ProjectManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.report_file_manager import ReportFileManager
from ui.report_editor_tab import ReportEditorTab


class ReportController(QObject):
    """Controller managing the ReportEditorTab and report file operations."""

    def __init__(
        self,
        project_manager: ProjectManager,
        loot_manager: LootManager,
        clipboard_watcher: ClipboardWatcher,
        parent_widget: Optional[QWidget] = None
    ):
        super().__init__(parent_widget)
        self.project_manager = project_manager
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher

        self.report_file_manager = ReportFileManager(self.project_manager)
        self.report_editor_tab = ReportEditorTab(
            self.report_file_manager,
            self.loot_manager,
            self.clipboard_watcher,
            parent=parent_widget
        )
        self.report_editor_tab.load_project(self.project_manager.get_active_project())

    def load_project(self, project_name: str) -> None:
        self.report_editor_tab.load_project(project_name)

    def confirm_discard_if_dirty(self) -> bool:
        return self.report_editor_tab.confirm_discard_if_dirty()

    def get_tab_widget(self) -> ReportEditorTab:
        return self.report_editor_tab

    def render_content(self, content_layout: QVBoxLayout) -> List[QWidget]:
        while content_layout.count():
            child = content_layout.takeAt(0)
            if child.widget() and child.widget() != self.report_editor_tab:
                child.widget().deleteLater()
        content_layout.addWidget(self.report_editor_tab)
        return [self.report_editor_tab]

    def detach_tab_if_needed(self, content_layout: QVBoxLayout) -> None:
        if self.report_editor_tab.parent() is not None:
            content_layout.removeWidget(self.report_editor_tab)
            self.report_editor_tab.setParent(None)

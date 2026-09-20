from typing import Optional, List, TYPE_CHECKING
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from core.project import ProjectManager
from core.loot import LootManager
from core.clipboard_history import ClipboardHistory
from core.reporting import ReportFileManager, ReportReadError, ReportReadStatus
from core.config import ConfigManager
from core.reporting import append_report_note
from core.i18n import t
from core.logger import get_logger
from ui.message_boxes import show_error_dialog

logger = get_logger("report_controller")

if TYPE_CHECKING:
    from ui.coordinators.export_coordinator import ExportCoordinator
    from ui.report_editor_tab import ReportEditorTab


class ReportController(QObject):
    """Controller managing the ReportEditorTab and report file operations."""

    def __init__(
        self,
        project_manager: ProjectManager,
        loot_manager: LootManager,
        clipboard_history: ClipboardHistory,
        parent_widget: Optional[QWidget] = None,
        config_manager: Optional[ConfigManager] = None,
        export_coordinator: Optional["ExportCoordinator"] = None,
    ):
        super().__init__(parent_widget)
        self.project_manager = project_manager
        self.loot_manager = loot_manager
        self.clipboard_history = clipboard_history
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
                self.clipboard_history,
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
            self.report_editor_tab.set_export_coordinator(coordinator)

    def load_project(self, project_name: str) -> None:
        if self.report_editor_tab is not None:
            self.report_editor_tab.load_project(project_name, fail_closed=True)
        else:
            self.report_file_manager.load(project_name)

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

    def refresh_loot_sync_state(self) -> None:
        """Refresh report/Loot status without eagerly constructing the editor."""
        if self.report_editor_tab is not None:
            self.report_editor_tab.refresh_loot_sync_state()

    def append_note(self, note: dict) -> bool:
        """Appends a quick note to the active project's report.md."""
        if self.report_editor_tab is not None:
            if self.report_editor_tab.is_write_blocked():
                return False
            current = self.report_editor_tab.current_markdown()
        else:
            try:
                current = self.report_file_manager.load()
            except ReportReadError as exc:
                logger.error("Could not append note because report reading failed: %s", exc)
                show_error_dialog(
                    self.parent_widget,
                    t("report.read_error_title", "Report could not be loaded"),
                    t(
                        "report.read_error_append",
                        "The note was not added because the existing report could not be read.",
                    ),
                    details=str(exc),
                )
                return False

        new_content = append_report_note(
            current,
            self.project_manager.get_active_project(),
            note,
        )
        if new_content is None:
            return False

        if self.report_editor_tab is not None:
            self.report_editor_tab.replace_markdown(new_content)
            return self.report_editor_tab.save()

        return self.report_file_manager.save(new_content)

    def markdown_for_analysis(self) -> Optional[str]:
        """Return report text for read-only UI analysis, or None when disk reading failed."""
        if self.report_editor_tab is not None:
            return (
                None
                if self.report_editor_tab.is_write_blocked()
                else self.report_editor_tab.current_markdown()
            )
        result = self.report_file_manager.load_result()
        if result.status is ReportReadStatus.READ_FAILED:
            logger.error("Skipping report analysis because reading failed: %s", result.detail)
            return None
        return result.content

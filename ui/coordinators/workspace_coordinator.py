"""
Workspace Coordinator for SpectreHUD.

Coordinates project workspaces, session state persistence, and project menu interactions.
"""

from typing import Optional, Dict, Any, Callable
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QPushButton, QMessageBox

from core.project_manager import ProjectManager
from core.project_session_service import ProjectSessionService
from core.event_bus import EventBus, EventType
from core.i18n import t
from core.logger import get_logger
from ui.styles import CYBER_DARK_QSS
from ui.controllers.project_controller import ProjectController
from ui.controllers.report_controller import ReportController

logger = get_logger(__name__)


class WorkspaceCoordinator(QObject):
    """Coordinates project lifecycle, switching, session persistence, and project dialogs."""

    project_changed = pyqtSignal(str)

    def __init__(
        self,
        project_manager: ProjectManager,
        session_service: ProjectSessionService,
        project_ctrl: ProjectController,
        report_ctrl: ReportController,
        event_bus: EventBus,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.project_manager = project_manager
        self.session_service = session_service
        self.project_ctrl = project_ctrl
        self.report_ctrl = report_ctrl
        self.event_bus = event_bus

    def load_active_project_session(self) -> Dict[str, str]:
        """Loads and returns the variable state for the currently active project."""
        active_proj = self.project_manager.get_active_project()
        return self.session_service.load_project_session(active_proj)

    def save_current_project_session(self, variables: Dict[str, str]) -> bool:
        """Persists the variable state for the currently active project."""
        return self.session_service.save_project_session(variables)

    def switch_to_project(
        self,
        project_name: str,
        window: QWidget,
        variables_provider: Callable[[], Dict[str, str]],
        on_success_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        Validates dirty reports, persists previous project state, and switches to a new project.
        """
        if project_name == self.project_manager.get_active_project():
            return False

        if not self.report_ctrl.confirm_discard_if_dirty():
            return False

        current_proj = self.project_manager.get_active_project()
        variables = variables_provider() if variables_provider else {}
        if not self.save_current_project_session(variables):
            logger.error(f"Failed to persist state for project '{current_proj}' before switching to '{project_name}'")
            project_unavailable = not self.project_manager.project_exists(current_proj)
            msg = QMessageBox(window)
            msg.setWindowTitle(t("general.save_failed", "Speichern fehlgeschlagen"))
            if project_unavailable:
                msg.setText(
                    f"Der Projektordner des aktiven Projekts '{current_proj}' wurde außerhalb von SpectreHUD "
                    "verschoben oder gelöscht. SpectreHUD hat ihn nicht neu erstellt.\n\n"
                    "Möchtest du den Projektwechsel trotzdem fortsetzen und ungespeicherte Änderungen verwerfen?"
                )
            else:
                msg.setText(
                    f"Der Zustand des aktuellen Projekts '{current_proj}' konnte nicht auf der Festplatte gespeichert werden.\n\n"
                    "Möchtest du den Projektwechsel trotzdem fortsetzen und ungespeicherte Änderungen verwerfen?"
                )
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
            msg.setStyleSheet(CYBER_DARK_QSS)
            if msg.exec() != QMessageBox.StandardButton.Yes:
                self.project_ctrl.update_project_combo()
                return False

        try:
            self.project_manager.activate_project(project_name)
        except Exception as activate_err:
            logger.error(f"Failed to activate project '{project_name}': {activate_err}")
            QMessageBox.critical(
                window,
                t("general.error", "Error"),
                t("project.not_found_msg", f"Project '{project_name}' does not exist and cannot be activated.\n\n{activate_err}")
            )
            self.project_ctrl.update_project_combo()
            return False

        try:
            self.report_ctrl.load_project(project_name)
        except Exception as report_err:
            logger.error(
                f"Failed to load report for project '{project_name}', rolling back project switch: {report_err}",
                exc_info=True,
            )
            try:
                self.project_manager.activate_project(current_proj)
            except Exception:
                logger.exception("Failed to restore the previous project after report load failure")
            QMessageBox.critical(
                window,
                t("general.error", "Error"),
                f"Failed to load the report for project '{project_name}'. The previous project has been restored.\n\n{report_err}",
            )
            self.project_ctrl.update_project_combo()
            return False

        if on_success_callback:
            on_success_callback(project_name)

        self.project_changed.emit(project_name)
        self.event_bus.publish(EventType.PROJECT_CHANGED, {"project_name": project_name})
        return True

    def show_project_menu(
        self,
        btn_anchor: QPushButton,
        window: QWidget,
        switch_cb: Callable[[str], None],
        new_dialog_cb: Callable[[], None]
    ) -> None:
        """Displays the popup project selection menu."""
        self.project_ctrl.show_project_menu(btn_anchor, switch_cb, new_dialog_cb, window)

    def open_new_project_dialog(
        self,
        window: QWidget,
        curr_target: str,
        curr_attacker: str,
        curr_port: str,
        switch_cb: Callable[[str], None]
    ) -> None:
        """Opens the project creation dialog."""
        self.project_ctrl.open_new_project_dialog(
            window, curr_target, curr_attacker, curr_port, switch_cb
        )

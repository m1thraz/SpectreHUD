"""
Workspace Coordinator for SpectreHUD.

Coordinates project workspaces, session state persistence, and project menu interactions.
"""

from typing import Optional, Dict, Callable
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QPushButton, QMessageBox

from core.project import ProjectManager
from core.project.validator import WorkspaceError, validate_workspace_directory
from core.config import ConfigManager
from core.project_session_service import ProjectSessionService
from core.event_bus import EventBus, EventType
from core.i18n import t
from core.logger import get_logger
from ui.controllers.project_controller import ProjectController
from ui.project_dialog import ProjectUnlockDialog
from core.project_lock_service import ProjectSecurityMetaError
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
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.project_manager = project_manager
        self.session_service = session_service
        self.project_ctrl = project_ctrl
        self.report_ctrl = report_ctrl
        self.event_bus = event_bus

    def load_active_project_session(self, window: Optional[QWidget] = None) -> Dict[str, str]:
        """Loads and returns the variable state for the currently active project."""
        active_proj = self.project_manager.get_active_project()
        if not self._unlock_project_if_needed(active_proj, window):
            return {}
        return self.session_service.load_project_session(active_proj)

    def _unlock_project_if_needed(self, project_name: str, window: Optional[QWidget]) -> bool:
        """Prompt only when a Pentest-Mode project lacks its in-memory session key."""
        try:
            needs_unlock = self.project_manager.is_pentest_mode(
                project_name
            ) and not self.project_manager.is_project_unlocked(project_name)
        except ProjectSecurityMetaError as exc:
            logger.error("Invalid Pentest-Mode metadata for '%s': %s", project_name, exc)
            if window is not None:
                QMessageBox.critical(window, "Pentest-Modus fehlerhaft", str(exc))
                return False
            raise
        if not needs_unlock:
            return True
        if window is None:
            return False
        while True:
            dialog = ProjectUnlockDialog(project_name, parent=window)
            if not dialog.exec():
                return False
            try:
                if self.project_manager.unlock_project(project_name, dialog.get_password()):
                    return True
            except ProjectSecurityMetaError as exc:
                QMessageBox.critical(window, "Pentest-Modus fehlerhaft", str(exc))
                return False
            QMessageBox.warning(
                window, "Entsperren fehlgeschlagen", "Das Passwort ist nicht korrekt."
            )

    def save_current_project_session(self, variables: Dict[str, str]) -> bool:
        """Persists the variable state for the currently active project."""
        return self.session_service.save_project_session(variables)

    def switch_to_project(
        self,
        project_name: str,
        window: QWidget,
        variables_provider: Callable[[], Dict[str, str]],
        on_success_callback: Optional[Callable[[str], None]] = None,
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
            logger.error(
                f"Failed to persist state for project '{current_proj}' before switching to '{project_name}'"
            )
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
            msg.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
            )
            msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
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
                t(
                    "project.not_found_msg",
                    f"Project '{project_name}' does not exist and cannot be activated.\n\n{activate_err}",
                ),
            )
            self.project_ctrl.update_project_combo()
            return False

        # The target is verified before the active project's key is cleared.
        if not self._unlock_project_if_needed(project_name, window):
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

    def apply_workspace_setting(
        self,
        workspace_dir: str,
        config: ConfigManager,
        window: QWidget,
        load_session: Callable[[], None],
        refresh_filters: Callable[[], None],
        refresh_content: Callable[[], None],
    ) -> bool:
        """Apply and persist a workspace switch as one rollback-capable transaction."""
        try:
            new_workspace = validate_workspace_directory(workspace_dir)
        except WorkspaceError as exc:
            logger.error("Failed to switch to new workspace directory: %s", exc)
            QMessageBox.warning(
                window,
                t("general.workspace_error", "Workspace Error"),
                f"Failed to set workspace directory:\n{exc}",
            )
            return False

        if new_workspace == self.project_manager.base_dir.resolve():
            return True

        old_base = self.project_manager.base_dir
        old_active = self.project_manager.get_active_project()
        try:
            self.project_manager.base_dir = new_workspace
            available = self.project_manager.list_projects()
            workspace_projects = [
                name
                for name in available
                if (new_workspace / name).is_dir() and not (new_workspace / name).is_symlink()
            ]
            if old_active not in workspace_projects:
                selected = workspace_projects[0] if workspace_projects else "Default"
                self.project_manager.activate_project(selected)
                if workspace_projects:
                    logger.info(
                        "Active project '%s' not found in new workspace; switched to '%s'.",
                        old_active,
                        selected,
                    )

            load_session()
            refresh_filters()
            refresh_content()
            config.set("workspace_dir", str(new_workspace))
            if not workspace_projects:
                self.project_manager.create_project("Default", allow_existing=True)
            try:
                self.project_manager.sync_registry()
            except Exception:
                logger.exception("Workspace switched, but registry synchronization was deferred.")
            return True
        except Exception as switch_err:
            logger.error("Workspace switch failed, rolling back: %s", switch_err)
            try:
                self.project_manager.base_dir = old_base
                self.project_manager.activate_project(old_active)
                load_session()
                refresh_filters()
                refresh_content()
            except Exception as restore_err:
                logger.exception(
                    "Failed to restore previous workspace session after switch failure."
                )
                QMessageBox.critical(
                    window,
                    t("general.workspace_error", "Workspace Error"),
                    t(
                        "general.workspace_restore_failed",
                        "The workspace switch failed and the previous session could not be restored safely. "
                        "Please restart SpectreHUD before making further changes.\n\n"
                        f"Switch error: {switch_err}\nRestore error: {restore_err}",
                    ),
                )
                return False
            QMessageBox.warning(
                window,
                t("general.workspace_error", "Workspace Error"),
                t(
                    "general.workspace_switch_failed",
                    f"Failed to switch workspace directory:\n{switch_err}\n\nThe previous workspace has been restored.",
                ),
            )
            return False

    def show_project_menu(
        self,
        btn_anchor: QPushButton,
        window: QWidget,
        switch_cb: Callable[[str], None],
        new_dialog_cb: Callable[[], None],
    ) -> None:
        """Displays the popup project selection menu."""
        self.project_ctrl.show_project_menu(btn_anchor, switch_cb, new_dialog_cb, window)

    def open_new_project_dialog(
        self,
        window: QWidget,
        curr_target: str,
        curr_attacker: str,
        curr_port: str,
        switch_cb: Callable[[str], None],
    ) -> None:
        """Opens the project creation dialog."""
        self.project_ctrl.open_new_project_dialog(
            window, curr_target, curr_attacker, curr_port, switch_cb
        )

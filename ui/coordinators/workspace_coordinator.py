"""
Workspace Coordinator for SpectreHUD.

Coordinates project workspaces, session state persistence, and project menu interactions.
"""

from typing import Optional, Dict, Callable
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QPushButton, QMessageBox

from core.project import ProjectManager, ProjectState, ProjectStateLoadError
from core.project import PersistFailureReason
from core.project import WorkspaceError, validate_workspace_directory
from core.project import (
    WorkspaceApplicationService,
    WorkspaceSwitchFailureReason,
    WorkspaceSwitchResult,
)
from core.config import ConfigManager
from core.project import ProjectSessionService
from core.event_bus import EventBus
from core.i18n import t
from core.logger import get_logger
from ui.controllers.project_controller import ProjectController
from ui.project_dialog import ProjectUnlockDialog
from core.project import ProjectSecurityMetaError
from ui.controllers.report_controller import ReportController
from ui.message_boxes import ask_confirmation, show_error_dialog, show_warning_dialog

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
        workspace_service: Optional[WorkspaceApplicationService] = None,
    ):
        super().__init__(parent)
        self.project_manager = project_manager
        self.session_service = session_service
        self.project_ctrl = project_ctrl
        self.report_ctrl = report_ctrl
        self.event_bus = event_bus
        self.workspace_service = workspace_service or WorkspaceApplicationService(
            project_manager=self.project_manager,
            session_service=self.session_service,
            report_loader=self.report_ctrl.load_project,
            event_bus=self.event_bus,
        )
        self._last_unlock_cancelled = False

    def load_active_project_session(
        self, window: Optional[QWidget] = None
    ) -> Optional[ProjectState]:
        """Loads and returns the variable state for the currently active project."""
        active_proj = self.project_manager.get_active_project()
        if not self._unlock_project_if_needed(active_proj, window):
            return None
        try:
            return self.session_service.load_project_session(active_proj)
        except ProjectStateLoadError as exc:
            logger.error("Could not load project state for '%s': %s", active_proj, exc)
            if window is None:
                raise
            schema_mismatch = exc.failure_reason is PersistFailureReason.SCHEMA_MISMATCH
            show_error_dialog(
                window,
                t(
                    "project.schema_mismatch_title"
                    if schema_mismatch
                    else "project.state_corrupted_title",
                    "Unsupported project state" if schema_mismatch else "Project state unreadable",
                ),
                t(
                    "project.schema_mismatch_msg"
                    if schema_mismatch
                    else "project.state_corrupted_msg",
                    (
                        "The project state for '{project}' uses an unsupported schema. SpectreHUD "
                        "did not replace it or clear the current session."
                        if schema_mismatch
                        else "The saved state for '{project}' is damaged or too large. SpectreHUD "
                        "did not replace it or clear the current session. Restore project_state.json "
                        "from a backup before continuing."
                    ),
                    project=active_proj,
                ),
                details=str(exc),
            )
            return None

    def _unlock_project_if_needed(self, project_name: str, window: Optional[QWidget]) -> bool:
        """Prompt only when a Pentest-Mode project lacks its in-memory session key."""
        try:
            needs_unlock = self.project_manager.is_pentest_mode(
                project_name
            ) and not self.project_manager.is_project_unlocked(project_name)
        except (ProjectSecurityMetaError, ProjectStateLoadError) as exc:
            logger.error("Invalid Pentest-Mode metadata for '%s': %s", project_name, exc)
            if window is not None:
                show_error_dialog(
                    window,
                    t("project.pentest_meta_error_title", "Pentest-Modus fehlerhaft"),
                    str(exc),
                )
                return False
            raise
        if not needs_unlock:
            return True
        if window is None:
            return False
        while True:
            dialog = ProjectUnlockDialog(project_name, parent=window)
            if not dialog.exec():
                self._last_unlock_cancelled = True
                return False
            try:
                if self.project_manager.unlock_project(project_name, dialog.get_password()):
                    return True
            except ProjectSecurityMetaError as exc:
                show_error_dialog(
                    window,
                    t("project.pentest_meta_error_title", "Pentest-Modus fehlerhaft"),
                    str(exc),
                )
                return False
            show_warning_dialog(
                window,
                t("project.unlock_failed_title", "Entsperren fehlgeschlagen"),
                t("project.unlock_failed_msg", "Das Passwort ist nicht korrekt."),
            )

    def save_current_project_session(self, variables: Dict[str, str]) -> bool:
        """Persists the variable state for the currently active project."""
        result = self.session_service.save_project_session(variables)
        self._last_save_failure_reason = result.failure_reason
        return result.success

    @staticmethod
    def _failure_reason_label(reason: Optional[PersistFailureReason]) -> str:
        return reason.value.replace("_", " ") if reason else "unknown"

    def switch_to_project(
        self,
        project_name: str,
        window: QWidget,
        variables_provider: Callable[[], Dict[str, str]],
        on_success_callback: Optional[Callable[[str], None]] = None,
    ) -> WorkspaceSwitchResult:
        """
        Coordinates dirty checks and user prompts, delegating atomic switching
        and rollback to WorkspaceApplicationService.
        """
        current_proj = self.project_manager.get_active_project()
        if project_name == current_proj:
            return WorkspaceSwitchResult(
                success=False,
                previous_project=current_proj,
                active_project=current_proj,
                failure_reason=WorkspaceSwitchFailureReason.SAME_PROJECT,
            )

        if not self.report_ctrl.confirm_discard_if_dirty():
            return WorkspaceSwitchResult(
                success=False,
                previous_project=current_proj,
                active_project=current_proj,
                failure_reason=None,
            )

        variables = variables_provider() if variables_provider is not None else {}

        def unlock_callback(pname: str) -> str:
            self._last_unlock_cancelled = False
            unlocked = self._unlock_project_if_needed(pname, window)
            if unlocked:
                return "success"
            if getattr(self, "_last_unlock_cancelled", False):
                return "cancelled"
            return "failed"

        result = self.workspace_service.switch_to_project(
            project_name,
            variables=variables,
            force_discard=False,
            unlock_callback=unlock_callback,
        )

        if (
            not result.success
            and result.failure_reason is WorkspaceSwitchFailureReason.PRE_SWITCH_SAVE_FAILED
        ):
            logger.error(
                "Failed to persist state for project '%s' before switching to '%s'",
                current_proj,
                project_name,
            )
            project_unavailable = not self.project_manager.project_exists(current_proj)
            if project_unavailable:
                message = t(
                    "workspace.switch_folder_missing",
                    "Der Projektordner des aktiven Projekts '{project}' wurde außerhalb von SpectreHUD "
                    "verschoben oder gelöscht. SpectreHUD hat ihn nicht neu erstellt.\n\n"
                    "Möchtest du den Projektwechsel trotzdem fortsetzen und ungespeicherte Änderungen verwerfen?",
                    project=current_proj,
                )
            else:
                base_message = t(
                    "workspace.switch_save_failed",
                    "Der Zustand des aktuellen Projekts '{project}' konnte nicht auf der Festplatte gespeichert werden.\n\n"
                    "Möchtest du den Projektwechsel trotzdem fortsetzen und ungespeicherte Änderungen verwerfen?",
                    project=current_proj,
                )
                save_reason = getattr(self, "_last_save_failure_reason", None)
                message = (
                    f"{base_message}\n\n"
                    f"({self._failure_reason_label(save_reason)})"
                )
            reply = ask_confirmation(
                window,
                t("general.save_failed", "Speichern fehlgeschlagen"),
                message,
                buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                default_button=QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Yes:
                result = self.workspace_service.switch_to_project(
                    project_name,
                    variables=variables,
                    force_discard=True,
                    unlock_callback=unlock_callback,
                )

        if not result.success:
            self._present_switch_failure(result, project_name, window)
            self.project_ctrl.update_project_combo()
            return result

        if on_success_callback:
            on_success_callback(project_name)

        self.project_changed.emit(project_name)
        return result

    def _present_switch_failure(
        self,
        result: WorkspaceSwitchResult,
        target_project: str,
        window: Optional[QWidget],
    ) -> None:
        if window is None or result.failure_reason is WorkspaceSwitchFailureReason.UNLOCK_CANCELLED:
            return

        if result.failure_reason in (
            WorkspaceSwitchFailureReason.TARGET_NOT_FOUND,
            WorkspaceSwitchFailureReason.ACTIVATION_FAILED,
        ):
            show_error_dialog(
                window,
                t("general.error", "Error"),
                t(
                    "project.not_found_msg",
                    f"Project '{target_project}' does not exist and cannot be activated.\n\n{result.error_message or ''}",
                ),
            )
        elif result.failure_reason is WorkspaceSwitchFailureReason.REPORT_LOAD_FAILED:
            show_error_dialog(
                window,
                t("general.error", "Error"),
                f"Failed to load the report for project '{target_project}'. The previous project has been restored.\n\n{result.error_message or ''}",
            )
        elif result.failure_reason is WorkspaceSwitchFailureReason.SESSION_LOAD_FAILED:
            show_error_dialog(
                window,
                t("general.error", "Error"),
                f"Failed to load session for project '{target_project}'. The previous project has been restored.\n\n{result.error_message or ''}",
            )
        elif result.failure_reason is WorkspaceSwitchFailureReason.UNLOCK_FAILED:
            if result.error_message:
                show_error_dialog(
                    window,
                    t("project.pentest_meta_error_title", "Pentest-Modus fehlerhaft"),
                    result.error_message,
                )

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
            show_error_dialog(
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
                show_error_dialog(
                    window,
                    t("general.workspace_error", "Workspace Error"),
                    t(
                        "general.workspace_restore_failed",
                        "The workspace switch failed and the previous session could not be restored safely. "
                        "Please restart SpectreHUD before making further changes.\n\n"
                        "Switch error: {switch_err}\nRestore error: {restore_err}",
                        switch_err=switch_err,
                        restore_err=restore_err,
                    ),
                )
                return False
            show_error_dialog(
                window,
                t("general.workspace_error", "Workspace Error"),
                t(
                    "general.workspace_switch_failed",
                    "Failed to switch workspace directory:\n{switch_err}\n\nThe previous workspace has been restored.",
                    switch_err=switch_err,
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

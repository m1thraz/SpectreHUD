"""
Headless workspace application service for SpectreHUD.

Orchestrates atomic project switching: validation, state persistence,
activation, Pentest-Mode unlocking, report loading, and session state loading
with guaranteed rollback to the previous project on any failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional

from core.event_bus import EventBus, EventType, ProjectChangedPayload
from core.logger import get_logger
from core.project.manager import ProjectManager
from core.project.session_service import ProjectSessionService
from core.project.state_store import ProjectState, ProjectStateLoadError
from core.project.validator import ProjectError, validate_project_name

logger = get_logger("workspace_service")


class WorkspaceSwitchFailureReason(Enum):
    """Specific failure reasons for project switching."""

    SAME_PROJECT = "same_project"
    TARGET_NOT_FOUND = "target_not_found"
    PRE_SWITCH_SAVE_FAILED = "pre_switch_save_failed"
    ACTIVATION_FAILED = "activation_failed"
    UNLOCK_CANCELLED = "unlock_cancelled"
    UNLOCK_FAILED = "unlock_failed"
    REPORT_LOAD_FAILED = "report_load_failed"
    SESSION_LOAD_FAILED = "session_load_failed"


@dataclass(frozen=True)
class WorkspaceSwitchResult:
    """Typed outcome of a project switch operation."""

    success: bool
    previous_project: str
    active_project: str
    failure_reason: Optional[WorkspaceSwitchFailureReason] = None
    rollback_performed: bool = False
    error_message: Optional[str] = None
    state: Optional[ProjectState] = None

    def __bool__(self) -> bool:
        """Allow transparent truthiness checking (if switch_result: ...)."""
        return self.success


class WorkspaceApplicationService:
    """
    Coordinates project transitions as a single rollback-capable atomic operation.

    Keeps pure business and transaction orchestration separated from UI dialogs,
    QMessageBox prompts, and localized presentation strings.
    """

    def __init__(
        self,
        project_manager: ProjectManager,
        session_service: ProjectSessionService,
        report_loader: Optional[Callable[[str], None]] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.project_manager = project_manager
        self.session_service = session_service
        self.report_loader = report_loader
        self.event_bus = event_bus

    def switch_to_project(
        self,
        project_name: str,
        *,
        variables: Optional[Dict[str, str]] = None,
        force_discard: bool = False,
        unlock_callback: Optional[Callable[[str], Any]] = None,
    ) -> WorkspaceSwitchResult:
        """
        Execute an atomic switch to project_name.

        Returns a WorkspaceSwitchResult detailing success or exact failure reason,
        and guarantees rollback to previous_project if any step fails.
        """
        current_project = self.project_manager.get_active_project()

        if project_name == current_project:
            return WorkspaceSwitchResult(
                success=False,
                previous_project=current_project,
                active_project=current_project,
                failure_reason=WorkspaceSwitchFailureReason.SAME_PROJECT,
            )

        # 1. Validate target name and existence
        try:
            clean_name = validate_project_name(project_name)
            if clean_name not in self.project_manager.list_projects():
                return WorkspaceSwitchResult(
                    success=False,
                    previous_project=current_project,
                    active_project=current_project,
                    failure_reason=WorkspaceSwitchFailureReason.TARGET_NOT_FOUND,
                    error_message=f"Project '{project_name}' does not exist.",
                )
        except (ProjectError, ValueError) as exc:
            return WorkspaceSwitchResult(
                success=False,
                previous_project=current_project,
                active_project=current_project,
                failure_reason=WorkspaceSwitchFailureReason.TARGET_NOT_FOUND,
                error_message=str(exc),
            )

        # 2. Persist previous project session if variables are supplied
        if variables is not None:
            save_result = self.session_service.save_project_session(
                variables, project_name=current_project
            )
            if not save_result.success and not force_discard:
                logger.error(
                    "Failed to persist state for '%s' before switching to '%s'",
                    current_project,
                    clean_name,
                )
                return WorkspaceSwitchResult(
                    success=False,
                    previous_project=current_project,
                    active_project=current_project,
                    failure_reason=WorkspaceSwitchFailureReason.PRE_SWITCH_SAVE_FAILED,
                    error_message=f"Failed to persist state for project '{current_project}'",
                )

        # Snapshot the previous project's in-memory session key for rollback
        previous_key = self.project_manager.lock_service.get_session_key(current_project)

        # 3. Activate the target project
        try:
            self.project_manager.activate_project(clean_name)
        except Exception as exc:
            logger.error("Failed to activate project '%s': %s", clean_name, exc)
            return WorkspaceSwitchResult(
                success=False,
                previous_project=current_project,
                active_project=current_project,
                failure_reason=WorkspaceSwitchFailureReason.ACTIVATION_FAILED,
                error_message=str(exc),
            )

        # 4. Check if target requires Pentest-Mode unlock
        try:
            needs_unlock = (
                self.project_manager.is_pentest_mode(clean_name)
                and not self.project_manager.is_project_unlocked(clean_name)
            )
        except Exception as exc:
            logger.error("Error inspecting security metadata for '%s': %s", clean_name, exc)
            self._rollback(current_project, previous_key)
            return WorkspaceSwitchResult(
                success=False,
                previous_project=current_project,
                active_project=current_project,
                failure_reason=WorkspaceSwitchFailureReason.UNLOCK_FAILED,
                rollback_performed=True,
                error_message=str(exc),
            )

        if needs_unlock:
            if unlock_callback is None:
                logger.warning("Target '%s' needs unlock but no unlock_callback was provided.", clean_name)
                self._rollback(current_project, previous_key)
                return WorkspaceSwitchResult(
                    success=False,
                    previous_project=current_project,
                    active_project=current_project,
                    failure_reason=WorkspaceSwitchFailureReason.UNLOCK_FAILED,
                    rollback_performed=True,
                    error_message="No unlock handler provided for encrypted project.",
                )

            try:
                outcome = unlock_callback(clean_name)
            except Exception as exc:
                logger.error("Unlock handler raised exception for '%s': %s", clean_name, exc)
                self._rollback(current_project, previous_key)
                return WorkspaceSwitchResult(
                    success=False,
                    previous_project=current_project,
                    active_project=current_project,
                    failure_reason=WorkspaceSwitchFailureReason.UNLOCK_FAILED,
                    rollback_performed=True,
                    error_message=str(exc),
                )

            # Interpret outcome: string "cancelled", boolean False/"failed", or True/"success"
            if outcome == "cancelled":
                logger.info("Unlock for '%s' was cancelled; rolling back.", clean_name)
                self._rollback(current_project, previous_key, report_loaded=False)
                return WorkspaceSwitchResult(
                    success=False,
                    previous_project=current_project,
                    active_project=current_project,
                    failure_reason=WorkspaceSwitchFailureReason.UNLOCK_CANCELLED,
                    rollback_performed=True,
                )
            elif outcome is not True and outcome != "success":
                logger.warning("Unlock for '%s' failed; rolling back.", clean_name)
                self._rollback(current_project, previous_key, report_loaded=False)
                return WorkspaceSwitchResult(
                    success=False,
                    previous_project=current_project,
                    active_project=current_project,
                    failure_reason=WorkspaceSwitchFailureReason.UNLOCK_FAILED,
                    rollback_performed=True,
                )

        # 5. Load target report
        report_loaded = False
        if self.report_loader is not None:
            try:
                self.report_loader(clean_name)
                report_loaded = True
            except Exception as exc:
                logger.error("Failed to load report for '%s', rolling back: %s", clean_name, exc)
                self._rollback(current_project, previous_key, report_loaded=False)
                return WorkspaceSwitchResult(
                    success=False,
                    previous_project=current_project,
                    active_project=current_project,
                    failure_reason=WorkspaceSwitchFailureReason.REPORT_LOAD_FAILED,
                    rollback_performed=True,
                    error_message=str(exc),
                )

        # 6. Load target session state
        try:
            loaded_state = self.session_service.load_project_session(clean_name)
        except ProjectStateLoadError as exc:
            logger.error("Failed to load session for '%s', rolling back: %s", clean_name, exc)
            self._rollback(current_project, previous_key, report_loaded=report_loaded)
            return WorkspaceSwitchResult(
                success=False,
                previous_project=current_project,
                active_project=current_project,
                failure_reason=WorkspaceSwitchFailureReason.SESSION_LOAD_FAILED,
                rollback_performed=True,
                error_message=str(exc),
            )
        except Exception as exc:
            logger.exception("Unexpected error loading session for '%s', rolling back: %s", clean_name, exc)
            self._rollback(current_project, previous_key, report_loaded=report_loaded)
            return WorkspaceSwitchResult(
                success=False,
                previous_project=current_project,
                active_project=current_project,
                failure_reason=WorkspaceSwitchFailureReason.SESSION_LOAD_FAILED,
                rollback_performed=True,
                error_message=str(exc),
            )

        # 7. Notify completion via EventBus
        if self.event_bus is not None:
            self.event_bus.publish(
                EventType.PROJECT_CHANGED,
                ProjectChangedPayload(project_name=clean_name, phase="loaded"),
            )

        return WorkspaceSwitchResult(
            success=True,
            previous_project=current_project,
            active_project=clean_name,
            rollback_performed=False,
            state=loaded_state,
        )

    def _rollback(
        self,
        previous_project: str,
        previous_key: Optional[bytes],
        *,
        report_loaded: bool = False,
    ) -> None:
        """
        Roll back active project, encryption key, report, and session to the previous project.
        """
        logger.info("Executing rollback to previous project '%s'", previous_project)
        try:
            self.project_manager.activate_project(previous_project)
            if previous_key is not None:
                self.project_manager.lock_service.set_session_key(previous_project, previous_key)

            if report_loaded and self.report_loader is not None:
                try:
                    self.report_loader(previous_project)
                except Exception:
                    logger.exception("Failed to restore report for '%s' during rollback", previous_project)

            try:
                self.session_service.load_project_session(previous_project)
            except Exception:
                logger.exception("Failed to restore session for '%s' during rollback", previous_project)
        except Exception:
            logger.exception("Critical error during rollback to '%s'", previous_project)

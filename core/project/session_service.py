from typing import Any, Callable, Dict, List, Optional

from core.project import ProjectManager, ProjectStateLoadError
from core.project.persistence import PersistFailureReason, PersistResult
from core.loot.manager import LootManager
from core.clipboard_history import ClipboardHistory
from core.logger import get_logger
from core.phases import VALID_PHASE_KEYS, try_normalize_phase_key
from core.validators import validate_clipboard_list, validate_loot_list, validate_quick_notes_list

logger = get_logger("project_session_service")


class ProjectSessionValidationError(ProjectStateLoadError):
    def __init__(self, component: str):
        super().__init__(
            f"Project session component '{component}' is invalid.",
            PersistFailureReason.VALIDATION_FAILED,
        )


class ProjectSessionService:
    """
    Orchestrates loading, saving, restoring, and isolating project-related runtime state
    (Target variables, session loot, clipboard history, quick notes) across CTF box workspaces.
    """

    def __init__(
        self,
        project_manager: ProjectManager,
        loot_manager: LootManager,
        clipboard_history: ClipboardHistory,
        quick_note_manager: Optional[Any] = None,
        phase_context: Optional[Any] = None,
    ):
        self.project_manager = project_manager
        self.loot_manager = loot_manager
        self.clipboard_history = clipboard_history
        self.quick_note_manager = quick_note_manager
        self.phase_context = phase_context

    def load_project_session(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Loads the persisted state for the given project (or active project)
        and populates the LootManager, ClipboardHistory, QuickNoteManager, and PhaseContext.
        """
        pname = project_name or self.project_manager.get_active_project()
        try:
            state = self.project_manager.load_project_state(name=pname)
        except ProjectStateLoadError:
            logger.error("Refusing to replace the live session with corrupted state for '%s'.", pname)
            raise

        staged_loot = self._validate_list_component(
            "loot", state.get("loot"), validate_loot_list
        )
        staged_history = self._validate_list_component(
            "clipboard_history", state.get("clipboard_history"), validate_clipboard_list
        )
        staged_notes = self._validate_list_component(
            "quick_notes", state.get("quick_notes"), validate_quick_notes_list
        )
        staged_phase = self._validate_phase(state.get("active_phase"))

        previous_loot = self.loot_manager.get_all_entries()
        previous_history = self.clipboard_history.get_all_history()
        previous_notes = (
            self.quick_note_manager.get_all_entries() if self.quick_note_manager else []
        )
        previous_phase = self.phase_context.active_phase_id if self.phase_context else None

        try:
            self.loot_manager.replace_entries(staged_loot)
            self.clipboard_history.replace_history(staged_history)
            if self.quick_note_manager:
                self.quick_note_manager.replace_entries(staged_notes)
            self._replace_phase(staged_phase)
        except Exception as exc:
            logger.exception("Session apply failed for '%s'; restoring previous runtime state.", pname)
            self._restore_runtime_state(
                previous_loot,
                previous_history,
                previous_notes,
                previous_phase,
            )
            raise ProjectSessionValidationError("runtime_apply") from exc
        return state

    @staticmethod
    def _validate_list_component(
        name: str,
        raw_value: Any,
        validator: Callable[[Any], List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        if not isinstance(raw_value, list):
            raise ProjectSessionValidationError(name)
        try:
            validated = validator(raw_value)
        except Exception as exc:
            raise ProjectSessionValidationError(name) from exc
        if len(validated) != len(raw_value):
            raise ProjectSessionValidationError(name)
        return validated

    @staticmethod
    def _validate_phase(raw_phase: Any) -> Optional[str]:
        if raw_phase in (None, ""):
            return None
        try:
            normalized = try_normalize_phase_key(str(raw_phase))
        except (TypeError, ValueError) as exc:
            raise ProjectSessionValidationError("active_phase") from exc
        if normalized not in VALID_PHASE_KEYS:
            raise ProjectSessionValidationError("active_phase")
        return normalized

    def _replace_phase(self, phase_id: Optional[str]) -> None:
        if not self.phase_context:
            return
        if phase_id is None:
            self.phase_context.clear_active_phase(source="project_load")
        else:
            self.phase_context.set_active_phase(phase_id, source="project_load")

    def _restore_runtime_state(
        self,
        loot: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
        notes: List[Dict[str, Any]],
        phase_id: Optional[str],
    ) -> None:
        restorers = [
            lambda: self.loot_manager.replace_entries(loot),
            lambda: self.clipboard_history.replace_history(history),
        ]
        note_manager = self.quick_note_manager
        if note_manager is not None:
            restorers.append(lambda: note_manager.replace_entries(notes))
        restorers.append(lambda: self._replace_phase(phase_id))
        for restore in restorers:
            try:
                restore()
            except Exception:
                logger.exception("Failed to restore one runtime component after session apply failure.")

    def save_project_session(
        self, variables: Dict[str, str], project_name: Optional[str] = None
    ) -> PersistResult[None]:
        """
        Persists the current runtime session state (target variables, session loot,
        clipboard history, quick notes, active phase) into the project's project_state.json.
        Returns the typed persistence outcome.
        """
        pname = project_name or self.project_manager.get_active_project()
        state = {
            "target_ip": variables.get("target_ip", "10.10.10.10"),
            "attacker_ip": variables.get("attacker_ip", "10.10.14.5"),
            "port": variables.get("port", "4444"),
            "username": variables.get("username", ""),
            "password": variables.get("password", ""),
            "loot": self.loot_manager.get_all_entries(),
            "clipboard_history": self.clipboard_history.get_all_history(),
            "quick_notes": (
                self.quick_note_manager.get_all_entries() if self.quick_note_manager else []
            ),
            "active_phase": (
                self.phase_context.active_phase_id if self.phase_context else None
            ),
        }
        return self.project_manager.save_project_state(name=pname, state=state)

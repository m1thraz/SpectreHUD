from typing import Dict, Any, Optional
from core.project import ProjectManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.logger import get_logger

logger = get_logger("project_session_service")


class ProjectSessionService:
    """
    Orchestrates loading, saving, restoring, and isolating project-related runtime state
    (Target variables, session loot, clipboard history) across CTF box workspaces.
    """

    def __init__(
        self,
        project_manager: ProjectManager,
        loot_manager: LootManager,
        clipboard_watcher: ClipboardWatcher,
    ):
        self.project_manager = project_manager
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher

    def load_project_session(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Loads the persisted state for the given project (or active project)
        and populates the LootManager and ClipboardWatcher.
        """
        pname = project_name or self.project_manager.get_active_project()
        state = self.project_manager.load_project_state(name=pname)
        if state:
            self.loot_manager.replace_entries(state.get("loot", []))
            self.clipboard_watcher.replace_history(state.get("clipboard_history", []))
        else:
            self.loot_manager.replace_entries([])
            self.clipboard_watcher.replace_history([])
        return state or {}

    def save_project_session(
        self, variables: Dict[str, str], project_name: Optional[str] = None
    ) -> bool:
        """
        Persists the current runtime session state (target variables, session loot,
        clipboard history) into the project's project_state.json.
        Returns True on successful save, False otherwise.
        """
        pname = project_name or self.project_manager.get_active_project()
        state = {
            "target_ip": variables.get("target_ip", "10.10.10.10"),
            "attacker_ip": variables.get("attacker_ip", "10.10.14.5"),
            "port": variables.get("port", "4444"),
            "username": variables.get("username", ""),
            "password": variables.get("password", ""),
            "loot": self.loot_manager.get_all_entries(),
            "clipboard_history": self.clipboard_watcher.get_all_history(),
        }
        return self.project_manager.save_project_state(name=pname, state=state)

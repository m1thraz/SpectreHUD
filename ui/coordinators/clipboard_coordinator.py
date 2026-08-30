"""
Clipboard Coordinator for SpectreHUD.

Coordinates clipboard logging, history capture, and conversions from history to loot.
"""

from typing import Optional, Dict, Any, Callable
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget

from core.clipboard_watcher import ClipboardWatcher
from core.loot_manager import LootManager
from core.project import ProjectManager
from core.logger import get_logger
from ui.controllers.history_controller import HistoryController
from ui.controllers.loot_controller import LootController

logger = get_logger(__name__)


class ClipboardCoordinator(QObject):
    """Manages clipboard logging lifecycles, history mutations, and loot conversion."""

    history_mutated = pyqtSignal()
    loot_mutated = pyqtSignal()

    def __init__(
        self,
        clipboard_watcher: ClipboardWatcher,
        history_ctrl: HistoryController,
        loot_ctrl: LootController,
        target_provider: Callable[[], str],
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.clipboard_watcher = clipboard_watcher
        self.history_ctrl = history_ctrl
        self.loot_ctrl = loot_ctrl
        self.target_provider = target_provider

        self.clipboard_watcher.set_target_provider(self.target_provider)

    def toggle_pause(self) -> None:
        """Toggles clipboard history recording pause/resume state."""
        self.history_ctrl.toggle_pause()

    def on_clipboard_entry_added(self, entry: Dict[str, Any]) -> None:
        """Handles a newly captured clipboard history item."""
        self.history_mutated.emit()

    def delete_history_entry(self, entry_id: str) -> None:
        """Deletes an entry from clipboard history."""
        self.history_ctrl.delete_entry(entry_id)
        self.history_mutated.emit()

    def add_history_to_loot(self, window: QWidget, history_item: Dict[str, Any]) -> bool:
        """Opens the loot creation dialog prefilled from a history item."""
        target_ip = history_item.get("target_ip") or self.target_provider()
        success = self.loot_ctrl.open_add_dialog(
            parent_widget=window,
            target_ip=target_ip,
            default_type="credentials" if history_item.get("is_command") else "note",
            default_category="access" if history_item.get("is_command") else "recon",
            default_title=f"Kopiert aus Terminal ({history_item.get('timestamp', '')})",
            default_content=history_item.get("text", "")
        )
        if success:
            self.loot_mutated.emit()
        return success

    def clear_history(self, window: QWidget) -> bool:
        """Clears all clipboard history entries after user confirmation."""
        if self.history_ctrl.clear_history(window):
            self.history_mutated.emit()
            return True
        return False

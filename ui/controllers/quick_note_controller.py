"""
Quick Note Controller for SpectreHUD.

Coordinates the QuickNotePopup, quick note persistence, promotion to loot,
and UI inbox synchronization.
"""

from typing import Optional, Callable, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget

from core.quick_note_manager import QuickNoteManager
from core.loot_manager import VALID_CATEGORY_IDS
from core.event_bus import EventBus, EventType
from core.logger import get_logger
from ui.quick_note_popup import QuickNotePopup

logger = get_logger("quick_note_controller")


class QuickNoteController(QObject):
    """
    Manages quick note capture popup lifecycle, persistence, and loot promotion.
    """

    note_added = pyqtSignal(dict)
    notes_updated = pyqtSignal()

    def __init__(
        self,
        quick_note_manager: QuickNoteManager,
        loot_controller: Optional[Any] = None,
        target_provider: Optional[Callable[[], str]] = None,
        event_bus: Optional[EventBus] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.quick_note_manager = quick_note_manager
        self.loot_controller = loot_controller
        self.target_provider = target_provider
        self.event_bus = event_bus if event_bus is not None else EventBus()
        self.last_category: str = "misc"
        self._popup: Optional[QuickNotePopup] = None

        if self.event_bus:
            self.event_bus.subscribe(EventType.QUICK_NOTES_UPDATED, self._on_notes_updated)

    def _on_notes_updated(self, payload: Optional[Dict[str, Any]] = None) -> None:
        self.notes_updated.emit()

    def get_popup(self) -> QuickNotePopup:
        """Returns the lazily instantiated QuickNotePopup instance."""
        if self._popup is None:
            self._popup = QuickNotePopup(default_category=self.last_category)
            self._popup.note_submitted.connect(self.submit_note)
        return self._popup

    def show_popup(self) -> None:
        """Opens the QuickNote popup at current cursor position."""
        popup = self.get_popup()
        popup.show_at_cursor(default_category=self.last_category)

    def submit_note(self, text: str, category: str) -> Optional[Dict[str, Any]]:
        """Saves a newly submitted note from popup or other inputs."""
        clean_cat = category if category in VALID_CATEGORY_IDS else "misc"
        self.last_category = clean_cat

        target_ip = ""
        if self.target_provider:
            try:
                target_ip = self.target_provider() or ""
            except Exception as e:
                logger.warning(f"Failed to resolve target_ip from provider: {e}")

        try:
            entry = self.quick_note_manager.add_entry(
                text=text, category=clean_cat, target_ip=target_ip
            )
            if entry:
                self.note_added.emit(entry)
            return entry
        except Exception as e:
            logger.error(f"Failed to save quick note: {e}")
            return None

    def delete_note(self, entry_id: str) -> bool:
        """Deletes a quick note."""
        try:
            return self.quick_note_manager.delete_entry(entry_id)
        except Exception as e:
            logger.error(f"Failed to delete quick note {entry_id}: {e}")
            return False

    def promote_to_loot(
        self, entry: Dict[str, Any], parent_widget: Optional[QWidget] = None
    ) -> bool:
        """
        Promotes a quick note to a full Loot entry via AddLootDialog.
        If accepted, deletes the note from inbox.
        """
        if not self.loot_controller:
            logger.warning("No loot_controller configured for promotion.")
            return False

        entry_id = entry.get("id")
        text = entry.get("text", "")
        category = entry.get("category", "misc")
        target_ip = entry.get("target_ip", "")

        # Default title is the first sentence or first 30 chars
        first_line = text.split("\n")[0].strip()
        default_title = first_line[:30] if len(first_line) > 30 else first_line

        success = self.loot_controller.open_add_dialog(
            parent_widget=parent_widget,
            target_ip=target_ip,
            default_type="note",
            default_category=category,
            default_title=default_title,
            default_content=text,
        )

        if success and entry_id:
            self.delete_note(entry_id)
            return True
        return False

"""
Quick Note Controller for SpectreHUD.

Coordinates the QuickNotePopup, quick note persistence, promotion to loot,
and UI inbox synchronization.
"""

from typing import Optional, Callable, Dict, Any, List
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox

from core.quick_note_manager import QuickNoteManager
from core.loot_manager import VALID_CATEGORY_IDS
from core.event_bus import EventBus, EventType
from core.logger import get_logger
from core.i18n import t
from ui.quick_note_popup import QuickNotePopup
from ui.quick_note_card import QuickNoteCard

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
        self.current_category_filter: str = "all"
        self.filter_buttons: Dict[str, QPushButton] = {}
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

    @property
    def current_category(self) -> str:
        return self.last_category

    @current_category.setter
    def current_category(self, cat: str) -> None:
        self.last_category = cat if cat in VALID_CATEGORY_IDS else "misc"

    def add_entry(
        self, text: str, category: str = "misc", target_ip: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Directly adds a quick note entry."""
        clean_cat = category if category in VALID_CATEGORY_IDS else "misc"
        self.last_category = clean_cat
        resolved_target = (
            target_ip
            if target_ip is not None
            else (self.target_provider() if self.target_provider else "")
        )
        try:
            entry = self.quick_note_manager.add_entry(
                text=text, category=clean_cat, target_ip=resolved_target or ""
            )
            if entry:
                self.note_added.emit(entry)
            return entry
        except Exception as e:
            logger.error(f"Failed to add quick note entry: {e}")
            return None

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

    def select_filter(self, filter_id: str) -> None:
        """Selects active category filter and updates pill styles."""
        self.current_category_filter = filter_id
        for fid, btn in self.filter_buttons.items():
            btn.setProperty("class", "FilterPillActive" if fid == filter_id else "FilterPill")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def build_filter_pills(
        self,
        pills_layout: QHBoxLayout,
        on_select_filter: Callable[[str], None],
        on_clear: Callable[[], None],
    ) -> None:
        """Builds category filter pills and Clear action button for Notes mode."""
        self.filter_buttons.clear()
        all_notes = self.quick_note_manager.get_all_entries()

        pills = [("all", f"All ({len(all_notes)})")]
        for cat in ["recon", "access", "privesc", "postex", "scripts", "misc"]:
            count = sum(1 for n in all_notes if n.get("category") == cat)
            pills.append((cat, f"{cat.capitalize()} ({count})"))

        for pid, ptext in pills:
            btn = QPushButton(ptext)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty(
                "class",
                "FilterPillActive" if self.current_category_filter == pid else "FilterPill",
            )
            btn.clicked.connect(lambda checked=False, fid=pid: on_select_filter(fid))
            self.filter_buttons[pid] = btn
            pills_layout.addWidget(btn)

        pills_layout.addStretch()

        btn_clear = QPushButton("Clear")
        btn_clear.setProperty("class", "MiniDangerBtn")
        btn_clear.setToolTip(
            t("quick_note.clear_tip", "Clear all quick notes in the inbox for this project")
        )
        btn_clear.clicked.connect(on_clear)
        pills_layout.addWidget(btn_clear)

    def clear_all_notes(self, parent_widget: Optional[QWidget] = None) -> bool:
        """Deletes all quick notes in the current project after user confirmation."""
        if parent_widget:
            reply = QMessageBox.question(
                parent_widget,
                t("quick_note.clear_title", "Clear Quick Notes"),
                t(
                    "quick_note.clear_confirm",
                    "Are you sure you want to delete all quick notes in the inbox for this project?",
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        try:
            self.quick_note_manager.clear_entries()
            self.notes_updated.emit()
            return True
        except Exception as e:
            logger.error(f"Failed to clear quick notes: {e}")
            return False

    def render_content(
        self,
        content_layout: QVBoxLayout,
        search_query: str,
        on_copied: Optional[Callable[[str], None]],
        parent_widget: QWidget,
        show_empty_state_fn: Callable[[str], None],
    ) -> List[QWidget]:
        """Renders notes inbox cards into the content layout."""
        cat_filter = (
            None if self.current_category_filter == "all" else self.current_category_filter
        )
        notes = self.quick_note_manager.get_entries(
            category=cat_filter,
            search_query=search_query,
        )

        if not notes:
            show_empty_state_fn(
                t(
                    "quick_note.empty_state",
                    "No quick notes in inbox. Use global hotkey (Ctrl+Alt+N) or click '📌 Note' to capture thoughts.",
                )
            )
            return []

        rendered_cards: List[QWidget] = []
        for item in notes:
            card = QuickNoteCard(item, parent=parent_widget)
            card.promote_requested.connect(
                lambda entry, p=parent_widget: self.promote_to_loot(entry, parent_widget=p)
            )
            card.deleted.connect(self.delete_note)
            if on_copied is not None:
                card.copied.connect(on_copied)
            content_layout.addWidget(card)
            rendered_cards.append(card)

        return rendered_cards

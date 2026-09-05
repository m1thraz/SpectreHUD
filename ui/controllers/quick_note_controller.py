"""
Quick Note Controller for SpectreHUD.

Coordinates the QuickNotePopup, quick note persistence, promotion to loot,
reporting export, inline editing, status triage, pinning, and bulk actions.
"""

from typing import Optional, Callable, Dict, Any, List, Set
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QMessageBox,
    QFrame,
    QMenu,
)
from PyQt6.QtGui import QAction

from core.quick_note_manager import QuickNoteManager
from core.loot.manager import VALID_CATEGORY_IDS
from core.event_bus import EventBus, EventType
from core.logger import get_logger
from core.i18n import t
from ui.quick_note_popup import QuickNotePopup
from ui.quick_note_card import QuickNoteCard
from ui.quick_note_bulk_bar import QuickNoteBulkBar
from ui.note_selection_model import NoteSelectionModel

logger = get_logger("quick_note_controller")


class QuickNoteController(QObject):
    """
    Manages quick note capture popup lifecycle, persistence, triage workflow,
    inline editing, and promotion to loot or report.
    """

    note_added = pyqtSignal(dict)
    notes_updated = pyqtSignal()
    selection_count_changed = pyqtSignal(int)
    selection_cleared = pyqtSignal()

    def __init__(
        self,
        quick_note_manager: QuickNoteManager,
        loot_controller: Optional[Any] = None,
        report_controller: Optional[Any] = None,
        target_provider: Optional[Callable[[], str]] = None,
        event_bus: Optional[EventBus] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.quick_note_manager = quick_note_manager
        self.loot_controller = loot_controller
        self.report_controller = report_controller
        self.target_provider = target_provider
        self.event_bus = event_bus if event_bus is not None else EventBus()
        self.last_category: str = "misc"
        self.current_category_filter: str = "all"
        self.current_status_filter: str = "all"
        self.selection_model = NoteSelectionModel()
        self.filter_buttons: Dict[str, QPushButton] = {}
        self.btn_phase: Optional[QPushButton] = None
        self._popup: Optional[QuickNotePopup] = None

        if self.event_bus:
            self.event_bus.subscribe(EventType.QUICK_NOTES_UPDATED, self._on_notes_updated)

    @property
    def selected_note_ids(self) -> Set[str]:
        """Compatibility snapshot of the selection model's current IDs."""
        return self.selection_model.snapshot()

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
        self,
        text: str,
        category: str = "misc",
        target_ip: Optional[str] = None,
        status: str = "inbox",
        pinned: bool = False,
        source: Optional[Dict[str, str]] = None,
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
                text=text,
                category=clean_cat,
                target_ip=resolved_target or "",
                status=status,
                pinned=pinned,
                source=source,
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

    def update_note_text(self, entry_id: str, new_text: str) -> bool:
        """Updates the text content of an existing note."""
        try:
            res = self.quick_note_manager.update_entry(entry_id, text=new_text)
            return res is not None
        except Exception as e:
            logger.error(f"Failed to update text for note {entry_id}: {e}")
            return False

    def open_edit_dialog(
        self, parent_widget: Optional[QWidget], entry: Dict[str, Any]
    ) -> bool:
        """Opens modal dialog to edit a quick note."""
        from ui.note_edit_dialog import EditNoteDialog

        dlg = EditNoteDialog(entry, parent=parent_widget)
        if dlg.exec():
            data = dlg.get_data()
            try:
                res = self.quick_note_manager.update_entry(
                    entry.get("id", ""),
                    text=data["text"],
                    category=data.get("category", "misc"),
                    target_ip=data.get("target_ip", ""),
                    status=data.get("status", "inbox"),
                )
                if res is not None:
                    self.notes_updated.emit()
                    return True
            except Exception as e:
                logger.error(f"Failed to save edited note: {e}")
        return False

    def set_note_status(self, entry_id: str, status: str) -> bool:
        """Sets the triage status (inbox, followup, resolved) of a note."""
        try:
            res = self.quick_note_manager.update_entry(entry_id, status=status)
            return res is not None
        except Exception as e:
            logger.error(f"Failed to set status for note {entry_id}: {e}")
            return False

    def toggle_note_pinned(self, entry_id: str, pinned: bool) -> bool:
        """Toggles the pinned state of a note."""
        try:
            res = self.quick_note_manager.update_entry(entry_id, pinned=pinned)
            return res is not None
        except Exception as e:
            logger.error(f"Failed to toggle pin for note {entry_id}: {e}")
            return False

    def delete_note(self, entry_id: str) -> bool:
        """Deletes a quick note."""
        try:
            self.selection_model.discard(entry_id)
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

    def send_to_report(
        self, entry: Dict[str, Any], parent_widget: Optional[QWidget] = None
    ) -> bool:
        """Appends a quick note to the active project report and marks it as resolved."""
        if not self.report_controller:
            logger.warning("No report_controller configured for send_to_report.")
            return False

        try:
            success = self.report_controller.append_note(entry)
            if success:
                entry_id = entry.get("id")
                if entry_id:
                    self.set_note_status(entry_id, "resolved")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to send note to report: {e}")
            return False

    # ------------------------------------------------------------------ #
    # Bulk Triage & Selection
    # ------------------------------------------------------------------ #

    def on_card_selection_changed(self, entry_id: str, is_selected: bool) -> None:
        """Tracks selection state for bulk triage operations."""
        self.selection_model.set_selected(entry_id, is_selected)
        self._update_bulk_bar()

    def _update_bulk_bar(self) -> None:
        self.selection_count_changed.emit(len(self.selection_model))

    def clear_selection(self) -> None:
        """Clears all selected notes."""
        if self.selection_model.clear():
            self.selection_cleared.emit()
        self._update_bulk_bar()

    def bulk_set_status(self, status: str) -> None:
        """Applies a triage status to all currently selected notes."""
        if not self.selection_model:
            return
        for entry_id in self.selection_model.snapshot():
            try:
                self.quick_note_manager.update_entry(entry_id, status=status)
            except Exception as e:
                logger.error(f"Failed to bulk update note {entry_id}: {e}")
        self.clear_selection()
        self.notes_updated.emit()

    def bulk_delete_notes(self, parent_widget: Optional[QWidget] = None) -> bool:
        """Deletes all currently selected notes after user confirmation."""
        if not self.selection_model:
            return False

        if parent_widget:
            count = len(self.selection_model)
            confirm_msg = t(
                "quick_note.bulk_delete_confirm",
                f"Are you sure you want to delete {count} selected quick note(s)?",
            ).replace("{count}", str(count))
            reply = QMessageBox.question(
                parent_widget,
                t("quick_note.bulk_delete_title", "Delete Notes"),
                confirm_msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        for entry_id in self.selection_model.snapshot():
            try:
                self.quick_note_manager.delete_entry(entry_id)
            except Exception as e:
                logger.error(f"Failed to bulk delete note {entry_id}: {e}")
        self.clear_selection()
        self.notes_updated.emit()
        return True

    # ------------------------------------------------------------------ #
    # Filter & Search
    # ------------------------------------------------------------------ #

    def select_filter(self, filter_id: str) -> None:
        """Selects active status or category filter and updates pill styles."""
        if filter_id in ("all", "inbox", "followup", "resolved", "pinned"):
            self.current_status_filter = filter_id
            if filter_id == "all":
                self.current_category_filter = "all"
        elif filter_id.startswith("cat:"):
            self.current_category_filter = filter_id[4:]
        elif filter_id in VALID_CATEGORY_IDS:
            self.current_category_filter = filter_id

        for fid, btn in self.filter_buttons.items():
            is_active = (
                (fid == self.current_status_filter)
                if fid in ("all", "inbox", "followup", "resolved", "pinned")
                else (fid == self.current_category_filter)
            )
            btn.setProperty("class", "FilterPillActive" if is_active else "FilterPill")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if self.btn_phase:
            cat_display = (
                self.current_category_filter.capitalize()
                if self.current_category_filter != "all"
                else t("quick_note.all_phases", "All Phases")
            )
            self.btn_phase.setText(f"{cat_display} ▾")
            is_cat_active = self.current_category_filter != "all"
            self.btn_phase.setProperty(
                "class", "FilterPillActive" if is_cat_active else "FilterPill"
            )
            self.btn_phase.style().unpolish(self.btn_phase)
            self.btn_phase.style().polish(self.btn_phase)

    def build_filter_pills(
        self,
        pills_layout: QHBoxLayout,
        on_select_filter: Callable[[str], None],
        on_clear: Callable[[], None],
    ) -> None:
        """Builds status triage pills, phase filter dropdown, and Clear action button."""
        self.filter_buttons.clear()
        all_notes = self.quick_note_manager.get_all_entries()

        total = len(all_notes)
        inbox_cnt = sum(1 for n in all_notes if n.get("status", "inbox") == "inbox")
        follow_cnt = sum(1 for n in all_notes if n.get("status") == "followup")
        resolved_cnt = sum(1 for n in all_notes if n.get("status") == "resolved")
        pinned_cnt = sum(1 for n in all_notes if bool(n.get("pinned", False)))

        # 1. Status Pills
        status_pills = [
            ("all", f"All ({total})"),
            ("inbox", f"Inbox ({inbox_cnt})"),
            ("followup", f"Follow-up ({follow_cnt})"),
            ("resolved", f"Resolved ({resolved_cnt})"),
            ("pinned", f"📌 Pinned ({pinned_cnt})"),
        ]

        for pid, ptext in status_pills:
            btn = QPushButton(ptext)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty(
                "class",
                "FilterPillActive" if self.current_status_filter == pid else "FilterPill",
            )
            btn.clicked.connect(lambda checked=False, fid=pid: on_select_filter(fid))
            self.filter_buttons[pid] = btn
            pills_layout.addWidget(btn)

        # 2. Phase Category Dropdown Menu
        cat_display = (
            self.current_category_filter.capitalize()
            if self.current_category_filter != "all"
            else t("quick_note.all_phases", "All Phases")
        )
        self.btn_phase = QPushButton(f"{cat_display} ▾")
        self.btn_phase.setCursor(Qt.CursorShape.PointingHandCursor)
        is_cat_active = self.current_category_filter != "all"
        self.btn_phase.setProperty(
            "class", "FilterPillActive" if is_cat_active else "FilterPill"
        )
        self.btn_phase.setToolTip(t("quick_note.phase_filter_tip", "Filter by pentest phase"))

        phase_menu = QMenu(self.btn_phase)
        act_all = QAction(t("quick_note.all_phases", "All Phases"), phase_menu)
        act_all.triggered.connect(lambda: on_select_filter("cat:all"))
        phase_menu.addAction(act_all)

        for cat in ["recon", "access", "privesc", "postex", "scripts", "misc"]:
            count = sum(1 for n in all_notes if n.get("category") == cat)
            act = QAction(f"{cat.capitalize()} ({count})", phase_menu)
            act.triggered.connect(lambda checked=False, c=cat: on_select_filter(f"cat:{c}"))
            phase_menu.addAction(act)
            # Retain programmatic reference in filter_buttons for category testing/compat
            dummy_btn = QPushButton(f"{cat.capitalize()} ({count})")
            dummy_btn.setVisible(False)
            self.filter_buttons[cat] = dummy_btn

        self.btn_phase.setMenu(phase_menu)
        pills_layout.addWidget(self.btn_phase)

        pills_layout.addStretch()

        # 3. Clear All Button
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

    def _create_bulk_bar(self, parent_widget: Optional[QWidget]) -> QFrame:
        """Creates the horizontal bulk triage action bar."""
        bulk_bar = QuickNoteBulkBar(parent_widget)
        bulk_bar.status_requested.connect(self.bulk_set_status)
        bulk_bar.delete_requested.connect(
            lambda: self.bulk_delete_notes(parent_widget)
        )
        bulk_bar.deselect_requested.connect(self.clear_selection)
        self.selection_count_changed.connect(bulk_bar.set_selected_count)
        bulk_bar.set_selected_count(len(self.selection_model))
        return bulk_bar

    def render_content(
        self,
        content_layout: QVBoxLayout,
        search_query: str,
        on_copied: Optional[Callable[[str], None]],
        parent_widget: QWidget,
        show_empty_state_fn: Callable[[str], None],
        on_edit_note: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[QWidget]:
        """Renders notes inbox cards into the content layout."""
        cat_filter = (
            None if self.current_category_filter in ("all", "") else self.current_category_filter
        )
        pinned_filter: Optional[bool] = None
        status_filter: Optional[str] = None

        if self.current_status_filter == "pinned":
            pinned_filter = True
        elif self.current_status_filter != "all":
            status_filter = self.current_status_filter

        notes = self.quick_note_manager.get_entries(
            category=cat_filter,
            status=status_filter,
            pinned=pinned_filter,
            search_query=search_query,
        )

        # Retain selection of only still existing items
        existing_ids = {n.get("id") for n in self.quick_note_manager.get_all_entries()}
        self.selection_model.retain(existing_ids)

        # Create and attach bulk bar
        bulk_bar = self._create_bulk_bar(parent_widget)
        self._update_bulk_bar()
        content_layout.addWidget(bulk_bar)

        if not notes:
            show_empty_state_fn(
                t(
                    "quick_note.empty_state",
                    "No quick notes found. Use global hotkey (Ctrl+Alt+N) or click '📌 Note' to capture thoughts.",
                )
            )
            return []

        rendered_cards: List[QWidget] = []
        for item in notes:
            card = QuickNoteCard(item, parent=parent_widget)
            card.promote_requested.connect(
                lambda entry, p=parent_widget: self.promote_to_loot(entry, parent_widget=p)
            )
            card.send_to_report_requested.connect(
                lambda entry, p=parent_widget: self.send_to_report(entry, parent_widget=p)
            )
            card.deleted.connect(self.delete_note)
            card.edited.connect(self.update_note_text)
            if on_edit_note is not None:
                card.edit_requested.connect(on_edit_note)
            else:
                card.edit_requested.connect(
                    lambda entry, p=parent_widget: self.open_edit_dialog(p, entry)
                )
            card.status_changed.connect(self.set_note_status)
            card.pin_toggled.connect(self.toggle_note_pinned)
            card.selection_changed.connect(self.on_card_selection_changed)

            self.selection_cleared.connect(card.clear_selection)

            if item.get("id") in self.selection_model:
                card.set_selected(True)

            if on_copied is not None:
                card.copied.connect(on_copied)

            content_layout.addWidget(card)
            rendered_cards.append(card)
        return rendered_cards

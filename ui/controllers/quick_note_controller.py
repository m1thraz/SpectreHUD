"""
Quick Note Controller for SpectreHUD.

Coordinates the QuickNotePopup, quick note persistence, promotion to loot,
reporting export, inline editing, status triage, pinning, and bulk actions.
"""

from datetime import datetime
from typing import Optional, Callable, Dict, Any, List, Set
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QSize
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
from ui.quick_note_focus_review import QuickNoteFocusReview, QuickNoteReviewSummary
from ui.note_selection_model import NoteSelectionModel
from ui.styles.icons import icon

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
        phase_provider: Optional[Callable[[], Optional[str]]] = None,
        event_bus: Optional[EventBus] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.quick_note_manager = quick_note_manager
        self.loot_controller = loot_controller
        self.report_controller = report_controller
        self.target_provider = target_provider
        self._phase_provider = phase_provider
        self.event_bus = event_bus if event_bus is not None else EventBus()
        self.last_category: str = "misc"
        self.current_category_filter: str = "all"
        self.current_status_filter: str = "all"
        self.selection_model = NoteSelectionModel()
        self.filter_buttons: Dict[str, QPushButton] = {}
        self.btn_phase: Optional[QPushButton] = None
        self.btn_select_mode: Optional[QPushButton] = None
        self.btn_review_mode: Optional[QPushButton] = None
        self.selection_mode = False
        self.review_mode = False
        self._pending_completions: Dict[str, str] = {}
        self._suppressed_event_ids: Set[str] = set()
        self._review_queue_ids: List[str] = []
        self._review_seen_count = 0
        self._review_completed_count = 0
        self._review_total = 0
        self._popup: Optional[QuickNotePopup] = None

        if self.event_bus:
            self.event_bus.subscribe(EventType.QUICK_NOTES_UPDATED, self._on_notes_updated)

    @property
    def selected_note_ids(self) -> Set[str]:
        """Compatibility snapshot of the selection model's current IDs."""
        return self.selection_model.snapshot()

    def _on_notes_updated(self, payload: Optional[Dict[str, Any]] = None) -> None:
        entry = (payload or {}).get("entry") or {}
        entry_id = entry.get("id")
        if entry_id in self._pending_completions or entry_id in self._suppressed_event_ids:
            return
        self.notes_updated.emit()

    def set_phase_provider(self, provider: Callable[[], Optional[str]]) -> None:
        """Sets the callback returning the globally active pentest phase key."""
        self._phase_provider = provider

    def get_popup(self) -> QuickNotePopup:
        """Returns the lazily instantiated QuickNotePopup instance."""
        if self._popup is None:
            self._popup = QuickNotePopup(default_category=self.last_category)
            self._popup.note_submitted.connect(self.submit_note)
        return self._popup

    def show_popup(self) -> None:
        """Opens the QuickNote popup at current cursor position."""
        category = self.last_category
        if self._phase_provider:
            try:
                active_phase = self._phase_provider()
                if active_phase and active_phase in VALID_CATEGORY_IDS:
                    category = active_phase
            except Exception as e:
                logger.debug(f"Failed to query active phase from provider: {e}")
        popup = self.get_popup()
        popup.show_at_cursor(default_category=category)

    @property
    def current_category(self) -> str:
        return self.last_category

    @current_category.setter
    def current_category(self, cat: str) -> None:
        self.last_category = cat if cat in VALID_CATEGORY_IDS else "misc"

    def add_entry(
        self,
        text: str,
        category: Optional[str] = None,
        target_ip: Optional[str] = None,
        status: str = "inbox",
        pinned: bool = False,
        source: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Directly adds a quick note entry."""
        if category is None:
            active_phase = self._phase_provider() if self._phase_provider else None
            chosen_cat = (
                active_phase
                if active_phase and active_phase in VALID_CATEGORY_IDS
                else self.last_category
            )
        else:
            chosen_cat = category

        clean_cat = chosen_cat if chosen_cat in VALID_CATEGORY_IDS else "misc"
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

    def set_selection_mode(self, enabled: bool) -> None:
        self.selection_mode = bool(enabled)
        if self.selection_mode:
            self.set_review_mode(False, refresh=False)
        else:
            self.clear_selection()
        self.notes_updated.emit()

    def set_review_mode(self, enabled: bool, *, refresh: bool = True) -> None:
        self.review_mode = bool(enabled)
        if self.review_mode:
            self.selection_mode = False
            self.clear_selection()
            self._review_queue_ids = []
            self._review_seen_count = 0
            self._review_completed_count = 0
            self._review_total = 0
        if refresh:
            self.notes_updated.emit()

    def begin_completion(self, entry_id: str, card: QuickNoteCard) -> bool:
        entry = next(
            (note for note in self.quick_note_manager.get_all_entries() if note.get("id") == entry_id),
            None,
        )
        if entry is None or entry.get("status", "inbox") == "resolved":
            return False
        self._pending_completions[entry_id] = entry.get("status", "inbox")
        if not self.set_note_status(entry_id, "resolved"):
            self._pending_completions.pop(entry_id, None)
            return False
        card.show_completion_pending()
        return True

    def undo_completion(self, entry_id: str) -> bool:
        previous_status = self._pending_completions.pop(entry_id, None)
        if previous_status is None:
            return False
        return self.set_note_status(entry_id, previous_status)

    def finalize_completion(self, entry_id: str) -> None:
        if self._pending_completions.pop(entry_id, None) is not None:
            self.notes_updated.emit()

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

        if self.review_mode:
            self._review_queue_ids = []
            self._review_seen_count = 0
            self._review_completed_count = 0
            self._review_total = 0

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

        open_cnt = sum(1 for n in all_notes if n.get("status", "inbox") != "resolved")
        inbox_cnt = sum(1 for n in all_notes if n.get("status", "inbox") == "inbox")
        follow_cnt = sum(1 for n in all_notes if n.get("status") == "followup")
        resolved_cnt = sum(1 for n in all_notes if n.get("status") == "resolved")
        pinned_cnt = sum(1 for n in all_notes if bool(n.get("pinned", False)))

        # 1. Status Pills
        status_pills = [
            ("all", f"{t('quick_note.filter_all', 'Open')} ({open_cnt})", None),
            ("inbox", f"{t('quick_note.status_inbox', 'Inbox')} ({inbox_cnt})", None),
            (
                "followup",
                f"{t('quick_note.status_followup', 'Follow-up')} ({follow_cnt})",
                None,
            ),
            (
                "resolved",
                f"{t('quick_note.status_resolved', 'Resolved')} ({resolved_cnt})",
                None,
            ),
            ("pinned", f"{t('quick_note.pinned', 'Pinned')} ({pinned_cnt})", "fa5s.thumbtack"),
        ]

        for pid, ptext, icon_name in status_pills:
            btn = QPushButton(ptext)
            if icon_name:
                btn.setIcon(icon(icon_name))
                btn.setIconSize(QSize(11, 11))
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

        self.btn_select_mode = QPushButton(t("quick_note.select_mode", "Select"))
        self.btn_select_mode.setIcon(icon("fa5s.check-square"))
        self.btn_select_mode.setIconSize(QSize(11, 11))
        self.btn_select_mode.setCheckable(True)
        self.btn_select_mode.setChecked(self.selection_mode)
        self.btn_select_mode.setProperty(
            "class", "FilterPillActive" if self.selection_mode else "FilterPill"
        )
        self.btn_select_mode.clicked.connect(self.set_selection_mode)
        pills_layout.addWidget(self.btn_select_mode)

        self.btn_review_mode = QPushButton(t("quick_note.review_mode", "Focus review"))
        self.btn_review_mode.setIcon(icon("fa5s.tasks"))
        self.btn_review_mode.setIconSize(QSize(11, 11))
        self.btn_review_mode.setCheckable(True)
        self.btn_review_mode.setChecked(self.review_mode)
        self.btn_review_mode.setProperty(
            "class", "FilterPillActive" if self.review_mode else "FilterPill"
        )
        self.btn_review_mode.clicked.connect(self.set_review_mode)
        pills_layout.addWidget(self.btn_review_mode)

        pills_layout.addStretch()

        # 3. Clear All Button
        btn_clear = QPushButton(t("quick_note.clear", "Clear"))
        btn_clear.setIcon(icon("fa5s.trash"))
        btn_clear.setIconSize(QSize(11, 11))
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
        """Render the selected Notes presentation without changing domain state."""
        notes = self._filtered_notes(search_query)

        existing_ids = {n.get("id") for n in self.quick_note_manager.get_all_entries()}
        self.selection_model.retain(existing_ids)

        if self.review_mode:
            return self._render_focus_review(content_layout, notes, parent_widget)

        if self._review_completed_count:
            content_layout.addWidget(
                QuickNoteReviewSummary(self._review_completed_count, parent=parent_widget)
            )

        if self.selection_mode:
            bulk_bar = self._create_bulk_bar(parent_widget)
            self._update_bulk_bar()
            content_layout.addWidget(bulk_bar)

        if not notes:
            show_empty_state_fn(
                t(
                    "quick_note.empty_state",
                    "No quick notes found. Use Ctrl+Alt+N or the Note button to capture thoughts.",
                )
            )
            return []

        rendered_cards: List[QWidget] = []
        render_now = datetime.now()
        for item in notes:
            card = QuickNoteCard(item, parent=parent_widget, now=render_now)
            self._wire_card(card, parent_widget, on_copied, on_edit_note)
            card.set_selection_mode(self.selection_mode)
            if item.get("id") in self.selection_model:
                card.set_selected(True)
            content_layout.addWidget(card)
            rendered_cards.append(card)
        return rendered_cards

    def _filtered_notes(self, search_query: str) -> List[Dict[str, Any]]:
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
        if self.current_status_filter == "all":
            notes = [n for n in notes if n.get("status", "inbox") != "resolved"]
        return notes

    def _wire_card(
        self,
        card: QuickNoteCard,
        parent_widget: QWidget,
        on_copied: Optional[Callable[[str], None]],
        on_edit_note: Optional[Callable[[Dict[str, Any]], None]],
    ) -> None:
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
        card.status_changed.connect(self.set_note_status)
        card.pin_toggled.connect(self.toggle_note_pinned)
        card.selection_changed.connect(self.on_card_selection_changed)
        card.completion_requested.connect(
            lambda entry_id, rendered=card: self.begin_completion(entry_id, rendered)
        )
        card.completion_undo_requested.connect(self.undo_completion)
        card.completion_expired.connect(self.finalize_completion)
        self.selection_cleared.connect(card.clear_selection)
        if on_copied is not None:
            card.copied.connect(on_copied)

    def _render_focus_review(
        self,
        content_layout: QVBoxLayout,
        notes: List[Dict[str, Any]],
        parent_widget: QWidget,
    ) -> List[QWidget]:
        eligible = [n for n in reversed(notes) if n.get("status", "inbox") != "resolved"]
        entries_by_id = {n.get("id"): n for n in eligible}
        if not self._review_queue_ids and self._review_total == 0:
            self._review_queue_ids = [n.get("id") for n in eligible if n.get("id")]
            self._review_total = len(self._review_queue_ids)
        else:
            self._review_queue_ids = [
                entry_id for entry_id in self._review_queue_ids if entry_id in entries_by_id
            ]

        if not self._review_queue_ids:
            summary = QuickNoteReviewSummary(self._review_completed_count, parent=parent_widget)
            content_layout.addWidget(summary)
            return []

        entry = entries_by_id[self._review_queue_ids[0]]
        review = QuickNoteFocusReview(
            entry,
            position=min(self._review_seen_count + 1, self._review_total),
            total=self._review_total,
            parent=parent_widget,
        )
        review.promote_requested.connect(
            lambda note, p=parent_widget: self._review_promote(note, p)
        )
        review.edit_requested.connect(
            lambda note, p=parent_widget: self.open_edit_dialog(p, note)
        )
        review.text_save_requested.connect(self.update_note_text)
        review.complete_requested.connect(self._review_complete)
        review.delete_requested.connect(self._review_delete)
        review.next_requested.connect(self._review_next)
        content_layout.addWidget(review)
        return [review]

    def _advance_review(self, entry_id: str, *, completed: bool) -> None:
        if entry_id in self._review_queue_ids:
            self._review_queue_ids.remove(entry_id)
        self._review_seen_count += 1
        if completed:
            self._review_completed_count += 1
        self.notes_updated.emit()

    def _review_complete(self, entry_id: str) -> None:
        self._suppressed_event_ids.add(entry_id)
        try:
            success = self.set_note_status(entry_id, "resolved")
        finally:
            self._suppressed_event_ids.discard(entry_id)
        if success:
            self._advance_review(entry_id, completed=True)

    def _review_delete(self, entry_id: str) -> None:
        self._suppressed_event_ids.add(entry_id)
        try:
            success = self.delete_note(entry_id)
        finally:
            self._suppressed_event_ids.discard(entry_id)
        if success:
            self._advance_review(entry_id, completed=True)

    def _review_promote(self, entry: Dict[str, Any], parent_widget: QWidget) -> None:
        entry_id = entry.get("id", "")
        self._suppressed_event_ids.add(entry_id)
        try:
            success = self.promote_to_loot(entry, parent_widget=parent_widget)
        finally:
            self._suppressed_event_ids.discard(entry_id)
        if success:
            self._advance_review(entry_id, completed=True)

    def _review_next(self) -> None:
        if not self._review_queue_ids:
            return
        self._review_queue_ids.pop(0)
        self._review_seen_count += 1
        self.notes_updated.emit()

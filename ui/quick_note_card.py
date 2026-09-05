"""
Visual card displaying a single Quick Note in the Inbox / History panel.
Supports inline editing, status triage (inbox/followup/resolved), pinning,
Markdown-light rendering, multi-selection, and promotion/export to Loot or Report.
"""

from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QCheckBox,
    QMenu,
    QWidget,
    QApplication,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt, QSize, QEvent
from PyQt6.QtGui import QKeyEvent, QAction, QMouseEvent
import pyperclip

from core.logger import get_logger
from core.i18n import t
from core.phases import get_phase
from ui.styles.icons import icon
from ui.styles.palette import CYBER_CYAN, STATUS_ERROR, STATUS_SUCCESS
from ui.elided_label import configure_badge_label

logger = get_logger("quick_note_card")

CARD_ICON_SIZE = QSize(13, 13)

STATUS_ICONS = {
    "inbox": "fa5s.inbox",
    "followup": "fa5s.clock",
    "resolved": "fa5s.check-circle",
}


class NoteEditor(QPlainTextEdit):
    """Inline plain text editor with Ctrl+Enter save and Esc cancel shortcuts."""

    save_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.save_requested.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class QuickNoteCard(QFrame):
    """
    Card displaying a quick thought note with inline editing, status triage,
    pinning, multi-selection, and send-to actions (Loot or Report).
    """

    copied = pyqtSignal(str)
    edit_requested = pyqtSignal(dict)
    promote_requested = pyqtSignal(dict)
    send_to_report_requested = pyqtSignal(dict)
    deleted = pyqtSignal(str)
    edited = pyqtSignal(str, str)  # (note_id, new_text)
    status_changed = pyqtSignal(str, str)  # (note_id, new_status)
    pin_toggled = pyqtSignal(str, bool)  # (note_id, new_pinned)
    selection_changed = pyqtSignal(str, bool)  # (note_id, is_selected)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("SnippetCard")
        self.entry = dict(entry)
        self.is_editing = False
        self._init_ui()
        self._update_status_style()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # ------------------------------------------------------------------ #
        # Header Row: Checkbox, Pin, Status Pill, Category, Time, Target, Delete
        # ------------------------------------------------------------------ #
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        # 1. Selection Checkbox for Bulk Triage
        self.chk_select = QCheckBox()
        self.chk_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_select.setToolTip(t("quick_note.select_tip", "Select for bulk action"))
        self.chk_select.toggled.connect(
            lambda checked: self.selection_changed.emit(self.entry.get("id", ""), checked)
        )
        header_layout.addWidget(self.chk_select)

        # 2. Pin Button
        is_pinned = bool(self.entry.get("pinned", False))
        self.btn_pin = QPushButton()
        self.btn_pin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pin.setIcon(icon("fa5s.thumbtack", color=CYBER_CYAN if is_pinned else "#8b949e"))
        self.btn_pin.setIconSize(QSize(11, 11))
        self.btn_pin.setFixedSize(22, 20)
        self._style_pin_button(is_pinned)
        self.btn_pin.setToolTip(
            t("quick_note.unpin_tip", "Unpin note")
            if is_pinned
            else t("quick_note.pin_tip", "Pin note to top")
        )
        self.btn_pin.clicked.connect(self._toggle_pin)
        header_layout.addWidget(self.btn_pin)

        # 3. Status Pill Button (Inbox, Follow-up, Resolved)
        self.btn_status = QPushButton()
        self.btn_status.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build_status_menu()
        header_layout.addWidget(self.btn_status)

        # 4. Phase Category Badge
        phase = get_phase(self.entry.get("category", "misc"))
        lbl_cat = QLabel(phase.short)
        lbl_cat.setTextFormat(Qt.TextFormat.PlainText)
        lbl_cat.setToolTip(phase.long)
        lbl_cat.setStyleSheet(
            "background-color: rgba(110, 118, 129, 0.2); color: #c9d1d9; "
            "border: 1px solid rgba(110, 118, 129, 0.4); border-radius: 4px; "
            "padding: 2px 6px; font-size: 10px; font-weight: bold;"
        )
        configure_badge_label(lbl_cat, phase.short, padding=14)
        header_layout.addWidget(lbl_cat)

        # 5. Time Badge
        ts = str(self.entry.get("timestamp", ""))
        time_display = ts.split(" ")[-1] if " " in ts else ts
        if time_display:
            lbl_time = QLabel(time_display)
            lbl_time.setTextFormat(Qt.TextFormat.PlainText)
            lbl_time.setStyleSheet(
                "background-color: rgba(56, 139, 253, 0.15); color: #79c0ff; "
                "border: 1px solid rgba(56, 139, 253, 0.3); border-radius: 4px; "
                "padding: 2px 6px; font-size: 10px; font-weight: bold;"
            )
            configure_badge_label(lbl_time, time_display, padding=14)
            header_layout.addWidget(lbl_time)

        # 6. Target IP Badge (if present)
        target_ip = str(self.entry.get("target_ip", "")).strip()
        if target_ip:
            lbl_target = QLabel(target_ip)
            lbl_target.setTextFormat(Qt.TextFormat.PlainText)
            lbl_target.setStyleSheet(
                "background-color: rgba(0, 229, 255, 0.12); color: #00e5ff; "
                "border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 4px; "
                "padding: 2px 6px; font-size: 10px; font-weight: bold;"
            )
            configure_badge_label(lbl_target, target_ip, padding=14)
            header_layout.addWidget(lbl_target)

        header_layout.addStretch()

        # 7. Delete Button
        self.btn_delete = QPushButton()
        self.btn_delete.setIcon(icon("fa5s.trash", color=STATUS_ERROR))
        self.btn_delete.setIconSize(CARD_ICON_SIZE)
        self.btn_delete.setProperty("class", "CardDangerIconBtn")
        self.btn_delete.setToolTip(t("quick_note.delete_tip", "Delete this quick note"))
        self.btn_delete.clicked.connect(lambda: self.deleted.emit(self.entry.get("id", "")))
        header_layout.addWidget(self.btn_delete)

        layout.addLayout(header_layout)

        # ------------------------------------------------------------------ #
        # Content Row: Markdown-Light Content / Inline Editor + Action Buttons
        # ------------------------------------------------------------------ #
        self.content_row = QHBoxLayout()
        self.content_row.setSpacing(8)

        # Content View Mode (Markdown-Light)
        self.lbl_content = QLabel(self.entry.get("text", ""))
        self.lbl_content.setTextFormat(Qt.TextFormat.MarkdownText)
        self.lbl_content.setObjectName("CommandLabel")
        self.lbl_content.setWordWrap(True)
        self.lbl_content.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.lbl_content.installEventFilter(self)
        self.lbl_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.content_row.addWidget(self.lbl_content, stretch=1)

        # Content Edit Mode Container (initially hidden)
        self.edit_container = QWidget()
        edit_layout = QVBoxLayout(self.edit_container)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(4)

        self.editor = NoteEditor()
        self.editor.setPlainText(self.entry.get("text", ""))
        self.editor.setMaximumHeight(120)
        self.editor.setStyleSheet(
            "QPlainTextEdit { background-color: rgba(22, 27, 34, 0.95); color: #f0f6fc; "
            "border: 1px solid #00e5ff; border-radius: 4px; padding: 4px; font-size: 12px; }"
        )
        self.editor.save_requested.connect(self._save_edit)
        self.editor.cancel_requested.connect(self._cancel_edit)
        edit_layout.addWidget(self.editor)

        edit_btns = QHBoxLayout()
        edit_btns.setSpacing(6)
        lbl_hint = QLabel(t("quick_note.edit_shortcut_hint", "Ctrl+Enter: Save | Esc: Cancel"))
        lbl_hint.setStyleSheet("color: #8b949e; font-size: 10px;")
        edit_btns.addWidget(lbl_hint)
        edit_btns.addStretch()

        btn_save_edit = QPushButton(t("quick_note.save", "Save"))
        btn_save_edit.setProperty("class", "PrimaryBtn")
        btn_save_edit.setFixedSize(55, 22)
        btn_save_edit.clicked.connect(self._save_edit)
        edit_btns.addWidget(btn_save_edit)

        btn_cancel_edit = QPushButton(t("quick_note.cancel", "Cancel"))
        btn_cancel_edit.setProperty("class", "SecondaryBtn")
        btn_cancel_edit.setFixedSize(55, 22)
        btn_cancel_edit.clicked.connect(self._cancel_edit)
        edit_btns.addWidget(btn_cancel_edit)

        edit_layout.addLayout(edit_btns)
        self.edit_container.setVisible(False)
        self.content_row.addWidget(self.edit_container, stretch=1)

        # ------------------------------------------------------------------ #
        # Action Buttons Column: Copy, Edit, Send to...
        # ------------------------------------------------------------------ #
        self.action_col = QVBoxLayout()
        self.action_col.setSpacing(4)

        self.btn_copy = QPushButton()
        self.btn_copy.setIcon(icon("fa5s.copy"))
        self.btn_copy.setIconSize(CARD_ICON_SIZE)
        self.btn_copy.setProperty("class", "CardIconBtn")
        self.btn_copy.setToolTip(t("quick_note.copy_tip", "Copy quick note"))
        self.btn_copy.clicked.connect(self._copy_content)
        self.action_col.addWidget(self.btn_copy)

        self.btn_edit = QPushButton()
        self.btn_edit.setProperty("class", "CardIconBtn")
        self.btn_edit.setIcon(icon("fa5s.pen", color="#79c0ff"))
        self.btn_edit.setIconSize(CARD_ICON_SIZE)
        self.btn_edit.setToolTip(t("quick_note.edit", "Edit"))
        self.btn_edit.clicked.connect(self._trigger_edit)
        self.action_col.addWidget(self.btn_edit)

        # Send to Dropdown Menu (Loot or Report)
        self.btn_send = QPushButton(t("quick_note.send_to", "Send to ▾"))
        self.btn_send.setIcon(icon("fa5s.share", color="#e3b341"))
        self.btn_send.setIconSize(CARD_ICON_SIZE)
        self.btn_send.setProperty("class", "SecondaryBtn")
        self.btn_send.setStyleSheet(
            "QPushButton { border-color: rgba(210, 153, 34, 0.6); color: #e3b341; } "
            "QPushButton:hover { background-color: rgba(210, 153, 34, 0.2); border-color: #e3b341; }"
        )
        self.btn_send.setMinimumWidth(85)
        self._build_send_menu()
        self.action_col.addWidget(self.btn_send)

        self.content_row.addLayout(self.action_col)
        layout.addLayout(self.content_row)

    # ------------------------------------------------------------------ #
    # Status & Pin Helpers
    # ------------------------------------------------------------------ #

    def _build_status_menu(self) -> None:
        status_menu = QMenu(self.btn_status)
        for s_code, s_label in [
            ("inbox", t("quick_note.status_inbox", "Inbox")),
            ("followup", t("quick_note.status_followup", "Follow-up")),
            ("resolved", t("quick_note.status_resolved", "Resolved")),
        ]:
            action = QAction(icon(STATUS_ICONS[s_code]), s_label, status_menu)
            action.triggered.connect(lambda checked=False, st=s_code: self._change_status(st))
            status_menu.addAction(action)
        self.btn_status.setMenu(status_menu)

    def _change_status(self, new_status: str) -> None:
        self.entry["status"] = new_status
        self._update_status_style()
        self.status_changed.emit(self.entry.get("id", ""), new_status)

    def _update_status_style(self) -> None:
        st = str(self.entry.get("status", "inbox")).lower()
        self.btn_status.setIcon(icon(STATUS_ICONS.get(st, STATUS_ICONS["inbox"])))
        self.btn_status.setIconSize(QSize(11, 11))
        if st == "followup":
            self.btn_status.setText(t("quick_note.status_followup_short", "Follow-up ▾"))
            self.btn_status.setStyleSheet(
                "background-color: rgba(210, 153, 34, 0.2); color: #e3b341; "
                "border: 1px solid rgba(210, 153, 34, 0.5); border-radius: 4px; "
                "padding: 2px 6px; font-size: 10px; font-weight: bold;"
            )
            self.lbl_content.setStyleSheet("")
        elif st == "resolved":
            self.btn_status.setText(t("quick_note.status_resolved_short", "Resolved ▾"))
            self.btn_status.setStyleSheet(
                "background-color: rgba(57, 211, 83, 0.15); color: #56d364; "
                "border: 1px solid rgba(57, 211, 83, 0.4); border-radius: 4px; "
                "padding: 2px 6px; font-size: 10px; font-weight: bold;"
            )
            # Subtle dimming of text for resolved notes
            self.lbl_content.setStyleSheet("color: #8b949e;")
        else:
            self.btn_status.setText(t("quick_note.status_inbox_short", "Inbox ▾"))
            self.btn_status.setStyleSheet(
                "background-color: rgba(56, 139, 253, 0.15); color: #79c0ff; "
                "border: 1px solid rgba(56, 139, 253, 0.4); border-radius: 4px; "
                "padding: 2px 6px; font-size: 10px; font-weight: bold;"
            )
            self.lbl_content.setStyleSheet("")

    def _toggle_pin(self) -> None:
        current_pin = bool(self.entry.get("pinned", False))
        new_pin = not current_pin
        self.entry["pinned"] = new_pin
        self._style_pin_button(new_pin)
        self.btn_pin.setIcon(icon("fa5s.thumbtack", color=CYBER_CYAN if new_pin else "#8b949e"))
        self.btn_pin.setToolTip(
            t("quick_note.unpin_tip", "Unpin note")
            if new_pin
            else t("quick_note.pin_tip", "Pin note to top")
        )
        self.pin_toggled.emit(self.entry.get("id", ""), new_pin)

    def _style_pin_button(self, is_pinned: bool) -> None:
        if is_pinned:
            self.btn_pin.setStyleSheet(
                "QPushButton { background-color: rgba(0, 229, 255, 0.2); "
                "border: 1px solid #00e5ff; border-radius: 4px; padding: 1px; } "
                "QPushButton:hover { background-color: rgba(0, 229, 255, 0.35); }"
            )
        else:
            self.btn_pin.setStyleSheet(
                "QPushButton { background-color: transparent; "
                "border: 1px solid rgba(139, 148, 158, 0.3); border-radius: 4px; padding: 1px; } "
                "QPushButton:hover { background-color: rgba(139, 148, 158, 0.2); border-color: #8b949e; }"
            )

    # ------------------------------------------------------------------ #
    # Send To Menu (Loot / Report)
    # ------------------------------------------------------------------ #

    def _build_send_menu(self) -> None:
        send_menu = QMenu(self.btn_send)

        act_loot = QAction(icon("fa5s.archive"), t("quick_note.send_loot", "Send to Loot"), send_menu)
        act_loot.triggered.connect(lambda: self.promote_requested.emit(self.entry))
        send_menu.addAction(act_loot)

        act_report = QAction(
            icon("fa5s.file-alt"),
            t("quick_note.send_report", "Send to Report"),
            send_menu,
        )
        act_report.triggered.connect(lambda: self.send_to_report_requested.emit(self.entry))
        send_menu.addAction(act_report)

        self.btn_send.setMenu(send_menu)

    # ------------------------------------------------------------------ #
    # Inline Editing Actions
    # ------------------------------------------------------------------ #

    def _start_edit(self) -> None:
        self.is_editing = True
        self.lbl_content.setVisible(False)
        self.editor.setPlainText(self.entry.get("text", ""))
        self.edit_container.setVisible(True)
        self.editor.setFocus()

    def _save_edit(self) -> None:
        new_text = self.editor.toPlainText().strip()
        if not new_text:
            return
        self.is_editing = False
        self.entry["text"] = new_text
        self.lbl_content.setText(new_text)
        self.edit_container.setVisible(False)
        self.lbl_content.setVisible(True)
        self.edited.emit(self.entry.get("id", ""), new_text)

    def _trigger_edit(self) -> None:
        """Emits edit_requested if connected, otherwise falls back to inline editor."""
        if self.receivers(self.edit_requested) > 0:
            self.edit_requested.emit(self.entry)
        else:
            self._start_edit()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if hasattr(event, "button") and event.button() == Qt.MouseButton.LeftButton:
                self._trigger_edit()
                return True
        return super().eventFilter(watched, event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._trigger_edit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def _cancel_edit(self) -> None:
        self.is_editing = False
        self.editor.setPlainText(self.entry.get("text", ""))
        self.edit_container.setVisible(False)
        self.lbl_content.setVisible(True)

    # ------------------------------------------------------------------ #
    # Copy Helper
    # ------------------------------------------------------------------ #

    def _copy_content(self) -> None:
        """Copies note text to system clipboard."""
        text = self.entry.get("text", "").strip()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            try:
                pyperclip.copy(text)
            except (pyperclip.PyperclipException, OSError) as exc:
                logger.debug(f"pyperclip copy fallback failed: {exc}")

            self.btn_copy.setIcon(icon("fa5s.check", color=STATUS_SUCCESS))
            self.btn_copy.setProperty("class", "CardIconBtnSuccess")
            self.btn_copy.setToolTip(t("snippet.copied", "Copied!"))
            self.btn_copy.style().unpolish(self.btn_copy)
            self.btn_copy.style().polish(self.btn_copy)

            QTimer.singleShot(1200, self._reset_copy_btn)
            self.copied.emit(text)

    def _reset_copy_btn(self) -> None:
        self.btn_copy.setText("")
        self.btn_copy.setIcon(icon("fa5s.copy"))
        self.btn_copy.setProperty("class", "CardIconBtn")
        self.btn_copy.setToolTip(t("quick_note.copy_tip", "Copy quick note"))
        self.btn_copy.style().unpolish(self.btn_copy)
        self.btn_copy.style().polish(self.btn_copy)

    def set_selected(self, selected: bool) -> None:
        """Sets the checkbox state without triggering redundant events."""
        self.chk_select.blockSignals(True)
        self.chk_select.setChecked(selected)
        self.chk_select.blockSignals(False)

    def clear_selection(self) -> None:
        """Clear the selection checkbox when the shared selection model resets."""
        self.set_selected(False)

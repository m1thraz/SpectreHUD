"""Compact stream row for a single Quick Note."""

from datetime import datetime
from typing import Any, Dict, Optional

import pyperclip
from PyQt6.QtCore import QEvent, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QContextMenuEvent, QFont, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.logger import get_logger
from core.phases import get_phase
from ui.styles.icons import icon
from ui.styles.palette import STATUS_SUCCESS

logger = get_logger("quick_note_card")

CARD_ICON_SIZE = QSize(13, 13)
COMPLETION_UNDO_MS = 3500
OVERDUE_HOURS = 3.0


def parse_note_timestamp(value: Any) -> Optional[datetime]:
    """Accept both timestamp formats produced by the configurable clock."""
    timestamp = str(value or "").strip()
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M:%S %p"):
        try:
            return datetime.strptime(timestamp, pattern)
        except ValueError:
            continue
    return None


def opacity_for_age(created_at: datetime, now: Optional[datetime] = None) -> float:
    """Keep old open notes legible while making stream age scannable."""
    age_hours = ((now or datetime.now()) - created_at).total_seconds() / 3600
    if age_hours < 0.5:
        return 1.0
    if age_hours < 2:
        return 0.85
    if age_hours < 6:
        return 0.65
    return 0.5


class NoteEditor(QPlainTextEdit):
    """Inline editor with explicit keyboard save and cancel boundaries."""

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
    """Show one primary completion action and defer secondary actions to context."""

    copied = pyqtSignal(str)
    edit_requested = pyqtSignal(dict)
    promote_requested = pyqtSignal(dict)
    send_to_report_requested = pyqtSignal(dict)
    deleted = pyqtSignal(str)
    status_changed = pyqtSignal(str, str)
    pin_toggled = pyqtSignal(str, bool)
    selection_changed = pyqtSignal(str, bool)
    completion_requested = pyqtSignal(str)
    completion_undo_requested = pyqtSignal(str)
    completion_expired = pyqtSignal(str)

    def __init__(
        self,
        entry: Dict[str, Any],
        parent: Optional[QWidget] = None,
        *,
        now: Optional[datetime] = None,
    ):
        super().__init__(parent)
        self.setObjectName("QuickNoteStreamCard")
        self.entry = dict(entry)
        self._completion_timer = QTimer(self)
        self._completion_timer.setSingleShot(True)
        self._completion_timer.timeout.connect(
            lambda: self.completion_expired.emit(self.entry.get("id", ""))
        )
        self._created_at = parse_note_timestamp(self.entry.get("timestamp"))
        self._age_hours = (
            max(0.0, ((now or datetime.now()) - self._created_at).total_seconds() / 3600)
            if self._created_at is not None
            else 0.0
        )
        self._init_ui()
        self._apply_age_presentation(now)
        self._update_completion_style()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(9)

        self.chk_select = QCheckBox()
        self.chk_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_select.setToolTip(t("quick_note.select_tip", "Select for bulk action"))
        self.chk_select.toggled.connect(
            lambda checked: self.selection_changed.emit(self.entry.get("id", ""), checked)
        )
        self.chk_select.setVisible(False)
        layout.addWidget(self.chk_select, alignment=Qt.AlignmentFlag.AlignTop)

        self.btn_complete = QPushButton()
        self.btn_complete.setProperty("class", "CardIconBtn")
        self.btn_complete.setIconSize(QSize(15, 15))
        self.btn_complete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_complete.clicked.connect(self._request_completion_toggle)
        layout.addWidget(self.btn_complete, alignment=Qt.AlignmentFlag.AlignTop)

        self.content_container = QWidget()
        content = QVBoxLayout(self.content_container)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(4)

        self.lbl_content = QLabel(self.entry.get("text", ""))
        self.lbl_content.setTextFormat(Qt.TextFormat.MarkdownText)
        self.lbl_content.setObjectName("QuickNoteText")
        self.lbl_content.setWordWrap(True)
        self.lbl_content.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.lbl_content.installEventFilter(self)
        self.lbl_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        content.addWidget(self.lbl_content)

        self.lbl_meta = QLabel(self._metadata_text())
        self.lbl_meta.setObjectName("QuickNoteMeta")
        content.addWidget(self.lbl_meta)

        self.undo_row = QWidget()
        undo_layout = QHBoxLayout(self.undo_row)
        undo_layout.setContentsMargins(0, 2, 0, 0)
        undo_layout.setSpacing(6)
        self.lbl_completed = QLabel(t("quick_note.completed_pending", "Marked as done"))
        self.lbl_completed.setObjectName("QuickNoteMeta")
        undo_layout.addWidget(self.lbl_completed)
        self.btn_undo = QPushButton(t("quick_note.undo", "Undo"))
        self.btn_undo.setProperty("class", "SecondaryBtn")
        self.btn_undo.clicked.connect(self._request_undo)
        undo_layout.addWidget(self.btn_undo)
        undo_layout.addStretch()
        self.undo_row.setVisible(False)
        content.addWidget(self.undo_row)

        layout.addWidget(self.content_container, stretch=1)

        self.btn_copy = QPushButton()
        self.btn_copy.setIcon(icon("fa5s.copy"))
        self.btn_copy.setIconSize(CARD_ICON_SIZE)
        self.btn_copy.setProperty("class", "CardIconBtn")
        self.btn_copy.setToolTip(t("quick_note.copy_tip", "Copy quick note"))
        self.btn_copy.clicked.connect(self._copy_content)
        layout.addWidget(self.btn_copy, alignment=Qt.AlignmentFlag.AlignTop)

    def _metadata_text(self) -> str:
        timestamp = str(self.entry.get("timestamp", "")).strip()
        phase = get_phase(self.entry.get("category", "misc"))
        parts = [part for part in (timestamp, phase.short) if part]
        if self._is_overdue():
            hours = max(3, int(self._age_hours))
            overdue = t("quick_note.open_for_hours", "open for {hours} h").replace(
                "{hours}", str(hours)
            )
            parts.append(overdue)
        return "  ·  ".join(parts)

    def _is_overdue(self) -> bool:
        return (
            self.entry.get("status", "inbox") != "resolved"
            and not bool(self.entry.get("pinned", False))
            and self._age_hours >= OVERDUE_HOURS
        )

    def _apply_age_presentation(self, now: Optional[datetime]) -> None:
        excluded = self.entry.get("status", "inbox") == "resolved" or bool(
            self.entry.get("pinned", False)
        )
        effect = QGraphicsOpacityEffect(self.content_container)
        effect.setOpacity(
            1.0
            if excluded or self._created_at is None
            else opacity_for_age(self._created_at, now=now)
        )
        self.content_container.setGraphicsEffect(effect)
        self.setProperty("overdue", self._is_overdue())

    def _request_completion_toggle(self) -> None:
        note_id = self.entry.get("id", "")
        if self.entry.get("status", "inbox") == "resolved":
            self.status_changed.emit(note_id, "inbox")
        else:
            self.completion_requested.emit(note_id)

    def show_completion_pending(self) -> None:
        self.entry["status"] = "resolved"
        self.undo_row.setVisible(True)
        self.btn_complete.setEnabled(False)
        self._update_completion_style(pending=True)
        self._completion_timer.start(COMPLETION_UNDO_MS)

    def _request_undo(self) -> None:
        self._completion_timer.stop()
        self.completion_undo_requested.emit(self.entry.get("id", ""))

    def _update_completion_style(self, pending: bool = False) -> None:
        resolved = self.entry.get("status", "inbox") == "resolved"
        self.btn_complete.setIcon(
            icon("fa5s.check-circle" if resolved else "fa5.circle", color=STATUS_SUCCESS)
        )
        self.btn_complete.setToolTip(
            t("quick_note.reopen_tip", "Move back to Inbox")
            if resolved and not pending
            else t("quick_note.complete_tip", "Mark note as done")
        )
        self.lbl_content.setProperty("resolved", resolved)
        self.lbl_content.style().unpolish(self.lbl_content)
        self.lbl_content.style().polish(self.lbl_content)
        font = QFont(self.lbl_content.font())
        font.setStrikeOut(resolved)
        self.lbl_content.setFont(font)

    def _build_context_menu(self) -> QMenu:
        menu = QMenu(self)
        pinned = bool(self.entry.get("pinned", False))
        pin_action = QAction(
            icon("fa5s.thumbtack"),
            t("quick_note.unpin", "Unpin") if pinned else t("quick_note.pin", "Pin"),
            menu,
        )
        pin_action.triggered.connect(
            lambda: self.pin_toggled.emit(self.entry.get("id", ""), not pinned)
        )
        menu.addAction(pin_action)

        followup = self.entry.get("status", "inbox") == "followup"
        follow_action = QAction(
            icon("fa5s.clock"),
            t("quick_note.move_inbox", "Move to Inbox")
            if followup
            else t("quick_note.set_followup", "Set Follow-up"),
            menu,
        )
        follow_action.triggered.connect(
            lambda: self.status_changed.emit(
                self.entry.get("id", ""), "inbox" if followup else "followup"
            )
        )
        menu.addAction(follow_action)
        menu.addSeparator()

        loot_action = QAction(
            icon("fa5s.archive"), t("quick_note.send_loot", "Send to Loot"), menu
        )
        loot_action.setToolTip(
            t("quick_note.send_loot_tip", "Create structured Loot; the Quick Note is removed after a successful save")
        )
        loot_action.triggered.connect(lambda: self.promote_requested.emit(self.entry))
        menu.addAction(loot_action)
        report_action = QAction(
            icon("fa5s.file-alt"), t("quick_note.send_report", "Send to Report"), menu
        )
        report_action.setToolTip(
            t("quick_note.send_report_tip", "Append to the current report and mark this Quick Note as resolved")
        )
        report_action.triggered.connect(lambda: self.send_to_report_requested.emit(self.entry))
        menu.addAction(report_action)

        target_ip = str(self.entry.get("target_ip", "")).strip()
        if target_ip:
            menu.addSeparator()
            target_action = QAction(icon("fa5s.crosshairs"), target_ip, menu)
            target_action.setEnabled(False)
            menu.addAction(target_action)

        menu.addSeparator()
        delete_action = QAction(
            icon("fa5s.trash"), t("quick_note.delete_tip", "Delete this quick note"), menu
        )
        delete_action.triggered.connect(lambda: self.deleted.emit(self.entry.get("id", "")))
        menu.addAction(delete_action)
        return menu

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self._build_context_menu().exec(event.globalPos())

    def _trigger_edit(self) -> None:
        self.edit_requested.emit(self.entry)

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

    def _copy_content(self) -> None:
        text = self.entry.get("text", "").strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
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
        self.btn_copy.setIcon(icon("fa5s.copy"))
        self.btn_copy.setProperty("class", "CardIconBtn")
        self.btn_copy.setToolTip(t("quick_note.copy_tip", "Copy quick note"))
        self.btn_copy.style().unpolish(self.btn_copy)
        self.btn_copy.style().polish(self.btn_copy)

    def set_selection_mode(self, enabled: bool) -> None:
        self.chk_select.setVisible(enabled)
        self.btn_complete.setVisible(not enabled)

    def set_selected(self, selected: bool) -> None:
        self.chk_select.blockSignals(True)
        self.chk_select.setChecked(selected)
        self.chk_select.blockSignals(False)

    def clear_selection(self) -> None:
        self.set_selected(False)

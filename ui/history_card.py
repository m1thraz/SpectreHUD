from typing import Any, Dict, Optional

import pyperclip
from PyQt6.QtCore import QEvent, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QContextMenuEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.logger import get_logger
from ui.quick_note_card import opacity_for_age, parse_note_timestamp
from ui.styles.icons import icon
from ui.styles.palette import STATUS_ERROR, STATUS_SUCCESS

logger = get_logger(__name__)

CARD_ICON_SIZE = QSize(13, 13)


class HistoryCard(QFrame):
    """Compact stream row for a single clipboard history entry.

    Resting state: content text + muted meta line + Copy icon + Promote button.
    Edit via double-click or context menu; Delete via context menu only.
    """

    copied = pyqtSignal(str)
    edit_requested = pyqtSignal(dict)
    transfer_to_loot = pyqtSignal(dict)
    transfer_to_note = pyqtSignal(dict)
    # Legacy aliases kept so existing signal connections don't break.
    add_to_loot_requested = transfer_to_loot
    added_to_loot = transfer_to_loot
    add_to_note_requested = transfer_to_note
    deleted = pyqtSignal(str)
    entry_deleted = deleted

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("SnippetCard")
        self.entry = entry
        self._created_at = parse_note_timestamp(self.entry.get("timestamp"))
        self._init_ui()
        self._apply_age_opacity()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self.lbl_content = QLabel(self.entry.get("text", ""))
        self.lbl_content.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_content.setObjectName("CommandLabel")
        self.lbl_content.setWordWrap(True)
        self.lbl_content.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.lbl_content.installEventFilter(self)
        self.lbl_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.lbl_content)

        # Footer: muted meta | stretch | copy | promote
        footer = QHBoxLayout()
        footer.setSpacing(6)

        self.lbl_meta = QLabel(self._metadata_text())
        self.lbl_meta.setObjectName("QuickNoteMeta")
        self.lbl_meta.setTextFormat(Qt.TextFormat.PlainText)
        footer.addWidget(self.lbl_meta)
        footer.addStretch()

        self.btn_copy = QPushButton()
        self.btn_copy.setIcon(icon("fa5s.copy"))
        self.btn_copy.setIconSize(CARD_ICON_SIZE)
        self.btn_copy.setProperty("class", "CardIconBtn")
        self.btn_copy.setToolTip(t("history.copy_tip", "Copy history entry"))
        self.btn_copy.clicked.connect(self._copy_content)
        footer.addWidget(self.btn_copy)

        self.btn_promote = QPushButton(t("history.promote", "Promote ▾"))
        self.btn_promote.setIcon(icon("fa5s.inbox"))
        self.btn_promote.setIconSize(CARD_ICON_SIZE)
        self.btn_promote.setProperty("class", "SecondaryBtn")
        self.btn_promote.setToolTip(t("history.promote_tip", "Promote to Notes or Loot"))
        self.btn_promote.setMinimumWidth(95)
        self.btn_promote.clicked.connect(self._show_promote_menu)
        footer.addWidget(self.btn_promote)

        layout.addLayout(footer)

    # ------------------------------------------------------------------ #
    # Metadata helpers
    # ------------------------------------------------------------------ #

    def _metadata_text(self) -> str:
        ts = self.entry.get("timestamp", "")
        # Show only the time portion when a full datetime string is present.
        time_part = ts.split(" ")[-1] if " " in ts else ts

        target_ip = self.entry.get("target_ip", "")

        phase_part = ""
        phase_id = self.entry.get("phase_id", "")
        if phase_id:
            from core.phases import get_phase
            phase_part = get_phase(phase_id).short

        lines_count = self.entry.get("lines_count", 1)
        char_count = self.entry.get("char_count", 0)
        type_str = (
            "Command"
            if lines_count <= 2 and char_count < 120
            else f"{lines_count} lines ({char_count} chars)"
        )

        parts = [p for p in (time_part, target_ip, phase_part, type_str) if p]
        return "  ·  ".join(parts)

    def _apply_age_opacity(self) -> None:
        """Static age fade — calculated once at construction, never animated."""
        if self._created_at is None:
            return
        opacity = opacity_for_age(self._created_at)
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(opacity)
        self.setGraphicsEffect(effect)

    # ------------------------------------------------------------------ #
    # Promote actions
    # ------------------------------------------------------------------ #

    def _show_promote_menu(self) -> None:
        menu = QMenu(self)
        # Notes first — lower barrier, default workflow.
        menu.addAction(
            icon("fa5s.sticky-note"),
            t("history.promote_note", "To Notes"),
            self._on_promote_note,
        )
        menu.addAction(
            icon("fa5s.archive"),
            t("history.promote_loot", "To Loot"),
            self._on_promote_loot,
        )
        menu.exec(self.btn_promote.mapToGlobal(self.btn_promote.rect().bottomLeft()))

    def _on_promote_note(self) -> None:
        """Promotes entry to Quick Notes; button stays disabled to prevent double-promote."""
        self.btn_promote.setEnabled(False)
        self.transfer_to_note.emit(self.entry)
        self._show_promote_feedback(t("history.promoted_as_note", "Note ✓"), auto_reset=False)

    def _on_promote_loot(self) -> None:
        """Opens Loot dialog for entry; button resets after brief feedback."""
        self.transfer_to_loot.emit(self.entry)
        self._show_promote_feedback("Loot...", auto_reset=True)

    def _show_promote_feedback(self, text: str, *, auto_reset: bool) -> None:
        self.btn_promote.setText(text)
        self.btn_promote.setIcon(icon("fa5s.check", color=STATUS_SUCCESS))
        self.btn_promote.setProperty("class", "CopyBtnSuccess")
        self.btn_promote.style().unpolish(self.btn_promote)
        self.btn_promote.style().polish(self.btn_promote)
        if auto_reset:
            QTimer.singleShot(1200, self._reset_promote_btn)

    def _reset_promote_btn(self) -> None:
        self.btn_promote.setEnabled(True)
        self.btn_promote.setText(t("history.promote", "Promote ▾"))
        self.btn_promote.setIcon(icon("fa5s.inbox"))
        self.btn_promote.setProperty("class", "SecondaryBtn")
        self.btn_promote.style().unpolish(self.btn_promote)
        self.btn_promote.style().polish(self.btn_promote)

    # ------------------------------------------------------------------ #
    # Copy action
    # ------------------------------------------------------------------ #

    def _copy_content(self) -> None:
        text_to_copy = self.entry.get("text", "").strip()
        if not text_to_copy:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(text_to_copy)
        try:
            pyperclip.copy(text_to_copy)
        except (pyperclip.PyperclipException, OSError) as exc:
            logger.debug(f"pyperclip copy fallback failed: {exc}")

        self.btn_copy.setIcon(icon("fa5s.check", color=STATUS_SUCCESS))
        self.btn_copy.setProperty("class", "CardIconBtnSuccess")
        self.btn_copy.setToolTip(t("snippet.copied", "Copied!"))
        self.btn_copy.style().unpolish(self.btn_copy)
        self.btn_copy.style().polish(self.btn_copy)
        QTimer.singleShot(1200, self._reset_copy_btn)
        self.copied.emit(text_to_copy)

    def _reset_copy_btn(self) -> None:
        self.btn_copy.setText("")
        self.btn_copy.setIcon(icon("fa5s.copy"))
        self.btn_copy.setProperty("class", "CardIconBtn")
        self.btn_copy.setToolTip(t("history.copy_tip", "Copy history entry"))
        self.btn_copy.style().unpolish(self.btn_copy)
        self.btn_copy.style().polish(self.btn_copy)

    # ------------------------------------------------------------------ #
    # Context menu — Edit / Delete
    # ------------------------------------------------------------------ #

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        menu.addAction(
            icon("fa5s.pen"),
            t("history.edit_tip", "Edit this history entry"),
            lambda: self.edit_requested.emit(self.entry),
        )
        menu.addAction(
            icon("fa5s.trash", color=STATUS_ERROR),
            t("history.delete_tip", "Delete this history entry"),
            lambda: self.deleted.emit(self.entry.get("id", "")),
        )
        menu.exec(event.globalPos())

    # ------------------------------------------------------------------ #
    # Double-click → Edit
    # ------------------------------------------------------------------ #

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if hasattr(event, "button") and event.button() == Qt.MouseButton.LeftButton:
                self.edit_requested.emit(self.entry)
                return True
        return super().eventFilter(watched, event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.edit_requested.emit(self.entry)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

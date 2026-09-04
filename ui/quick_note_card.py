"""
Visual card displaying a single Quick Note in the Inbox / History panel.
"""

from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QApplication,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
import pyperclip

from core.logger import get_logger
from core.i18n import t

logger = get_logger("quick_note_card")


class QuickNoteCard(QFrame):
    """
    Card displaying a quick thought note with one-click copy, deletion,
    and promotion to formal Loot.
    """

    copied = pyqtSignal(str)
    promote_requested = pyqtSignal(dict)
    deleted = pyqtSignal(str)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("SnippetCard")
        self.entry = entry
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header Row: Note Badge, Category, Time, Target, Delete
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        # Quick Note Type Badge
        lbl_type = QLabel("📌 NOTE")
        lbl_type.setTextFormat(Qt.TextFormat.PlainText)
        lbl_type.setStyleSheet(
            "background-color: rgba(210, 153, 34, 0.18); color: #e3b341; "
            "border: 1px solid rgba(210, 153, 34, 0.4); border-radius: 4px; "
            "padding: 2px 6px; font-size: 10px; font-weight: bold;"
        )
        header_layout.addWidget(lbl_type)

        # Phase Category Badge
        cat = self.entry.get("category", "misc").upper()
        lbl_cat = QLabel(cat)
        lbl_cat.setTextFormat(Qt.TextFormat.PlainText)
        lbl_cat.setStyleSheet(
            "background-color: rgba(110, 118, 129, 0.2); color: #c9d1d9; "
            "border: 1px solid rgba(110, 118, 129, 0.4); border-radius: 4px; "
            "padding: 2px 6px; font-size: 10px; font-weight: bold;"
        )
        header_layout.addWidget(lbl_cat)

        # Time Badge
        ts = self.entry.get("timestamp", "")
        time_display = ts.split(" ")[-1] if " " in ts else ts
        if time_display:
            lbl_time = QLabel(time_display)
            lbl_time.setTextFormat(Qt.TextFormat.PlainText)
            lbl_time.setStyleSheet(
                "background-color: rgba(56, 139, 253, 0.15); color: #79c0ff; "
                "border: 1px solid rgba(56, 139, 253, 0.3); border-radius: 4px; "
                "padding: 2px 6px; font-size: 10px; font-weight: bold;"
            )
            header_layout.addWidget(lbl_time)

        # Target IP Badge (if present)
        target_ip = self.entry.get("target_ip", "")
        if target_ip:
            lbl_target = QLabel(target_ip)
            lbl_target.setTextFormat(Qt.TextFormat.PlainText)
            lbl_target.setStyleSheet(
                "background-color: rgba(0, 229, 255, 0.12); color: #00e5ff; "
                "border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 4px; "
                "padding: 2px 6px; font-size: 10px; font-weight: bold;"
            )
            header_layout.addWidget(lbl_target)

        header_layout.addStretch()

        # Delete Button
        btn_delete = QPushButton("✕")
        btn_delete.setProperty("class", "DangerBtn")
        btn_delete.setToolTip(t("quick_note.delete_tip", "Delete this quick note"))
        btn_delete.clicked.connect(lambda: self.deleted.emit(self.entry.get("id", "")))
        header_layout.addWidget(btn_delete)

        layout.addLayout(header_layout)

        # Content Box Row
        content_row = QHBoxLayout()
        content_row.setSpacing(8)

        self.lbl_content = QLabel(self.entry.get("text", ""))
        self.lbl_content.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_content.setObjectName("CommandLabel")
        self.lbl_content.setWordWrap(True)
        self.lbl_content.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.lbl_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        content_row.addWidget(self.lbl_content, stretch=1)

        # Action Buttons Column
        action_col = QVBoxLayout()
        action_col.setSpacing(4)

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setProperty("class", "CopyBtn")
        self.btn_copy.setMinimumWidth(95)
        self.btn_copy.clicked.connect(self._copy_content)
        action_col.addWidget(self.btn_copy)

        self.btn_promote = QPushButton("★ Promote")
        self.btn_promote.setProperty("class", "SecondaryBtn")
        self.btn_promote.setStyleSheet(
            "QPushButton { border-color: rgba(210, 153, 34, 0.6); color: #e3b341; } "
            "QPushButton:hover { background-color: rgba(210, 153, 34, 0.2); border-color: #e3b341; }"
        )
        self.btn_promote.setToolTip(
            t("quick_note.promote_tip", "Promote note to formal Loot and remove from inbox")
        )
        self.btn_promote.setMinimumWidth(95)
        self.btn_promote.clicked.connect(lambda: self.promote_requested.emit(self.entry))
        action_col.addWidget(self.btn_promote)

        content_row.addLayout(action_col)
        layout.addLayout(content_row)

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

            self.btn_copy.setText("✓ Copied!")
            self.btn_copy.setProperty("class", "CopyBtnSuccess")
            self.btn_copy.style().unpolish(self.btn_copy)
            self.btn_copy.style().polish(self.btn_copy)

            QTimer.singleShot(1200, self._reset_copy_btn)
            self.copied.emit(text)

    def _reset_copy_btn(self) -> None:
        self.btn_copy.setText("Copy")
        self.btn_copy.setProperty("class", "CopyBtn")
        self.btn_copy.style().unpolish(self.btn_copy)
        self.btn_copy.style().polish(self.btn_copy)

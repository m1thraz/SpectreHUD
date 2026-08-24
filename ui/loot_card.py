from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QPlainTextEdit, QPushButton, QWidget, QApplication
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from typing import Dict, Any
from core.loot_manager import LOOT_TYPES
import pyperclip

class LootCard(QFrame):
    """Visual card displaying a single loot/note item with 1-click copying and delete support."""

    copied = pyqtSignal(str)
    deleted = pyqtSignal(str)

    def __init__(self, entry: Dict[str, Any], parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("SnippetCard")
        self.entry = entry
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        # Header Row: Badge, Title, Target IP, Time, Delete
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        # Type Badge
        entry_type = self.entry.get("type", "note")
        badge_info = next((t for t in LOOT_TYPES if t["id"] == entry_type), {"name": "📝 Notiz", "icon": "📝", "badge_class": "BadgeNote"})
        
        lbl_badge = QLabel(f"{badge_info['icon']} {badge_info['name'].split(' ')[1] if ' ' in badge_info['name'] else badge_info['name']}")
        lbl_badge.setProperty("class", f"LootBadge {badge_info['badge_class']}")
        header_layout.addWidget(lbl_badge)

        # Title
        lbl_title = QLabel(self.entry.get("title", "Unbenannt"))
        lbl_title.setObjectName("SnippetTitle")
        lbl_title.setWordWrap(True)
        header_layout.addWidget(lbl_title, stretch=1)

        # Target IP (if set)
        target_ip = self.entry.get("target_ip", "")
        if target_ip:
            lbl_target = QLabel(f"🎯 {target_ip}")
            lbl_target.setStyleSheet("color: #58a6ff; font-size: 11px; font-weight: 500;")
            header_layout.addWidget(lbl_target)

        # Timestamp
        timestamp = self.entry.get("timestamp", "")
        if timestamp:
            time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
            lbl_time = QLabel(time_part)
            lbl_time.setStyleSheet("color: #6e7681; font-size: 10px;")
            header_layout.addWidget(lbl_time)

        # Delete Button
        btn_delete = QPushButton("✕")
        btn_delete.setProperty("class", "DangerBtn")
        btn_delete.setToolTip("Diesen Eintrag löschen")
        btn_delete.clicked.connect(lambda: self.deleted.emit(self.entry.get("id", "")))
        header_layout.addWidget(btn_delete)

        layout.addLayout(header_layout)

        # Content Box & Copy Button Row
        content_row = QHBoxLayout()
        content_row.setSpacing(8)

        self.txt_content = QPlainTextEdit()
        self.txt_content.setObjectName("CommandBox")
        self.txt_content.setReadOnly(True)
        self.txt_content.setPlainText(self.entry.get("content", ""))
        self.txt_content.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.txt_content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.txt_content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        lines_count = max(1, self.entry.get("content", "").count("\n") + 1)
        self.txt_content.setFixedHeight(min(140, max(36, lines_count * 20 + 14)))
        content_row.addWidget(self.txt_content, stretch=1)

        self.btn_copy = QPushButton("📋 Kopieren")
        self.btn_copy.setProperty("class", "CopyBtn")
        self.btn_copy.setMinimumWidth(90)
        self.btn_copy.clicked.connect(self._copy_content)
        content_row.addWidget(self.btn_copy, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addLayout(content_row)

    def _copy_content(self) -> None:
        """Copies entry content directly to clipboard."""
        text_to_copy = self.entry.get("content", "").strip()
        if text_to_copy:
            clipboard = QApplication.clipboard()
            clipboard.setText(text_to_copy)
            try:
                pyperclip.copy(text_to_copy)
            except Exception:
                pass

            # Visual animation
            self.btn_copy.setText("✓ Kopiert!")
            self.btn_copy.setProperty("class", "CopyBtnSuccess")
            self.btn_copy.style().unpolish(self.btn_copy)
            self.btn_copy.style().polish(self.btn_copy)

            QTimer.singleShot(1200, self._reset_copy_btn)
            self.copied.emit(text_to_copy)

    def _reset_copy_btn(self) -> None:
        self.btn_copy.setText("📋 Kopieren")
        self.btn_copy.setProperty("class", "CopyBtn")
        self.btn_copy.style().unpolish(self.btn_copy)
        self.btn_copy.style().polish(self.btn_copy)

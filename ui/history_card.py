from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QPlainTextEdit, QPushButton, QWidget, QApplication
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from typing import Dict, Any
import pyperclip

class HistoryCard(QFrame):
    """Visual card displaying a single clipboard history item with 1-click copying and Loot-transfer."""

    copied = pyqtSignal(str)
    transfer_to_loot = pyqtSignal(dict)
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

        # Header Row: Time, Target IP, Stats, Delete
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        # Time Badge
        ts = self.entry.get("timestamp", "")
        time_display = ts.split(" ")[-1] if " " in ts else ts
        lbl_time = QLabel(f"🕒 {time_display}")
        lbl_time.setStyleSheet("background-color: rgba(56, 139, 253, 0.15); color: #79c0ff; border: 1px solid rgba(56, 139, 253, 0.3); border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        header_layout.addWidget(lbl_time)

        # Target IP Badge (if present)
        target_ip = self.entry.get("target_ip", "")
        if target_ip:
            lbl_target = QLabel(f"🎯 {target_ip}")
            lbl_target.setStyleSheet("background-color: rgba(0, 229, 255, 0.12); color: #00e5ff; border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
            header_layout.addWidget(lbl_target)

        # Stats Badge
        lines_count = self.entry.get("lines_count", 1)
        char_count = self.entry.get("char_count", 0)
        type_str = "⌨️ Befehl" if lines_count <= 2 and char_count < 120 else f"📄 {lines_count} Zeilen ({char_count} Z.)"
        lbl_stats = QLabel(type_str)
        lbl_stats.setStyleSheet("color: #8b949e; font-size: 10px;")
        header_layout.addWidget(lbl_stats)

        header_layout.addStretch()

        # Delete Button
        btn_delete = QPushButton("✕")
        btn_delete.setProperty("class", "DangerBtn")
        btn_delete.setToolTip("Diesen Verlaufseintrag löschen")
        btn_delete.clicked.connect(lambda: self.deleted.emit(self.entry.get("id", "")))
        header_layout.addWidget(btn_delete)

        layout.addLayout(header_layout)

        # Content Box
        content_row = QHBoxLayout()
        content_row.setSpacing(8)

        self.txt_content = QPlainTextEdit()
        self.txt_content.setObjectName("CommandBox")
        self.txt_content.setReadOnly(True)
        self.txt_content.setPlainText(self.entry.get("text", ""))
        self.txt_content.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.txt_content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.txt_content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Dynamic height
        raw_lines = max(1, self.entry.get("text", "").count("\n") + 1)
        self.txt_content.setFixedHeight(min(140, max(36, raw_lines * 19 + 14)))
        content_row.addWidget(self.txt_content, stretch=1)

        # Action Buttons Column
        action_col = QVBoxLayout()
        action_col.setSpacing(4)

        self.btn_copy = QPushButton("📋 Kopieren")
        self.btn_copy.setProperty("class", "CopyBtn")
        self.btn_copy.setMinimumWidth(90)
        self.btn_copy.clicked.connect(self._copy_content)
        action_col.addWidget(self.btn_copy)

        self.btn_to_loot = QPushButton("➕ Zu Loot")
        self.btn_to_loot.setProperty("class", "SecondaryBtn")
        self.btn_to_loot.setToolTip("Diesen Text als Credential/Notiz in Session-Loot übernehmen")
        self.btn_to_loot.setMinimumWidth(90)
        self.btn_to_loot.clicked.connect(lambda: self.transfer_to_loot.emit(self.entry))
        action_col.addWidget(self.btn_to_loot)

        content_row.addLayout(action_col)
        layout.addLayout(content_row)

    def _copy_content(self) -> None:
        """Copies content back to system clipboard."""
        text_to_copy = self.entry.get("text", "").strip()
        if text_to_copy:
            clipboard = QApplication.clipboard()
            clipboard.setText(text_to_copy)
            try:
                pyperclip.copy(text_to_copy)
            except Exception:
                pass

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

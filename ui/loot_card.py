import os
import sys
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QWidget, QApplication, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QPixmap
from typing import Dict, Any
from core.loot_manager import LOOT_TYPES
import pyperclip

class LootCard(QFrame):
    """Visual card displaying a single loot/note item or screenshot thumbnail with natural word wrapping."""

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
        layout.setSpacing(6)

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

        # If Screenshot: Show image thumbnail & open button
        img_path = self._resolve_image_path()
        if entry_type == "screenshot" and img_path and img_path.exists():
            thumb_row = QHBoxLayout()
            thumb_row.setSpacing(8)

            lbl_thumb = QLabel()
            pix = QPixmap(str(img_path))
            if not pix.isNull():
                scaled = pix.scaledToHeight(75, Qt.TransformationMode.SmoothTransformation)
                lbl_thumb.setPixmap(scaled)
                lbl_thumb.setStyleSheet("border: 1px solid #30363d; border-radius: 4px;")
                thumb_row.addWidget(lbl_thumb)

            btn_open_img = QPushButton("🖼️ Öffnen")
            btn_open_img.setProperty("class", "SecondaryBtn")
            btn_open_img.setToolTip("Screenshot in Standard-Bildbetrachter öffnen")
            btn_open_img.clicked.connect(lambda: self._open_image(img_path))
            thumb_row.addWidget(btn_open_img, alignment=Qt.AlignmentFlag.AlignVCenter)

            thumb_row.addStretch()
            layout.addLayout(thumb_row)

        # Content Box & Copy Button Row
        content_row = QHBoxLayout()
        content_row.setSpacing(8)

        self.lbl_content = QLabel(self.entry.get("content", ""))
        self.lbl_content.setObjectName("CommandLabel")
        self.lbl_content.setWordWrap(True)
        self.lbl_content.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | 
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.lbl_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        content_row.addWidget(self.lbl_content, stretch=1)

        self.btn_copy = QPushButton("📋 Kopieren")
        self.btn_copy.setProperty("class", "CopyBtn")
        self.btn_copy.setMinimumWidth(90)
        self.btn_copy.clicked.connect(self._copy_content)
        content_row.addWidget(self.btn_copy, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addLayout(content_row)

    def _resolve_image_path(self) -> Path:
        """Resolves file path for screenshot from entry."""
        if "file_path" in self.entry and self.entry["file_path"]:
            p = Path(self.entry["file_path"])
            if p.exists():
                return p

        content = self.entry.get("content", "")
        if "loot/" in content:
            import re
            m = re.search(r'\((loot/[^\)]+)\)', content)
            if m:
                rel = m.group(1)
                base_dir = Path.home() / "spectre_projects"
                matches = list(base_dir.glob(f"**/{Path(rel).name}"))
                if matches:
                    return matches[0]
        return None

    def _open_image(self, img_path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(img_path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(img_path)])
            else:
                subprocess.Popen(["xdg-open", str(img_path)])
        except Exception as e:
            print(f"[LootCard] Error opening image: {e}")

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

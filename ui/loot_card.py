import os
import sys
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QWidget, QApplication, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QPixmap, QMouseEvent
from typing import Dict, Any, Optional
from core.loot_manager import LOOT_TYPES, CATEGORIES
from core.project_manager import get_default_projects_dir
from core.logger import get_logger
import pyperclip

logger = get_logger("loot_card")

class LootCard(QFrame):
    """Visual card displaying a single loot/note item or screenshot thumbnail with natural word wrapping."""

    copied = pyqtSignal(str)
    deleted = pyqtSignal(str)
    edit_requested = pyqtSignal(dict)
    loot_deleted = deleted

    def __init__(self, entry: Dict[str, Any], project_dir: Optional[Path] = None, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("SnippetCard")
        self.entry = entry
        self.project_dir = project_dir
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header Row: Type Badge, Category Badge, Title, Target IP, Time, Edit, Delete
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        # 1. Type Badge
        entry_type = self.entry.get("type", "note")
        badge_info = next((t for t in LOOT_TYPES if t["id"] == entry_type), {"name": "Note", "icon": "", "badge_class": "BadgeNote"})
        
        lbl_badge = QLabel(badge_info["name"])
        lbl_badge.setProperty("class", f"LootBadge {badge_info['badge_class']}")
        header_layout.addWidget(lbl_badge)

        # 2. Category Badge
        cat_id = self.entry.get("category", "misc")
        cat_info = next((c for c in CATEGORIES if c["id"] == cat_id), {"name": "Miscellaneous", "icon": ""})
        cat_short_name = cat_info["name"].split(".")[1].strip().split("&")[0].strip() if "." in cat_info["name"] else cat_info["name"]
        lbl_cat = QLabel(cat_short_name)
        lbl_cat.setProperty("class", "CategoryBadge")
        lbl_cat.setToolTip(f"Pentest-Phase: {cat_info['name']}")
        header_layout.addWidget(lbl_cat)

        # 3. Title
        lbl_title = QLabel(self.entry.get("title", "Unbenannt"))
        lbl_title.setObjectName("SnippetTitle")
        lbl_title.setWordWrap(True)
        header_layout.addWidget(lbl_title, stretch=1)

        # 4. Target IP (if set)
        target_ip = self.entry.get("target_ip", "")
        if target_ip:
            lbl_target = QLabel(target_ip)
            lbl_target.setStyleSheet("color: #58a6ff; font-size: 11px; font-weight: 500;")
            header_layout.addWidget(lbl_target)

        # 5. Timestamp
        timestamp = self.entry.get("timestamp", "")
        if timestamp:
            time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
            lbl_time = QLabel(time_part)
            lbl_time.setStyleSheet("color: #6e7681; font-size: 10px;")
            header_layout.addWidget(lbl_time)

        # 6. Edit Button
        btn_edit = QPushButton("✎")
        btn_edit.setProperty("class", "EditBtn")
        btn_edit.setToolTip("Diesen Eintrag bearbeiten / umkategorisieren")
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(self.entry))
        header_layout.addWidget(btn_edit)

        # 7. Delete Button
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

            btn_open_img = QPushButton("Open")
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

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setProperty("class", "CopyBtn")
        self.btn_copy.setMinimumWidth(90)
        self.btn_copy.clicked.connect(self._copy_content)
        content_row.addWidget(self.btn_copy, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addLayout(content_row)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.edit_requested.emit(self.entry)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def _resolve_image_path(self) -> Optional[Path]:
        """
        Resolves file path for screenshot from entry strictly within this project's loot directory.
        Strictly prevents cross-project file leakage.
        """
        filename = None
        if "file_path" in self.entry and self.entry["file_path"]:
            filename = Path(self.entry["file_path"]).name
        elif "content" in self.entry:
            content = self.entry.get("content", "")
            if "loot/" in content:
                import re
                m = re.search(r'\((loot/[^\)]+)\)', content)
                if m:
                    rel = m.group(1)
                    filename = Path(rel).name

        if not filename:
            return None

        # 1. Look strictly in the assigned project directory
        if self.project_dir:
            candidate = Path(self.project_dir) / "loot" / filename
            if candidate.exists():
                return candidate
            return None

        # 2. Standalone fallback (e.g. tests or legacy without explicit project_dir)
        base_dir = get_default_projects_dir()
        for candidate_proj in [base_dir / "Default", base_dir]:
            candidate = candidate_proj / "loot" / filename
            if candidate.exists():
                return candidate

        return None

    def _open_image(self, img_path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(img_path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(img_path)])
            else:
                subprocess.Popen(["xdg-open", str(img_path)])
        except (OSError, FileNotFoundError, subprocess.SubprocessError) as e:
            logger.error(f"Error opening image {img_path}: {e}", exc_info=True)

    def _copy_content(self) -> None:
        """Copies entry content directly to clipboard."""
        text_to_copy = self.entry.get("content", "").strip()
        if text_to_copy:
            clipboard = QApplication.clipboard()
            clipboard.setText(text_to_copy)
            try:
                pyperclip.copy(text_to_copy)
            except (pyperclip.PyperclipException, OSError) as exc:
                logger.debug(f"pyperclip copy fallback failed: {exc}")

            self.btn_copy.setText("✓ Copied!")
            self.btn_copy.setProperty("class", "CopyBtnSuccess")
            self.btn_copy.style().unpolish(self.btn_copy)
            self.btn_copy.style().polish(self.btn_copy)

            QTimer.singleShot(1200, self._reset_copy_btn)
            self.copied.emit(text_to_copy)

    def _reset_copy_btn(self) -> None:
        self.btn_copy.setText("Copy")
        self.btn_copy.setProperty("class", "CopyBtn")
        self.btn_copy.style().unpolish(self.btn_copy)
        self.btn_copy.style().polish(self.btn_copy)

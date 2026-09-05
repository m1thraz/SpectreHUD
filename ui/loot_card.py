from pathlib import Path
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QApplication,
    QSizePolicy,
    QGraphicsOpacityEffect,
    QMessageBox,
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt, QMimeData, QSize, QEvent
from PyQt6.QtGui import QPixmap, QMouseEvent, QDrag, QTextLayout, QTextOption
from typing import Dict, Any, Optional
from core.loot.manager import LOOT_TYPES
from core.phases import get_phase
from core.project import get_default_projects_dir
from core.logger import get_logger
from core.i18n import t
from core.platform.opener import open_path
from ui.styles.icons import icon
from ui.styles.palette import STATUS_ERROR, STATUS_SUCCESS
from ui.elided_label import ElidedLabel, configure_badge_label
import pyperclip

logger = get_logger("loot_card")

CARD_ICON_SIZE = QSize(13, 13)


class LootCard(QFrame):
    """Visual card displaying a single loot/note item or screenshot thumbnail with natural word wrapping."""

    copied = pyqtSignal(str)
    deleted = pyqtSignal(str)
    edit_requested = pyqtSignal(dict)
    export_requested = pyqtSignal(str)
    obsidian_export_requested = pyqtSignal(str)
    loot_deleted = deleted

    def __init__(
        self,
        entry: Dict[str, Any],
        project_dir: Optional[Path] = None,
        parent: QWidget = None,
        preview_line_limit: Optional[int] = None,
    ):
        super().__init__(parent)
        self.setObjectName("lootCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.entry = entry
        self.project_dir = project_dir
        self.preview_line_limit = max(1, int(preview_line_limit)) if preview_line_limit else None
        self._full_content = str(self.entry.get("content", ""))
        self._last_preview_width = -1
        self._drag_start_position = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Row 1 (Metadata & Actions): Type Badge, Target IP, Time, Stretch, Edit, Export, Obsidian, Delete
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        # 1. Type Badge
        entry_type = self.entry.get("type", "note")
        badge_info = next(
            (t for t in LOOT_TYPES if t["id"] == entry_type),
            {"name": "Note", "icon": "", "badge_class": "BadgeNote"},
        )

        lbl_badge = QLabel(badge_info["name"])
        lbl_badge.setTextFormat(Qt.TextFormat.PlainText)
        lbl_badge.setProperty("class", f"LootBadge {badge_info['badge_class']}")
        configure_badge_label(lbl_badge, badge_info["name"], padding=14)
        header_layout.addWidget(lbl_badge)

        # 2. Target IP (if set)
        target_ip = self.entry.get("target_ip", "")
        if target_ip:
            lbl_target = QLabel(target_ip)
            lbl_target.setTextFormat(Qt.TextFormat.PlainText)
            lbl_target.setStyleSheet("color: #58a6ff; font-size: 11px; font-weight: 500;")
            configure_badge_label(lbl_target, target_ip, padding=8)
            header_layout.addWidget(lbl_target)

        # 3. Timestamp
        timestamp = self.entry.get("timestamp", "")
        if timestamp:
            time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
            lbl_time = QLabel(time_part)
            lbl_time.setTextFormat(Qt.TextFormat.PlainText)
            lbl_time.setStyleSheet("color: #6e7681; font-size: 10px;")
            configure_badge_label(lbl_time, time_part, padding=6)
            header_layout.addWidget(lbl_time)

        header_layout.addStretch()

        # 4. Action Buttons (Edit, Export, Obsidian, Delete)
        self.btn_edit = QPushButton()
        self.btn_edit.setIcon(icon("fa5s.pen"))
        self.btn_edit.setIconSize(CARD_ICON_SIZE)
        self.btn_edit.setProperty("class", "CardIconBtn")
        self.btn_edit.setToolTip(t("loot.edit_tip", "Edit or recategorize this entry"))
        self.btn_edit.clicked.connect(lambda: self.edit_requested.emit(self.entry))
        header_layout.addWidget(self.btn_edit)

        self.btn_export_file = QPushButton()
        self.btn_export_file.setIcon(icon("fa5s.download"))
        self.btn_export_file.setIconSize(CARD_ICON_SIZE)
        self.btn_export_file.setProperty("class", "CardIconBtn")
        self.btn_export_file.setToolTip(
            t("loot.export_file_tip", "Export this loot entry to a text file in the project")
        )
        self.btn_export_file.clicked.connect(
            lambda: self.export_requested.emit(self.entry.get("id", ""))
        )
        header_layout.addWidget(self.btn_export_file)

        self.btn_export_obsidian = QPushButton()
        self.btn_export_obsidian.setIcon(icon("fa5s.book-open"))
        self.btn_export_obsidian.setIconSize(CARD_ICON_SIZE)
        self.btn_export_obsidian.setProperty("class", "CardIconBtn")
        self.btn_export_obsidian.setToolTip(
            t("loot.export_obsidian_tip", "Append this loot entry to the Obsidian project note")
        )
        self.btn_export_obsidian.clicked.connect(
            lambda: self.obsidian_export_requested.emit(self.entry.get("id", ""))
        )
        header_layout.addWidget(self.btn_export_obsidian)

        self.btn_delete = QPushButton()
        self.btn_delete.setIcon(icon("fa5s.trash", color=STATUS_ERROR))
        self.btn_delete.setIconSize(CARD_ICON_SIZE)
        self.btn_delete.setProperty("class", "CardDangerIconBtn")
        self.btn_delete.setToolTip(t("loot.delete_tip", "Delete this entry"))
        self.btn_delete.clicked.connect(lambda: self.deleted.emit(self.entry.get("id", "")))
        header_layout.addWidget(self.btn_delete)

        layout.addLayout(header_layout)

        # Row 2: Grip Handle Icon, Title & Category Badge
        title_row = QHBoxLayout()
        title_row.setSpacing(6)

        self.lbl_grip = QLabel()
        grip_pix = icon("fa5s.grip-vertical", color="#6e7681").pixmap(QSize(12, 14))
        if not grip_pix.isNull():
            self.lbl_grip.setPixmap(grip_pix)
        self.lbl_grip.setFixedWidth(12)
        self.lbl_grip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_grip.setToolTip(t("loot.drag_tip", "Drag to move to another phase column"))
        title_row.addWidget(self.lbl_grip)

        title_text = self.entry.get("title", "Unbenannt")
        self.lbl_title = ElidedLabel(title_text)
        self.lbl_title.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_title.setObjectName("SnippetTitle")
        self.lbl_title.installEventFilter(self)
        title_row.addWidget(self.lbl_title, stretch=1)

        phase = get_phase(self.entry.get("category", "misc"))
        lbl_cat = QLabel(phase.short)
        lbl_cat.setTextFormat(Qt.TextFormat.PlainText)
        lbl_cat.setProperty("class", "CategoryBadge")
        lbl_cat.setToolTip(t("loot.category_tip", "Pentest phase: {name}", name=phase.long))
        configure_badge_label(lbl_cat, phase.short, padding=14)
        title_row.addWidget(lbl_cat)

        layout.addLayout(title_row)

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
            btn_open_img.setToolTip(
                t("loot.open_screenshot_tip", "Open screenshot in the default image viewer")
            )
            btn_open_img.clicked.connect(lambda: self._open_image(img_path))
            thumb_row.addWidget(btn_open_img, alignment=Qt.AlignmentFlag.AlignVCenter)

            thumb_row.addStretch()
            layout.addLayout(thumb_row)

        # Content Box & Copy Button Row
        content_row = QHBoxLayout()
        content_row.setSpacing(8)

        if self.preview_line_limit is not None:
            raw_lines = self._full_content.splitlines()
            if len(raw_lines) > self.preview_line_limit:
                initial_text = "\n".join(raw_lines[: self.preview_line_limit]) + "…"
            elif len(self._full_content) > 300:
                initial_text = self._full_content[:300] + "…"
            else:
                initial_text = self._full_content
        else:
            initial_text = self._full_content

        self.lbl_content = QLabel(initial_text)
        self.lbl_content.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_content.setObjectName("CommandLabel")
        self.lbl_content.setWordWrap(True)
        self.lbl_content.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.lbl_content.installEventFilter(self)
        if self.preview_line_limit is not None:
            # A very long unbroken value must not enlarge the Kanban column.
            # Ignoring only the horizontal hint lets the column supply the real
            # preview width; vertical sizing still follows the font metrics.
            self.lbl_content.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred,
            )
            self.lbl_content.setMinimumWidth(0)
        else:
            self.lbl_content.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
        content_row.addWidget(self.lbl_content, stretch=1)

        self.btn_copy = QPushButton()
        self.btn_copy.setIcon(icon("fa5s.copy"))
        self.btn_copy.setIconSize(CARD_ICON_SIZE)
        self.btn_copy.setProperty("class", "CardIconBtn")
        self.btn_copy.setToolTip(t("loot.copy_tip", "Copy this entry"))
        self.btn_copy.clicked.connect(self._copy_content)
        content_row.addWidget(self.btn_copy, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addLayout(content_row)
        if self.preview_line_limit is not None:
            QTimer.singleShot(0, self._update_content_preview)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "lbl_title") and isinstance(self.lbl_title, ElidedLabel):
            self.lbl_title._update_elision()
        if self.preview_line_limit is not None:
            self._update_content_preview()

    def _update_content_preview(self) -> None:
        """Render at most the configured number of visual lines with an ellipsis."""
        if self.preview_line_limit is None:
            self.lbl_content.setText(self._full_content)
            return

        margins = self.lbl_content.contentsMargins()
        available_width = max(
            1,
            self.lbl_content.width() - margins.left() - margins.right(),
        )
        metrics = self.lbl_content.fontMetrics()
        preview_height = (
            metrics.lineSpacing() * self.preview_line_limit + margins.top() + margins.bottom()
        )
        self.lbl_content.setMaximumHeight(preview_height)

        if available_width == self._last_preview_width:
            return
        self._last_preview_width = available_width

        # QTextLayout treats Unicode line separators as mandatory visual line
        # breaks while retaining one-to-one character offsets for truncation.
        layout_text = self._full_content.replace("\r\n", "\n").replace("\r", "\n")
        layout_text = layout_text.replace("\n", "\u2028")
        text_layout = QTextLayout(layout_text, self.lbl_content.font())
        text_option = QTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        text_layout.setTextOption(text_option)
        text_layout.beginLayout()

        last_start = 0
        last_end = 0
        for _ in range(self.preview_line_limit):
            line = text_layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(available_width)
            last_start = line.textStart()
            last_end = last_start + line.textLength()
        text_layout.endLayout()

        if last_end >= len(layout_text):
            preview = self._full_content
        else:
            prefix = layout_text[:last_start]
            final_line = layout_text[last_start:last_end].rstrip()
            elided_line = metrics.elidedText(
                f"{final_line}…",
                Qt.TextElideMode.ElideRight,
                available_width,
            )
            if not elided_line.endswith("…"):
                elided_line = f"{elided_line.rstrip()}…"
            preview = f"{prefix}{elided_line}".replace("\u2028", "\n")
        self.lbl_content.setText(preview)

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

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_start_position = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._drag_start_position is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self._drag_start_position).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            entry_id = str(self.entry.get("id", ""))
            if entry_id:
                mime_data = QMimeData()
                mime_data.setData("application/x-spectrehud-loot-entry", entry_id.encode("utf-8"))
                drag = QDrag(self)
                drag.setMimeData(mime_data)
                drag.setPixmap(self.grab())
                drag.setHotSpot(self._drag_start_position)
                opacity_effect = QGraphicsOpacityEffect(self)
                opacity_effect.setOpacity(0.60)
                self.setGraphicsEffect(opacity_effect)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                try:
                    drag.exec(Qt.DropAction.MoveAction)
                finally:
                    self.setGraphicsEffect(None)
                    self.setCursor(Qt.CursorShape.OpenHandCursor)
            self._drag_start_position = None
            event.accept()
            return
        super().mouseMoveEvent(event)

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

                m = re.search(r"\((loot/[^\)]+)\)", content)
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
        if open_path(img_path):
            return
        logger.error("Could not open loot image %s", img_path)
        QMessageBox.warning(
            self,
            t("loot.open_screenshot_error_title", "Screenshot unavailable"),
            t(
                "loot.open_screenshot_error_message",
                "The screenshot could not be opened:\n{path}",
                path=str(img_path),
            ),
        )

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
        self.btn_copy.setToolTip(t("loot.copy_tip", "Copy this entry"))
        self.btn_copy.style().unpolish(self.btn_copy)
        self.btn_copy.style().polish(self.btn_copy)

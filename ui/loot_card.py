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
    QMenu,
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt, QMimeData, QSize, QEvent, QPoint
from PyQt6.QtGui import QPixmap, QMouseEvent, QDrag, QContextMenuEvent, QCursor
from typing import Dict, Any, Optional
from core.loot import LOOT_TYPES
from core.phases import get_phase
from core.project import get_default_projects_dir
from core.logger import get_logger
from core.i18n import t
from ui.message_boxes import show_error_dialog
from core.platform import open_path
from ui.styles.icons import icon
from ui.styles.palette import STATUS_ERROR, STATUS_SUCCESS
from ui.elided_label import ElidedLabel, configure_badge_label
from ui.wrapped_value_view import WrappedValueView
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
        parent: Optional[QWidget] = None,
        board_mode: bool = False,
        density: str = "comfortable",  # "compact" | "comfortable"
    ):
        super().__init__(parent)
        self.setObjectName("lootCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.entry = entry
        self.project_dir = project_dir
        self.board_mode = board_mode
        self.density = density
        self.setProperty("boardCard", board_mode)
        self.setProperty("cardDensity", density)
        self._full_content = str(self.entry.get("content", ""))
        self._drag_start_position = None
        self._action_bar_widget: Optional[QWidget] = None
        self._init_ui()

    def _init_ui(self) -> None:
        entry_type = self.entry.get("type", "note")
        badge_info = next(
            (t for t in LOOT_TYPES if t["id"] == entry_type),
            {"name": "Note", "icon": "", "badge_class": "BadgeNote"},
        )
        target_ip = self.entry.get("target_ip", "")
        timestamp = self.entry.get("timestamp", "")
        title_text = self.entry.get("title", "Unbenannt")
        phase = get_phase(self.entry.get("category", "misc"))

        # Shared action buttons inside self._action_bar_widget (hidden in resting state)
        self._action_bar_widget = QWidget(self)
        self._action_bar_widget.setObjectName("LootCardActionBar")
        action_layout = QHBoxLayout(self._action_bar_widget)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(4)

        self.btn_edit = QPushButton()
        self.btn_edit.setIcon(icon("fa5s.pen"))
        self.btn_edit.setIconSize(CARD_ICON_SIZE)
        self.btn_edit.setProperty("class", "CardIconBtn")
        self.btn_edit.setToolTip(t("loot.edit_tip", "Edit or recategorize this entry"))
        self.btn_edit.clicked.connect(lambda: self.edit_requested.emit(self.entry))
        action_layout.addWidget(self.btn_edit)

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
        action_layout.addWidget(self.btn_export_file)

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
        action_layout.addWidget(self.btn_export_obsidian)

        self.btn_delete = QPushButton()
        self.btn_delete.setIcon(icon("fa5s.trash"))
        self.btn_delete.setIconSize(CARD_ICON_SIZE)
        self.btn_delete.setProperty("class", "CardDangerIconBtn")
        self.btn_delete.setToolTip(t("loot.delete_tip", "Delete this entry"))
        self.btn_delete.clicked.connect(lambda: self.deleted.emit(self.entry.get("id", "")))
        self.btn_delete.installEventFilter(self)
        action_layout.addWidget(self.btn_delete)

        self._action_bar_widget.setVisible(False)

        # Shared copy button
        self.btn_copy = QPushButton()
        self.btn_copy.setIcon(icon("fa5s.copy"))
        self.btn_copy.setIconSize(CARD_ICON_SIZE)
        self.btn_copy.setProperty("class", "CardIconBtn")
        self.btn_copy.setToolTip(t("loot.copy_tip", "Copy this entry"))
        self.btn_copy.clicked.connect(self._copy_content)

        # Shared grip handle & phase badge
        self.lbl_grip = QLabel()
        grip_pix = icon("fa5s.grip-vertical", color="#6e7681").pixmap(QSize(12, 14))
        if not grip_pix.isNull():
            self.lbl_grip.setPixmap(grip_pix)
        self.lbl_grip.setFixedWidth(12)
        self.lbl_grip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_grip.setToolTip(t("loot.drag_tip", "Drag to move to another phase column"))

        self.lbl_cat = QLabel(phase.short)
        self.lbl_cat.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_cat.setProperty("class", "CategoryBadge")
        self.lbl_cat.setToolTip(t("loot.category_tip", "Pentest phase: {name}", name=phase.long))
        configure_badge_label(self.lbl_cat, phase.short, padding=14)

        if self.density == "compact":
            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 5, 8, 5)
            layout.setSpacing(0)

            compact_row = QHBoxLayout()
            compact_row.setContentsMargins(0, 0, 0, 0)
            compact_row.setSpacing(6)

            compact_row.addWidget(self.lbl_grip)

            self.lbl_title = ElidedLabel(title_text)
            self.lbl_title.setTextFormat(Qt.TextFormat.PlainText)
            self.lbl_title.setObjectName("SnippetTitle")
            self.lbl_title.installEventFilter(self)
            compact_row.addWidget(self.lbl_title, stretch=1)

            compact_row.addWidget(self.lbl_cat)
            compact_row.addWidget(self.btn_copy)

            layout.addLayout(compact_row)

            # Hidden metadata/content widgets to preserve attribute contract
            self.lbl_badge = QLabel(badge_info["name"].upper())
            self.lbl_badge.setVisible(False)
            self.lbl_content = WrappedValueView(self._full_content)
            self.lbl_content.setVisible(False)

            tooltip_lines = [f"[{badge_info['name'].upper()}] {title_text}"]
            if target_ip:
                tooltip_lines.append(f"Target: {target_ip}")
            if timestamp:
                time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
                tooltip_lines.append(f"Time: {time_part}")
            if self._full_content:
                tooltip_lines.append(f"\n{self._full_content}")
            self.setToolTip("\n".join(tooltip_lines))
        else:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(6)

            # Row 1 (Metadata & Actions): Consolidated single row
            header_layout = QHBoxLayout()
            header_layout.setSpacing(6)

            self.lbl_badge = QLabel(badge_info["name"].upper())
            self.lbl_badge.setTextFormat(Qt.TextFormat.PlainText)
            self.lbl_badge.setProperty("class", f"LootBadge {badge_info['badge_class']}")
            configure_badge_label(self.lbl_badge, self.lbl_badge.text(), padding=18)
            header_layout.addWidget(self.lbl_badge)

            if target_ip:
                self.lbl_target = QLabel(target_ip)
                self.lbl_target.setTextFormat(Qt.TextFormat.PlainText)
                self.lbl_target.setStyleSheet("color: #58a6ff; font-size: 11px; font-weight: 500;")
                if self.board_mode:
                    self.lbl_target.setWordWrap(True)
                    self.lbl_target.setMinimumWidth(0)
                    self.lbl_target.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                else:
                    configure_badge_label(self.lbl_target, target_ip, padding=8)
                header_layout.addWidget(self.lbl_target)

            if timestamp:
                time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
                self.lbl_time = QLabel(time_part)
                self.lbl_time.setTextFormat(Qt.TextFormat.PlainText)
                self.lbl_time.setStyleSheet("color: #6e7681; font-size: 10px;")
                configure_badge_label(self.lbl_time, time_part, padding=6)
                header_layout.addWidget(self.lbl_time)

            header_layout.addStretch()
            header_layout.addWidget(self.btn_copy)
            layout.addLayout(header_layout)

            # Row 2: Grip Handle Icon, Title & Category Badge
            title_row = QHBoxLayout()
            title_row.setSpacing(6)
            title_row.addWidget(self.lbl_grip)

            self.lbl_title = ElidedLabel(title_text)
            self.lbl_title.setTextFormat(Qt.TextFormat.PlainText)
            self.lbl_title.setObjectName("SnippetTitle")
            self.lbl_title.installEventFilter(self)
            title_row.addWidget(self.lbl_title, stretch=1)

            title_row.addWidget(self.lbl_cat)
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

            # Row 4: Content Box
            self.lbl_content = WrappedValueView(self._full_content)
            self.lbl_content.setObjectName("CommandLabel")
            self.lbl_content.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            self.lbl_content.installEventFilter(self)
            self.lbl_content.viewport().installEventFilter(self)
            self.lbl_content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            self.lbl_content.setMinimumWidth(0)
            layout.addWidget(self.lbl_content)

            QTimer.singleShot(0, self._update_content_height)

    def _update_content_height(self) -> None:
        # Setting a minimum can synchronously resize the text viewport again.
        if getattr(self, "_updating_content_height", False):
            return
        self._updating_content_height = True
        try:
            for label in (getattr(self, "lbl_content", None), getattr(self, "lbl_title", None)):
                if label is not None and label.isVisible():
                    required = label.heightForWidth(label.width())
                    if required >= 0 and required != label.minimumHeight():
                        label.setMinimumHeight(required)
                        self.updateGeometry()
        finally:
            self._updating_content_height = False

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_content_height()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            QTimer.singleShot(0, self._update_content_height)

    def enterEvent(self, event) -> None:
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)

    def _on_delete_hover_enter(self, event) -> None:
        self.btn_delete.setIcon(icon("fa5s.trash", color=STATUS_ERROR))

    def _on_delete_hover_leave(self, event) -> None:
        self.btn_delete.setIcon(icon("fa5s.trash"))

    def eventFilter(self, watched, event) -> bool:
        if watched == getattr(self, "btn_delete", None):
            if event.type() == QEvent.Type.Enter:
                self._on_delete_hover_enter(event)
            elif event.type() == QEvent.Type.Leave:
                self._on_delete_hover_leave(event)
        if event.type() == QEvent.Type.Resize:
            self._update_content_height()
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if hasattr(event, "button") and event.button() == Qt.MouseButton.LeftButton:
                self.edit_requested.emit(self.entry)
                return True
        if event.type() == QEvent.Type.ContextMenu:
            pos = (
                event.globalPos()
                if hasattr(event, "globalPos")
                else (
                    event.globalPosition().toPoint()
                    if hasattr(event, "globalPosition")
                    else QCursor.pos()
                )
            )
            self._show_context_menu(pos)
            return True
        return super().eventFilter(watched, event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self._show_context_menu(event.globalPos())
        event.accept()

    def _create_context_menu(self) -> QMenu:
        menu = QMenu(self)
        self._last_context_menu = menu

        edit_action = menu.addAction(icon("fa5s.pen"), t("loot.edit", "Edit"))
        edit_action.triggered.connect(lambda: self.edit_requested.emit(self.entry))

        export_file_action = menu.addAction(
            icon("fa5s.download"), t("loot.export_file", "Export (.md)")
        )
        export_file_action.triggered.connect(
            lambda: self.export_requested.emit(self.entry.get("id", ""))
        )

        export_obsidian_action = menu.addAction(
            icon("fa5s.book-open"), t("loot.export_obsidian", "Obsidian")
        )
        export_obsidian_action.triggered.connect(
            lambda: self.obsidian_export_requested.emit(self.entry.get("id", ""))
        )

        menu.addSeparator()

        delete_action = menu.addAction(
            icon("fa5s.trash", color=STATUS_ERROR), t("loot.delete", "Delete")
        )
        delete_action.triggered.connect(lambda: self.deleted.emit(self.entry.get("id", "")))

        return menu

    def _show_context_menu(self, global_pos: QPoint) -> None:
        menu = self._create_context_menu()
        menu.exec(global_pos)

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
        show_error_dialog(
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

from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMenu,
    QWidget,
    QApplication,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from typing import Dict, Any, Optional
import pyperclip
from core.logger import get_logger
from core.i18n import t

logger = get_logger(__name__)


class SplitCaptureButton(QPushButton):
    """
    Split button that triggers a default quick action on main body click
    and opens a dropdown menu when clicking the indicator arrow.
    """

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self._menu: Optional[QMenu] = None

    def setMenu(self, menu: Optional[QMenu]) -> None:
        self._menu = menu
        super().setMenu(menu)

    def mousePressEvent(self, event) -> None:
        arrow_width = 24
        if event.position().x() >= (self.width() - arrow_width):
            if self._menu:
                self.showMenu()
        else:
            self.clicked.emit()


class HistoryCard(QFrame):
    """Visual card displaying a single clipboard history item with natural word wrapping and Loot/Note-capture."""

    copied = pyqtSignal(str)
    transfer_to_loot = pyqtSignal(dict)
    transfer_to_note = pyqtSignal(dict)
    add_to_loot_requested = transfer_to_loot
    added_to_loot = transfer_to_loot
    add_to_note_requested = transfer_to_note
    deleted = pyqtSignal(str)
    entry_deleted = deleted

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("SnippetCard")
        self.entry = entry
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header Row: Time, Target IP, Stats, Delete
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        # Time Badge
        ts = self.entry.get("timestamp", "")
        time_display = ts.split(" ")[-1] if " " in ts else ts
        lbl_time = QLabel(time_display)
        lbl_time.setTextFormat(Qt.TextFormat.PlainText)
        lbl_time.setStyleSheet(
            "background-color: rgba(56, 139, 253, 0.15); color: #79c0ff; border: 1px solid rgba(56, 139, 253, 0.3); border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;"
        )
        header_layout.addWidget(lbl_time)

        # Target IP Badge (if present)
        target_ip = self.entry.get("target_ip", "")
        if target_ip:
            lbl_target = QLabel(target_ip)
            lbl_target.setTextFormat(Qt.TextFormat.PlainText)
            lbl_target.setStyleSheet(
                "background-color: rgba(0, 229, 255, 0.12); color: #00e5ff; border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;"
            )
            header_layout.addWidget(lbl_target)

        # Stats Badge
        lines_count = self.entry.get("lines_count", 1)
        char_count = self.entry.get("char_count", 0)
        type_str = (
            "Command"
            if lines_count <= 2 and char_count < 120
            else f"{lines_count} lines ({char_count} chars)"
        )
        lbl_stats = QLabel(type_str)
        lbl_stats.setTextFormat(Qt.TextFormat.PlainText)
        lbl_stats.setStyleSheet("color: #8b949e; font-size: 10px;")
        header_layout.addWidget(lbl_stats)

        header_layout.addStretch()

        # Delete Button
        btn_delete = QPushButton("✕")
        btn_delete.setProperty("class", "DangerBtn")
        btn_delete.setToolTip(t("history.delete_tip", "Delete this history entry"))
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
        self.btn_copy.setMinimumWidth(90)
        self.btn_copy.clicked.connect(self._copy_content)
        action_col.addWidget(self.btn_copy)

        self.btn_capture = SplitCaptureButton(t("history.capture", "Erfassen ▾"), self)
        self.btn_capture.setProperty("class", "SecondaryBtn")
        self.btn_capture.setToolTip(
            t("history.capture_tip", "Klick: Als Note erfassen | Pfeil: Optionen (Note / Loot)")
        )
        self.btn_capture.setMinimumWidth(95)

        capture_menu = QMenu(self.btn_capture)
        capture_menu.setProperty("class", "SecondaryMenu")

        act_note = capture_menu.addAction(t("history.capture_as_note", "Als Note erfassen"))
        act_note.triggered.connect(self._on_capture_note)

        act_loot = capture_menu.addAction(t("history.capture_as_loot", "Als Loot erfassen..."))
        act_loot.triggered.connect(self._on_capture_loot)

        self.btn_capture.setMenu(capture_menu)
        self.btn_capture.clicked.connect(self._on_capture_note)
        self.btn_to_loot = self.btn_capture  # backwards-compatibility alias

        action_col.addWidget(self.btn_capture)

        content_row.addLayout(action_col)
        layout.addLayout(content_row)

    def _on_capture_note(self) -> None:
        """Captures entry directly as a Quick Note and shows visual feedback."""
        self.transfer_to_note.emit(self.entry)
        self._show_capture_feedback("✓ Note!")

    def _on_capture_loot(self) -> None:
        """Transfers entry to Loot via dialog and shows visual feedback."""
        self.transfer_to_loot.emit(self.entry)
        self._show_capture_feedback("✓ Loot...")

    def _show_capture_feedback(self, text: str) -> None:
        self.btn_capture.setText(text)
        self.btn_capture.setProperty("class", "CopyBtnSuccess")
        self.btn_capture.style().unpolish(self.btn_capture)
        self.btn_capture.style().polish(self.btn_capture)
        QTimer.singleShot(1200, self._reset_capture_btn)

    def _reset_capture_btn(self) -> None:
        self.btn_capture.setText(t("history.capture", "Erfassen ▾"))
        self.btn_capture.setProperty("class", "SecondaryBtn")
        self.btn_capture.style().unpolish(self.btn_capture)
        self.btn_capture.style().polish(self.btn_capture)

    def _copy_content(self) -> None:
        """Copies content back to system clipboard."""
        text_to_copy = self.entry.get("text", "").strip()
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

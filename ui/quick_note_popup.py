"""
Quick Note Popup for SpectreHUD.

Minimal frameless popup for rapid note capturing with single-key pentest phase tagging.
"""

from typing import Dict, Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QCursor, QGuiApplication, QKeyEvent

from core.loot_manager import VALID_CATEGORY_IDS
from core.i18n import t


PHASE_PILLS = [
    ("recon", "1. Recon"),
    ("access", "2. Access"),
    ("privesc", "3. PrivEsc"),
    ("postex", "4. PostEx"),
    ("scripts", "5. Scripts"),
    ("misc", "6. Misc"),
]

KEY_TO_CATEGORY: Dict[Qt.Key, str] = {
    Qt.Key.Key_1: "recon",
    Qt.Key.Key_2: "access",
    Qt.Key.Key_3: "privesc",
    Qt.Key.Key_4: "postex",
    Qt.Key.Key_5: "scripts",
    Qt.Key.Key_6: "misc",
}


class QuickNotePopup(QWidget):
    """
    Frameless, lightweight popup positioned near the mouse cursor
    for spontaneous thought capture during CTFs/engagements.
    """

    note_submitted = pyqtSignal(str, str)  # (text, category)
    cancelled = pyqtSignal()

    def __init__(
        self,
        default_category: str = "misc",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._has_been_active = False
        self.current_category = (
            default_category if default_category in VALID_CATEGORY_IDS else "misc"
        )
        self.pill_buttons: Dict[str, QPushButton] = {}
        self._init_window()
        self._init_ui()

    def _init_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(400, 170)

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(4, 4, 4, 4)

        # Card container with glass HUD styling
        self.card = QFrame(self)
        self.card.setObjectName("QuickNoteCard")
        self.card.setStyleSheet(
            """
            QFrame#QuickNoteCard {
                background-color: rgba(13, 17, 23, 0.96);
                border: 1px solid rgba(0, 229, 255, 0.45);
                border-radius: 8px;
            }
            """
        )
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(6)

        # Header Row: Title & Hint
        header_layout = QHBoxLayout()
        lbl_title = QLabel("📌 QUICK NOTE")
        lbl_title.setStyleSheet(
            "color: #00e5ff; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;"
        )
        header_layout.addWidget(lbl_title)

        header_layout.addStretch()

        lbl_hint = QLabel("Enter: Save | Esc: Cancel | 1-6: Phase")
        lbl_hint.setStyleSheet("color: #8b949e; font-size: 10px;")
        header_layout.addWidget(lbl_hint)
        card_layout.addLayout(header_layout)

        # Phase Pills Row
        pills_layout = QHBoxLayout()
        pills_layout.setSpacing(4)
        for cat_id, label in PHASE_PILLS:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, cid=cat_id: self.select_category(cid))
            self.pill_buttons[cat_id] = btn
            pills_layout.addWidget(btn)
        card_layout.addLayout(pills_layout)

        # Text Editor
        self.text_edit = QPlainTextEdit(self.card)
        self.text_edit.setPlaceholderText(
            t("quick_note.placeholder", "Schnellnotiz eingeben (Enter = Speichern, Shift+Enter = Zeilenumbruch)...")
        )
        self.text_edit.setStyleSheet(
            """
            QPlainTextEdit {
                background-color: rgba(22, 27, 34, 0.9);
                color: #e6edf3;
                border: 1px solid rgba(48, 54, 61, 0.8);
                border-radius: 4px;
                font-size: 12px;
                padding: 4px;
            }
            QPlainTextEdit:focus {
                border: 1px solid #00e5ff;
            }
            """
        )
        self.text_edit.installEventFilter(self)
        card_layout.addWidget(self.text_edit)

        outer_layout.addWidget(self.card)
        self._update_pill_styles()

    def select_category(self, category_id: str) -> None:
        """Selects the active category pill."""
        if category_id in VALID_CATEGORY_IDS:
            self.current_category = category_id
            self._update_pill_styles()

    def _update_pill_styles(self) -> None:
        active_style = (
            "background-color: rgba(0, 229, 255, 0.2); color: #00e5ff; "
            "border: 1px solid #00e5ff; border-radius: 3px; font-size: 10px; font-weight: bold; padding: 2px 5px;"
        )
        inactive_style = (
            "background-color: rgba(33, 38, 45, 0.6); color: #8b949e; "
            "border: 1px solid rgba(48, 54, 61, 0.8); border-radius: 3px; font-size: 10px; padding: 2px 5px;"
        )
        for cat_id, btn in self.pill_buttons.items():
            btn.setStyleSheet(active_style if cat_id == self.current_category else inactive_style)

    def eventFilter(self, watched, event) -> bool:
        """Intercepts Enter and Escape inside the text editor."""
        if watched is self.text_edit and event.type() == event.Type.KeyPress:
            key_event: QKeyEvent = event
            key = key_event.key()
            modifiers = key_event.modifiers()

            # Esc -> Cancel
            if key == Qt.Key.Key_Escape:
                self.reject()
                return True

            # Enter (without Shift) -> Submit
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not (modifiers & Qt.KeyboardModifier.ShiftModifier):
                    self.accept()
                    return True

            # Number keys 1-6:
            # If Alt is held OR text edit is currently empty -> switch category
            if key in KEY_TO_CATEGORY:
                if (modifiers & Qt.KeyboardModifier.AltModifier) or not self.text_edit.toPlainText().strip():
                    self.select_category(KEY_TO_CATEGORY[key])
                    return True

        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handles keys if focus is on the popup container itself."""
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
            return
        if key in KEY_TO_CATEGORY:
            self.select_category(KEY_TO_CATEGORY[key])
            return
        super().keyPressEvent(event)

    def changeEvent(self, event) -> None:
        """Dismisses popup when focus/activation is lost after having been active."""
        if event is not None and event.type() == event.Type.ActivationChange:
            if self.isActiveWindow():
                self._has_been_active = True
            elif self._has_been_active:
                self.close()
        super().changeEvent(event)

    def accept(self) -> None:
        """Submits the note if text is non-empty and closes."""
        text = self.text_edit.toPlainText().strip()
        if text:
            self.note_submitted.emit(text, self.current_category)
        self.close()

    def reject(self) -> None:
        """Closes the popup without saving."""
        self.cancelled.emit()
        self.close()

    def show_at_cursor(self, default_category: Optional[str] = None) -> None:
        """Positions the popup near the active mouse cursor clamped to screen bounds."""
        if default_category and default_category in VALID_CATEGORY_IDS:
            self.select_category(default_category)

        self.text_edit.clear()
        self._has_been_active = False

        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()

        popup_width = self.width()
        popup_height = self.height()

        target_x = cursor_pos.x() - (popup_width // 2)
        target_y = cursor_pos.y() - (popup_height // 2)

        if screen:
            geom = screen.availableGeometry()
            target_x = max(geom.left() + 10, min(target_x, geom.right() - popup_width - 10))
            target_y = max(geom.top() + 10, min(target_y, geom.bottom() - popup_height - 10))

        self.move(QPoint(target_x, target_y))
        self.show()
        self.raise_()
        self.activateWindow()
        # Give keyboard focus once on open — no repeated timer so click-outside still dismisses
        self.text_edit.setFocus(Qt.FocusReason.ActiveWindowFocusReason)


"""
Quick Note Popup for SpectreHUD.

Minimal frameless popup for rapid note capturing with single-key pentest phase tagging.
"""

from datetime import datetime
from typing import Any, Dict, Optional
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
from PyQt6.QtGui import QColor, QCursor, QGuiApplication, QKeyEvent

from core.loot import VALID_CATEGORY_IDS
from core.i18n import t
from core.logger import get_logger
from ui.styles.icons import get_theme_color
from ui.styles.theme import rgba_str

logger = get_logger("quick_note_popup")


PHASE_PILLS = [
    ("recon", "quick_note.phase_recon", "1. Recon"),
    ("access", "quick_note.phase_access", "2. Access"),
    ("privesc", "quick_note.phase_privesc", "3. PrivEsc"),
    ("postex", "quick_note.phase_postex", "4. PostEx"),
    ("scripts", "quick_note.phase_scripts", "5. Scripts"),
    ("misc", "quick_note.phase_misc", "6. Misc"),
]

KEY_TO_CATEGORY: Dict[Any, str] = {
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
        bg_col = QColor(get_theme_color("BG_DARK"))
        accent_col = QColor(get_theme_color("ACCENT_BRAND"))
        self.card.setStyleSheet(
            f"""
            QFrame#QuickNoteCard {{
                background-color: {rgba_str(bg_col, 0.96)};
                border: 1px solid {rgba_str(accent_col, 0.45)};
                border-radius: 8px;
            }}
            """
        )
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(6)

        # Header Row: Title & Hint
        header_layout = QHBoxLayout()
        lbl_title = QLabel(t("quick_note.popup_title", "QUICK NOTE"))
        lbl_title.setStyleSheet(
            f"color: {get_theme_color('ACCENT_BRAND')}; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;"
        )
        header_layout.addWidget(lbl_title)

        header_layout.addStretch()

        lbl_hint = QLabel(
            t(
                "quick_note.popup_hint",
                "Enter: Save · Shift+Enter: New line · Alt+1–6: Phase",
            )
        )
        lbl_hint.setStyleSheet(f"color: {get_theme_color('TEXT_MUTED')}; font-size: 10px;")
        header_layout.addWidget(lbl_hint)
        card_layout.addLayout(header_layout)

        # Phase Pills Row
        pills_layout = QHBoxLayout()
        pills_layout.setSpacing(4)
        for cat_id, label_key, fallback in PHASE_PILLS:
            btn = QPushButton(t(label_key, fallback))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, cid=cat_id: self.select_category(cid))
            self.pill_buttons[cat_id] = btn
            pills_layout.addWidget(btn)
        card_layout.addLayout(pills_layout)

        # Draft Recovery Banner (shown only when an unsaved fallback draft exists)
        self.recovery_banner = QFrame(self.card)
        self.recovery_banner.setObjectName("DraftRecoveryBanner")
        self.recovery_banner.setStyleSheet(
            f"""
            QFrame#DraftRecoveryBanner {{
                background-color: {get_theme_color("BG_INPUT")};
                border: 1px solid {get_theme_color("STATUS_WARNING") if get_theme_color("STATUS_WARNING") else "#d97706"};
                border-radius: 4px;
                padding: 1px 4px;
            }}
            """
        )
        rec_layout = QHBoxLayout(self.recovery_banner)
        rec_layout.setContentsMargins(4, 2, 4, 2)
        rec_layout.setSpacing(6)

        self.lbl_recovery = QLabel(self.recovery_banner)
        self.lbl_recovery.setStyleSheet(f"color: {get_theme_color('TEXT_PRIMARY')}; font-size: 10px;")
        rec_layout.addWidget(self.lbl_recovery, stretch=1)

        self.btn_restore_draft = QPushButton(t("quick_note.restore_yes", "Ja"), self.recovery_banner)
        self.btn_restore_draft.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_restore_draft.setStyleSheet(
            f"background-color: {get_theme_color('CYAN_A20')}; color: {get_theme_color('ACCENT_BRAND')}; "
            f"border: 1px solid {get_theme_color('ACCENT_BRAND')}; border-radius: 3px; font-size: 10px; font-weight: bold; padding: 1px 6px;"
        )
        self.btn_restore_draft.clicked.connect(self._restore_fallback_draft)
        rec_layout.addWidget(self.btn_restore_draft)

        self.btn_discard_draft = QPushButton(t("quick_note.restore_no", "Verwerfen"), self.recovery_banner)
        self.btn_discard_draft.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_discard_draft.setStyleSheet(
            f"background-color: {get_theme_color('CONTROL_A70')}; color: {get_theme_color('TEXT_MUTED')}; "
            f"border: 1px solid {get_theme_color('BORDER_A80')}; border-radius: 3px; font-size: 10px; padding: 1px 6px;"
        )
        self.btn_discard_draft.clicked.connect(self._discard_fallback_draft)
        rec_layout.addWidget(self.btn_discard_draft)

        self.recovery_banner.hide()
        card_layout.addWidget(self.recovery_banner)

        # Text Editor

        self.text_edit = QPlainTextEdit(self.card)
        self.text_edit.setPlaceholderText(
            t(
                "quick_note.placeholder",
                "Schnellnotiz eingeben (Enter = Speichern, Shift+Enter = Zeilenumbruch)...",
            )
        )
        self.text_edit.setStyleSheet(
            f"""
            QPlainTextEdit {{
                background-color: {get_theme_color("BG_INPUT")};
                color: {get_theme_color("TEXT_PRIMARY")};
                border: 1px solid {get_theme_color("BORDER_A80")};
                border-radius: 4px;
                font-size: 12px;
                padding: 4px;
            }}
            QPlainTextEdit:focus {{
                border: 1px solid {get_theme_color("ACCENT_BRAND")};
            }}
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
            f"background-color: {get_theme_color('CYAN_A20')}; color: {get_theme_color('ACCENT_BRAND')}; "
            f"border: 1px solid {get_theme_color('ACCENT_BRAND')}; border-radius: 3px; font-size: 10px; font-weight: bold; padding: 2px 5px;"
        )
        inactive_style = (
            f"background-color: {get_theme_color('CONTROL_A70')}; color: {get_theme_color('TEXT_MUTED')}; "
            f"border: 1px solid {get_theme_color('BORDER_A80')}; border-radius: 3px; font-size: 10px; padding: 2px 5px;"
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
                if (
                    modifiers & Qt.KeyboardModifier.AltModifier
                ) or not self.text_edit.toPlainText().strip():
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

    _cached_draft: Optional[Dict[str, Any]] = None

    def changeEvent(self, event) -> None:
        """Dismisses popup when focus/activation is lost after having been active, auto-saving non-empty text."""
        if event is not None and event.type() == event.Type.ActivationChange:
            if self.isActiveWindow():
                self._has_been_active = True
            elif self._has_been_active:
                text = self.text_edit.toPlainText().strip()
                if text:
                    self._auto_save_or_fallback(text)
                self.close()
        super().changeEvent(event)

    def _emit_note_submitted(self, text: str, category: str) -> None:
        """Emits the note_submitted signal."""
        self.note_submitted.emit(text, category)

    def _auto_save_or_fallback(self, text: str) -> None:
        """Saves note text via note_submitted or stores in fallback cache on failure."""
        cat = self.current_category
        try:
            self._emit_note_submitted(text, cat)
            self.text_edit.clear()
            QuickNotePopup._cached_draft = None
        except Exception as exc:
            logger.warning(f"Failed to auto-save quick note draft: {exc}")
            QuickNotePopup._cached_draft = {
                "text": text,
                "category": cat,
                "time": datetime.now().strftime("%H:%M:%S"),
            }


    def _restore_fallback_draft(self) -> None:
        draft = QuickNotePopup._cached_draft
        if draft:
            self.text_edit.setPlainText(draft.get("text", ""))
            self.select_category(draft.get("category", self.current_category))
            QuickNotePopup._cached_draft = None
        self.recovery_banner.hide()
        self.setFixedSize(400, 170)
        self.text_edit.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def _discard_fallback_draft(self) -> None:
        QuickNotePopup._cached_draft = None
        self.recovery_banner.hide()
        self.setFixedSize(400, 170)
        self.text_edit.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def accept(self) -> None:
        """Submits the note if text is non-empty and closes."""
        text = self.text_edit.toPlainText().strip()
        if text:
            self._auto_save_or_fallback(text)
        self.close()

    def reject(self) -> None:
        """Closes the popup without saving."""
        self.text_edit.clear()
        self.cancelled.emit()
        self.close()

    def show_at_cursor(self, default_category: Optional[str] = None) -> None:
        """Positions the popup near the active mouse cursor clamped to screen bounds."""
        if default_category and default_category in VALID_CATEGORY_IDS:
            self.select_category(default_category)

        self.text_edit.clear()
        self._has_been_active = False

        if QuickNotePopup._cached_draft:
            draft_time = QuickNotePopup._cached_draft.get("time", "")
            self.lbl_recovery.setText(
                t(
                    "quick_note.draft_prompt",
                    "Unvollständiger Entwurf von {time} wiederherstellen?",
                    time=draft_time,
                )
            )
            self.recovery_banner.show()
            self.setFixedSize(400, 205)
        else:
            self.recovery_banner.hide()
            self.setFixedSize(400, 170)

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


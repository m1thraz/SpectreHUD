"""
Session Recap Banner for SpectreHUD.

Slim, non-modal HUD strip displayed upon reactivation after prolonged inactivity.
Shows active phase, last logged action, and badge counters to restore focus without distraction.
"""

from typing import Any, Dict, Optional
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor

from core.i18n import t
from ui.styles.icons import get_theme_color
from ui.styles.theme import rgba_str


class SessionRecapBanner(QFrame):
    """
    Lightweight, non-distracting banner providing instant context and resume when returning to SpectreHUD.
    """

    resume_clicked = pyqtSignal(dict)

    def __init__(self, parent: Optional[QWidget] = None, auto_dismiss_ms: int = 25000):
        super().__init__(parent)
        self.setObjectName("SessionRecapBanner")
        self.auto_dismiss_ms = auto_dismiss_ms
        self._current_info: Dict[str, Any] = {}
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.hide)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setFixedHeight(28)
        bg = QColor(get_theme_color("BG_SURFACE"))
        border = QColor(get_theme_color("ACCENT_BRAND"))
        self.setStyleSheet(
            f"""
            QFrame#SessionRecapBanner {{
                background-color: {rgba_str(bg, 0.95)};
                border-bottom: 1px solid {rgba_str(border, 0.4)};
                border-top: 1px solid {rgba_str(border, 0.2)};
            }}
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 8, 2)
        layout.setSpacing(8)

        self.lbl_tag = QLabel(t("recap.tag", "RECAP //"))
        self.lbl_tag.setStyleSheet(
            f"color: {get_theme_color('ACCENT_BRAND')}; font-size: 10px; font-weight: 800; letter-spacing: 0.5px;"
        )
        layout.addWidget(self.lbl_tag)

        self.lbl_phase = QLabel("")
        self.lbl_phase.setStyleSheet(
            f"color: {get_theme_color('TEXT_PRIMARY')}; font-size: 11px; font-weight: 600;"
        )
        layout.addWidget(self.lbl_phase)

        self.lbl_sep_target = QLabel("·")
        self.lbl_sep_target.setStyleSheet(f"color: {get_theme_color('TEXT_MUTED')}; font-size: 11px;")
        layout.addWidget(self.lbl_sep_target)

        self.lbl_target = QLabel("")
        self.lbl_target.setStyleSheet(
            f"color: {get_theme_color('TEXT_PRIMARY')}; font-size: 11px; font-weight: 600;"
        )
        layout.addWidget(self.lbl_target)

        self.lbl_sep1 = QLabel("·")
        self.lbl_sep1.setStyleSheet(f"color: {get_theme_color('TEXT_MUTED')}; font-size: 11px;")
        layout.addWidget(self.lbl_sep1)

        self.lbl_last_action = QLabel("")
        self.lbl_last_action.setStyleSheet(
            f"color: {get_theme_color('TEXT_SECONDARY')}; font-size: 11px;"
        )
        layout.addWidget(self.lbl_last_action)

        self.lbl_sep2 = QLabel("·")
        self.lbl_sep2.setStyleSheet(f"color: {get_theme_color('TEXT_MUTED')}; font-size: 11px;")
        layout.addWidget(self.lbl_sep2)

        self.lbl_badges = QLabel("")
        self.lbl_badges.setStyleSheet(
            f"color: {get_theme_color('TEXT_MUTED')}; font-size: 11px;"
        )
        layout.addWidget(self.lbl_badges)

        layout.addStretch()

        self.btn_resume = QPushButton(t("recap.resume", "Resume"))
        self.btn_resume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_resume.setFixedHeight(20)
        self.btn_resume.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {get_theme_color("CYAN_A15")};
                color: {get_theme_color("ACCENT_BRAND")};
                border: 1px solid {get_theme_color("BORDER_GLOW")};
                border-radius: 3px;
                font-size: 10px;
                font-weight: 700;
                padding: 1px 8px;
            }}
            QPushButton:hover {{
                background-color: {get_theme_color("CYAN_A25", get_theme_color("CYAN_A15"))};
                color: {get_theme_color("TEXT_PRIMARY")};
            }}
            """
        )
        self.btn_resume.clicked.connect(self._on_resume_clicked)
        layout.addWidget(self.btn_resume)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(18, 18)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {get_theme_color('TEXT_MUTED')};
                border: none;
                font-size: 11px;
                padding: 0;
            }}
            QPushButton:hover {{
                color: {get_theme_color('TEXT_PRIMARY')};
            }}
            """
        )
        self.btn_close.clicked.connect(self.hide)
        layout.addWidget(self.btn_close)

    def _on_resume_clicked(self) -> None:
        self.hide()
        self.resume_clicked.emit(self._current_info.get("resume_context") or {})

    def show_recap(self, info: Dict[str, Any]) -> None:
        """Populates fields and displays the recap banner, resetting the auto-dismiss timer."""
        self._current_info = dict(info)
        phase_name = info.get("phase_name") or t("recap.phase_none", "Keine Phase")
        self.lbl_phase.setText(f"Phase: {phase_name}")

        target = info.get("target")
        if target:
            self.lbl_target.setText(f"Target: {target}")
            self.lbl_sep_target.show()
            self.lbl_target.show()
        else:
            self.lbl_sep_target.hide()
            self.lbl_target.hide()

        last_action = info.get("last_action")
        if last_action:
            self.lbl_last_action.setText(last_action)
            self.lbl_sep1.show()
            self.lbl_last_action.show()
        else:
            self.lbl_sep1.hide()
            self.lbl_last_action.hide()

        open_notes = info.get("open_notes", 0)
        unsynced_loot = info.get("unsynced_loot", 0)
        parts = []
        if open_notes > 0:
            parts.append(t("recap.open_notes", "{count} offene Notes", count=open_notes))
        if unsynced_loot > 0:
            parts.append(t("recap.unsynced_loot", "{count} ungesynctes Loot", count=unsynced_loot))

        if parts:
            self.lbl_badges.setText(" · ".join(parts))
            self.lbl_sep2.show()
            self.lbl_badges.show()
        else:
            self.lbl_sep2.hide()
            self.lbl_badges.hide()

        self.show()
        self._dismiss_timer.start(self.auto_dismiss_ms)

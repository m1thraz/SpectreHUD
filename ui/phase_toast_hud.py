"""
Phase Toast HUD for SpectreHUD.

A transient, frameless, non-focus-stealing HUD overlay that displays
the active pentest phase on the screen where the mouse cursor resides.
"""

from typing import Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor, QGuiApplication

from core.phases import get_phase, Phase
from core.i18n import t


class PhaseToastHUD(QWidget):
    """
    Frameless, non-activating HUD overlay toast for pentest phase confirmation.
    Displayed in the top-third of the active monitor under the mouse cursor.
    """

    DISPLAY_DURATION_MS = 1200

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_window()
        self._init_ui()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def _init_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFixedSize(360, 68)

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(4, 4, 4, 4)

        self.card = QFrame(self)
        self.card.setObjectName("PhaseHUDCard")
        self.card.setStyleSheet(
            """
            QFrame#PhaseHUDCard {
                background-color: rgba(13, 17, 23, 0.94);
                border: 1px solid rgba(0, 229, 255, 0.65);
                border-radius: 8px;
            }
            """
        )
        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(14, 8, 14, 8)
        card_layout.setSpacing(12)

        # Left: Phase badge
        self.badge = QLabel("RECON", self.card)
        self.badge.setObjectName("PhaseBadge")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setStyleSheet(
            """
            QLabel#PhaseBadge {
                background-color: rgba(0, 229, 255, 0.15);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.4);
                border-radius: 4px;
                font-size: 11px;
                font-weight: 800;
                padding: 4px 8px;
                min-width: 58px;
            }
            """
        )
        card_layout.addWidget(self.badge)

        # Right: Info column (Title + Phase Name)
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_category = QLabel("ACTIVE PENTEST PHASE", self.card)
        self.lbl_category.setStyleSheet(
            "color: #8b949e; font-size: 9px; font-weight: 700; letter-spacing: 0.8px;"
        )
        info_layout.addWidget(self.lbl_category)

        self.lbl_phase_name = QLabel("Reconnaissance & Enumeration", self.card)
        self.lbl_phase_name.setStyleSheet(
            "color: #f0f6fc; font-size: 13px; font-weight: 700;"
        )
        info_layout.addWidget(self.lbl_phase_name)

        card_layout.addLayout(info_layout)
        outer_layout.addWidget(self.card)

    def show_phase(self, phase_or_key: Optional[str]) -> None:
        """
        Updates HUD content to the given phase and displays it centered
        in the upper third of the monitor containing the mouse cursor.
        """
        if not phase_or_key:
            self.badge.setText("NONE")
            self.badge.setStyleSheet(
                """
                QLabel#PhaseBadge {
                    background-color: rgba(139, 148, 158, 0.15);
                    color: #8b949e;
                    border: 1px solid rgba(139, 148, 158, 0.4);
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 800;
                    padding: 4px 8px;
                    min-width: 58px;
                }
                """
            )
            self.lbl_phase_name.setText(t("phases.unassigned", default="Unassigned"))
        else:
            phase: Phase = get_phase(phase_or_key)
            self.badge.setText(phase.short)
            self.badge.setStyleSheet(
                """
                QLabel#PhaseBadge {
                    background-color: rgba(0, 229, 255, 0.15);
                    color: #00e5ff;
                    border: 1px solid rgba(0, 229, 255, 0.4);
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 800;
                    padding: 4px 8px;
                    min-width: 58px;
                }
                """
            )
            self.lbl_phase_name.setText(f"{phase.order}. {phase.long}")

        self._reposition_to_cursor_screen()
        self.show()
        self._timer.start(self.DISPLAY_DURATION_MS)

    def _reposition_to_cursor_screen(self) -> None:
        """Calculates position in top third of the monitor containing the mouse cursor."""
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos)
        if not screen:
            screen = QGuiApplication.primaryScreen()

        if screen:
            geom = screen.geometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + int(geom.height() * 0.14)
            self.move(x, y)

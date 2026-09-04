"""
Quick IP Popup for SpectreHUD.

Lightweight frameless popup for rapid inspection, clipboard copying, and
live modification of Target IP and LHOST with auto-detection.
"""

import sys
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QEvent, QTimer
from PyQt6.QtGui import QCursor, QGuiApplication, QKeyEvent

from core.i18n import t
from core.net_detector import NetDetector
from ui.copyable_line_edit import CopyableLineEdit


class QuickIpPopup(QWidget):
    """
    Frameless, lightweight popup positioned near the mouse cursor
    for inspecting and updating Target and Attacker (LHOST) IPs live.
    """

    target_changed = pyqtSignal(str)
    attacker_changed = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(
        self,
        target_ip: str = "",
        attacker_ip: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._has_been_active = False
        self._init_window()
        self._init_ui()
        self.set_values(target_ip, attacker_ip)

    def _init_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(360, 125)

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(4, 4, 4, 4)

        # Card container with glass HUD styling
        self.card = QFrame(self)
        self.card.setObjectName("QuickIpCard")
        self.card.setStyleSheet(
            """
            QFrame#QuickIpCard {
                background-color: rgba(13, 17, 23, 0.96);
                border: 1px solid rgba(0, 229, 255, 0.45);
                border-radius: 8px;
            }
            """
        )
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 8, 12, 10)
        card_layout.setSpacing(8)

        # 1. Header Row: Title & Hint
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        lbl_title = QLabel("⚡ QUICK-IP")
        lbl_title.setStyleSheet(
            "color: #00e5ff; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;"
        )
        header_layout.addWidget(lbl_title)

        header_layout.addStretch()

        lbl_hint = QLabel("Esc: Close")
        lbl_hint.setStyleSheet("color: #8b949e; font-size: 10px;")
        header_layout.addWidget(lbl_hint)
        card_layout.addLayout(header_layout)

        # 2. Target IP Row
        row_target = QHBoxLayout()
        row_target.setContentsMargins(0, 0, 0, 0)
        row_target.setSpacing(8)

        lbl_target = QLabel(t("varbar.target", "Target:"))
        lbl_target.setProperty("class", "VarTagLabel")
        lbl_target.setFixedWidth(55)
        row_target.addWidget(lbl_target)

        self.txt_target = CopyableLineEdit("")
        self.txt_target.setProperty("class", "CompactVarInput")
        self.txt_target.setPlaceholderText("10.10.10.x")
        self.txt_target.textChanged.connect(self.target_changed.emit)
        self.txt_target.installEventFilter(self)
        row_target.addWidget(self.txt_target, stretch=1)
        card_layout.addLayout(row_target)

        # 3. Attacker IP (LHOST) Row + Auto Button
        row_attacker = QHBoxLayout()
        row_attacker.setContentsMargins(0, 0, 0, 0)
        row_attacker.setSpacing(8)

        lbl_attacker = QLabel(t("varbar.attacker", "LHOST:"))
        lbl_attacker.setProperty("class", "VarTagLabel")
        lbl_attacker.setFixedWidth(55)
        row_attacker.addWidget(lbl_attacker)

        self.txt_attacker = CopyableLineEdit("")
        self.txt_attacker.setProperty("class", "CompactVarInput")
        self.txt_attacker.setPlaceholderText("10.10.14.x")
        self.txt_attacker.textChanged.connect(self.attacker_changed.emit)
        self.txt_attacker.installEventFilter(self)
        row_attacker.addWidget(self.txt_attacker, stretch=1)

        self.btn_auto = QPushButton(t("varbar.auto", "Auto"))
        self.btn_auto.setProperty("class", "AutoDetectBtn")
        self.btn_auto.setToolTip(t("varbar.auto_tip", "Auto-Erkennung für tun0 / VPN / lokale IP"))
        self.btn_auto.clicked.connect(self.auto_detect_ip)
        row_attacker.addWidget(self.btn_auto)

        card_layout.addLayout(row_attacker)
        outer_layout.addWidget(self.card)

    def set_values(self, target_ip: str, attacker_ip: str) -> None:
        """Sets both input fields without emitting changed signals."""
        self.txt_target.blockSignals(True)
        self.txt_attacker.blockSignals(True)
        self.txt_target.setText(target_ip)
        self.txt_attacker.setText(attacker_ip)
        self.txt_target.blockSignals(False)
        self.txt_attacker.blockSignals(False)

    def auto_detect_ip(self) -> None:
        """Detects active attacker IP and populates LHOST live."""
        detected = NetDetector.detect_attacker_ip()
        if detected:
            self.txt_attacker.setText(detected)
            self.btn_auto.setText("✓ " + detected)
            QTimer.singleShot(2000, lambda: self.btn_auto.setText(t("varbar.auto", "Auto")))
        else:
            self.btn_auto.setText(t("varbar.no_ip", "Keine IP"))
            QTimer.singleShot(2000, lambda: self.btn_auto.setText(t("varbar.auto", "Auto")))

    def eventFilter(self, watched, event: QEvent) -> bool:
        """Intercepts Esc key in line edits to close popup immediately."""
        if event.type() == QEvent.Type.KeyPress:
            key_event = event
            if isinstance(key_event, QKeyEvent) and key_event.key() == Qt.Key.Key_Escape:
                self.close()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handles keypresses on the popup frame."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event: Optional[QEvent]) -> None:
        """Dismisses popup when focus/activation is lost after having been active."""
        if event is not None and event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                self._has_been_active = True
            elif self._has_been_active:
                self.close()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        """Emits closed signal upon dismissal."""
        self.closed.emit()
        super().closeEvent(event)

    def _force_focus_target(self) -> None:
        """Ensures the popup and its target IP input receive active keyboard focus."""
        if sys.platform == "win32":
            try:
                import ctypes

                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                hwnd = int(self.winId())
                fg = user32.GetForegroundWindow()
                if fg != hwnd:
                    fore_thread = user32.GetWindowThreadProcessId(fg, None)
                    app_thread = kernel32.GetCurrentThreadId()
                    if fore_thread != app_thread and fore_thread != 0:
                        user32.AttachThreadInput(fore_thread, app_thread, True)
                        user32.BringWindowToTop(hwnd)
                        user32.SetForegroundWindow(hwnd)
                        user32.AttachThreadInput(fore_thread, app_thread, False)
                    else:
                        user32.BringWindowToTop(hwnd)
                        user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

        self.raise_()
        self.activateWindow()
        self.txt_target.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.txt_target.selectAll()

    def show_at_cursor(
        self,
        target_ip: Optional[str] = None,
        attacker_ip: Optional[str] = None,
    ) -> None:
        """Positions the popup near the active mouse cursor clamped to screen bounds."""
        if target_ip is not None and attacker_ip is not None:
            self.set_values(target_ip, attacker_ip)

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
        self.setWindowState(
            self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive
        )
        self.raise_()
        self.activateWindow()

        # Give keyboard focus once on open — single queued call so Qt finishes
        # painting before focus is set; no repeated timer so click-outside still dismisses
        self._force_focus_target()
        QTimer.singleShot(0, self._force_focus_target)


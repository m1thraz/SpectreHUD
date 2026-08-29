"""Tests for the recording-state system tray icon."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication

from main import create_tray_icon_pixmap, handle_tray_quit


app = QApplication.instance() or QApplication(sys.argv)


def test_tray_icon_keeps_logo_when_paused_and_tints_it_red_when_recording():
    """The active state changes only the logo colour, not its shape."""
    logo = QPixmap(32, 32)
    logo.fill(QColor("#00e5ff"))
    icon = QIcon(logo)

    paused = create_tray_icon_pixmap(is_recording=False, app_icon=icon)
    recording = create_tray_icon_pixmap(is_recording=True, app_icon=icon)

    assert paused.toImage().pixelColor(16, 16) == QColor("#00e5ff")
    assert recording.toImage().pixelColor(16, 16) == QColor("#f85149")


def test_tray_quit_ignores_qaction_checked_argument():
    class Window:
        def __init__(self):
            self.arguments = []

        def request_quit(self, quit_app=True):
            self.arguments.append(quit_app)
            return True

    window = Window()
    assert handle_tray_quit(window, False) is True
    assert window.arguments == [True]

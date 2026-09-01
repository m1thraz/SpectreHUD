"""Tests for the recording-state system tray icon."""

import os
import sys
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QIcon, QPixmap
import main
from main import (
    RESTART_EXIT_CODE,
    create_tray_icon_pixmap,
    handle_tray_quit,
    request_application_restart,
)


def test_tray_icon_keeps_logo_when_paused_and_tints_it_red_when_recording(qapp):
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


def test_restart_uses_transactional_quit_before_exiting_event_loop():
    lifecycle = []

    class Window:
        def request_quit(self, quit_app=True):
            lifecycle.append(("quit", quit_app))
            return True

    class App:
        def exit(self, code):
            lifecycle.append(("exit", code))

    assert request_application_restart(Window(), App()) is True
    assert lifecycle == [("quit", False), ("exit", RESTART_EXIT_CODE)]


def test_restart_is_cancelled_when_transactional_quit_is_rejected():
    class Window:
        @staticmethod
        def request_quit(quit_app=True):
            return False

    app = type(
        "App", (), {"exit": lambda self, code: (_ for _ in ()).throw(AssertionError(code))}
    )()

    assert request_application_restart(Window(), app) is False


def test_replacement_source_process_relaunches_main_script():
    with patch.object(main.QProcess, "startDetached", return_value=(True, 1234)) as start:
        with patch.object(sys, "argv", ["main.py"]):
            assert main._start_replacement_process() is True

    program, arguments, working_directory = start.call_args.args
    assert program == sys.executable
    assert arguments == [str(main.Path(main.__file__).resolve())]
    assert working_directory == str(main.Path(main.__file__).resolve().parent)

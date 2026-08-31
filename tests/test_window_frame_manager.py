"""Tests for frameless window gestures."""

import os
import sys
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QWidget

from PyQt6 import sip

from ui.controllers.window_frame_manager import WindowFrameManager


app = QApplication.instance() or QApplication(sys.argv)


class GestureWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(400, 300)
        self.fullscreen_toggles = 0

        self.background = QFrame(self)
        self.background.setGeometry(30, 30, 340, 240)
        self.label = QLabel("Visible text", self.background)
        self.label.move(20, 20)
        self.button = QPushButton("Action", self.background)
        self.button.move(20, 70)

    def toggle_fullscreen(self):
        self.fullscreen_toggles += 1


def test_double_click_toggles_only_on_empty_background():
    window = GestureWindow()
    manager = WindowFrameManager(window, Mock())

    assert manager._process_mouse_double_click(QPoint(250, 200), Qt.MouseButton.LeftButton)
    assert window.fullscreen_toggles == 1

    label_point = window.label.mapTo(window, QPoint(2, 2))
    assert not manager._process_mouse_double_click(label_point, Qt.MouseButton.LeftButton)
    button_point = window.button.mapTo(window, QPoint(2, 2))
    assert not manager._process_mouse_double_click(button_point, Qt.MouseButton.LeftButton)
    assert not manager._process_mouse_double_click(QPoint(2, 2), Qt.MouseButton.LeftButton)
    assert window.fullscreen_toggles == 1


def test_event_filter_survives_deleted_window():
    """The theme-restart teardown deletes the MainWindow while this filter is
    still installed; late events must not raise RuntimeError."""
    window = GestureWindow()
    watched = QWidget()
    manager = WindowFrameManager(window, Mock())
    watched.installEventFilter(manager)

    sip.delete(window)
    assert not manager.eventFilter(watched, QEvent(QEvent.Type.MouseMove))

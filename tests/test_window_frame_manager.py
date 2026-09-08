"""Tests for frameless window gestures."""

import os
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QWidget

from PyQt6 import sip

from ui.controllers.window_frame_manager import WindowFrameManager


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


def test_double_click_toggles_only_on_empty_background(qapp):
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


def test_event_filter_survives_deleted_window(qapp):
    """The theme-restart teardown deletes the MainWindow while this filter is
    still installed; late events must not raise RuntimeError."""
    window = GestureWindow()
    watched = QWidget()
    manager = WindowFrameManager(window, Mock())
    watched.installEventFilter(manager)

    sip.delete(window)
    assert not manager.eventFilter(watched, QEvent(QEvent.Type.MouseMove))


def test_resize_edge_rejects_positions_outside_window(qapp):
    window = GestureWindow()
    manager = WindowFrameManager(window, Mock())

    assert manager.get_resize_edge(QPoint(-1, 150)) == ""
    assert manager.get_resize_edge(QPoint(200, -1)) == ""
    assert manager.get_resize_edge(QPoint(400, 150)) == ""
    assert manager.get_resize_edge(QPoint(200, 300)) == ""

    window.deleteLater()


def test_interactive_control_wins_over_overlapping_resize_zone(qapp):
    window = GestureWindow()
    edge_button = QPushButton("Tab", window)
    edge_button.setGeometry(80, 4, 80, 28)
    manager = WindowFrameManager(window, Mock())
    button_point = edge_button.mapTo(window, QPoint(20, 4))

    assert manager.get_resize_edge(button_point) == "top"
    assert manager._resize_edge_at(button_point) == ""
    assert not manager._process_mouse_press(
        window.mapToGlobal(button_point), button_point, Qt.MouseButton.LeftButton
    )
    assert not manager._is_resizing

    window.deleteLater()


def test_entering_child_resets_stale_resize_cursor(qapp):
    window = GestureWindow()
    window.show()
    manager = WindowFrameManager(window, Mock())
    window.setCursor(Qt.CursorShape.SizeHorCursor)
    center = window.mapToGlobal(QPoint(200, 150))

    with patch("ui.controllers.window_frame_manager.QCursor.pos", return_value=center):
        manager.eventFilter(window.background, QEvent(QEvent.Type.Enter))

    assert window.cursor().shape() == Qt.CursorShape.ArrowCursor
    window.close()
    window.deleteLater()


def test_entering_edge_child_keeps_resize_cursor(qapp):
    window = GestureWindow()
    window.show()
    manager = WindowFrameManager(window, Mock())
    edge = window.mapToGlobal(QPoint(2, 150))

    with patch("ui.controllers.window_frame_manager.QCursor.pos", return_value=edge):
        manager.eventFilter(window.background, QEvent(QEvent.Type.Enter))

    assert window.cursor().shape() == Qt.CursorShape.SizeHorCursor
    window.close()
    window.deleteLater()

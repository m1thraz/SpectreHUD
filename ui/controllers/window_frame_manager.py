from typing import Optional, List
from PyQt6.QtCore import QObject, QPoint, QRect, QEvent, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QWidget, QLabel, QAbstractButton, QLineEdit, QTextEdit, 
    QPlainTextEdit, QComboBox, QScrollBar, QAbstractSlider, QMenu, QSizeGrip
)
from core.config import ConfigManager

RESIZE_MARGIN = 20
CORNER_MARGIN = 32

def is_interactive_widget(widget: Optional[QWidget], top_window: Optional[QWidget] = None) -> bool:
    """Checks if a widget or its parents are interactive controls (buttons, inputs, sliders, grips)."""
    if widget is None:
        return False
    curr = widget
    while curr is not None and curr != top_window:
        if isinstance(curr, (QAbstractButton, QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QScrollBar, QAbstractSlider, QMenu, QSizeGrip)):
            return True
        if isinstance(curr, QLabel) and curr.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse:
            return True
        curr = curr.parentWidget()
    return False

class WindowFrameManager(QObject):
    """Handles frameless window drag-to-move, 8-zone edge resizing, and cursor adaptation."""

    def __init__(self, window: QWidget, config_manager: ConfigManager):
        super().__init__(window)
        self.window = window
        self.config = config_manager

        self._is_resizing = False
        self._resize_edge = ""
        self._resize_start_pos = QPoint()
        self._resize_start_geo = QRect()
        self._is_moving = False
        self._drag_pos = QPoint()

    def install_on(self, widgets: List[QWidget]) -> None:
        for w in widgets:
            if w is not None:
                w.installEventFilter(self)

    def get_resize_edge(self, pos: QPoint) -> str:
        """Determines if the mouse position is on an outer resize border/corner with generous grab zones."""
        w, h = self.window.width(), self.window.height()
        x, y = pos.x(), pos.y()
        margin = RESIZE_MARGIN
        corner = CORNER_MARGIN

        # Corners take priority with a larger radius
        if x <= corner and y <= corner:
            return "top_left"
        if x >= w - corner and y <= corner:
            return "top_right"
        if x <= corner and y >= h - corner:
            return "bottom_left"
        if x >= w - corner and y >= h - corner:
            return "bottom_right"

        # Edges
        if x <= margin:
            return "left"
        if x >= w - margin:
            return "right"
        if y <= margin:
            return "top"
        if y >= h - margin:
            return "bottom"
        return ""

    def update_cursor_for_edge(self, edge: str) -> None:
        if edge in ("top_left", "bottom_right"):
            self.window.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in ("top_right", "bottom_left"):
            self.window.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edge in ("left", "right"):
            self.window.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in ("top", "bottom"):
            self.window.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.window.unsetCursor()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if not self.window.isVisible():
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.MouseMove:
            if hasattr(event, "globalPosition"):
                global_pt = event.globalPosition().toPoint()

                if self._is_resizing:
                    delta = global_pt - self._resize_start_pos
                    geo = QRect(self._resize_start_geo)
                    min_w = self.window.minimumWidth()
                    min_h = self.window.minimumHeight()

                    if "right" in self._resize_edge:
                        new_w = max(min_w, self._resize_start_geo.width() + delta.x())
                        geo.setWidth(new_w)
                    elif "left" in self._resize_edge:
                        new_w = max(min_w, self._resize_start_geo.width() - delta.x())
                        geo.setLeft(self._resize_start_geo.right() - new_w)

                    if "bottom" in self._resize_edge:
                        new_h = max(min_h, self._resize_start_geo.height() + delta.y())
                        geo.setHeight(new_h)
                    elif "top" in self._resize_edge:
                        new_h = max(min_h, self._resize_start_geo.height() - delta.y())
                        geo.setTop(self._resize_start_geo.bottom() - new_h)

                    self.window.setGeometry(geo)
                    return True

                if self._is_moving and not self._drag_pos.isNull():
                    self.window.move(global_pt - self._drag_pos)
                    return True

                local_pt = self.window.mapFromGlobal(global_pt)
                edge = self.get_resize_edge(local_pt)
                self.update_cursor_for_edge(edge)

        elif event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if hasattr(event, "globalPosition"):
                global_pt = event.globalPosition().toPoint()
                local_pt = self.window.mapFromGlobal(global_pt)
                edge = self.get_resize_edge(local_pt)

                if edge:
                    self._is_resizing = True
                    self._resize_edge = edge
                    self._resize_start_pos = global_pt
                    self._resize_start_geo = self.window.geometry()
                    return True

                clicked_widget = self.window.childAt(local_pt)
                if not is_interactive_widget(clicked_widget, self.window):
                    self._is_moving = True
                    self._drag_pos = global_pt - self.window.frameGeometry().topLeft()
                    return True

        elif event.type() == QEvent.Type.MouseButtonRelease:
            if self._is_resizing:
                self._is_resizing = False
                self._resize_edge = ""
                self.window.unsetCursor()
                self.config.set("window_width", self.window.width())
                self.config.set("window_height", self.window.height())
                return True
            elif self._is_moving:
                self._is_moving = False
                self._drag_pos = QPoint()
                return True

        return super().eventFilter(watched, event)

    def handle_mouse_press(self, event: QMouseEvent) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self.get_resize_edge(event.pos())
            if edge:
                self._is_resizing = True
                self._resize_edge = edge
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geo = self.window.geometry()
                event.accept()
                return True

            clicked_widget = self.window.childAt(event.pos())
            if not is_interactive_widget(clicked_widget, self.window):
                self._is_moving = True
                self._drag_pos = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
                event.accept()
                return True
        return False

    def handle_mouse_move(self, event: QMouseEvent) -> bool:
        if self._is_resizing:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geo = QRect(self._resize_start_geo)
            min_w = self.window.minimumWidth()
            min_h = self.window.minimumHeight()

            if "right" in self._resize_edge:
                new_w = max(min_w, self._resize_start_geo.width() + delta.x())
                geo.setWidth(new_w)
            elif "left" in self._resize_edge:
                new_w = max(min_w, self._resize_start_geo.width() - delta.x())
                geo.setLeft(self._resize_start_geo.right() - new_w)

            if "bottom" in self._resize_edge:
                new_h = max(min_h, self._resize_start_geo.height() + delta.y())
                geo.setHeight(new_h)
            elif "top" in self._resize_edge:
                new_h = max(min_h, self._resize_start_geo.height() - delta.y())
                geo.setTop(self._resize_start_geo.bottom() - new_h)

            self.window.setGeometry(geo)
            event.accept()
            return True

        if self._is_moving and not self._drag_pos.isNull():
            self.window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return True

        edge = self.get_resize_edge(event.pos())
        self.update_cursor_for_edge(edge)
        return False

    def handle_mouse_release(self, event: QMouseEvent) -> bool:
        if self._is_resizing:
            self._is_resizing = False
            self._resize_edge = ""
            self.window.unsetCursor()
            self.config.set("window_width", self.window.width())
            self.config.set("window_height", self.window.height())
            event.accept()
            return True
        elif self._is_moving:
            self._is_moving = False
            self._drag_pos = QPoint()
            event.accept()
            return True
        return False

    def handle_leave(self, event: QEvent) -> None:
        if not self._is_resizing:
            self.window.unsetCursor()

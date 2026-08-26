from typing import Optional
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QFont, QGuiApplication, QKeyEvent, QMouseEvent
from core.display_geometry import VirtualDesktopBoundingBox

class SnippingOverlay(QWidget):
    """
    Frameless, translucent multi-monitor snipping overlay with rubber band selection,
    cyan border glow, dimension indicator, and crosshair cursor.
    Spans the entire virtual desktop bounding box across all connected displays.
    """
    snip_completed = pyqtSignal(QPixmap)
    snip_cancelled = pyqtSignal()

    def __init__(
        self, 
        full_screen_pixmap: QPixmap, 
        bbox: Optional[VirtualDesktopBoundingBox] = None, 
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.full_pixmap = full_screen_pixmap
        
        if bbox is not None:
            self.bbox = bbox
        else:
            screen = QGuiApplication.primaryScreen()
            if screen:
                geom = screen.geometry()
                self.bbox = VirtualDesktopBoundingBox(geom.x(), geom.y(), geom.width(), geom.height())
            else:
                self.bbox = VirtualDesktopBoundingBox(0, 0, full_screen_pixmap.width(), full_screen_pixmap.height())

        self.begin: QPoint = QPoint()
        self.end: QPoint = QPoint()
        self.is_selecting: bool = False

        self._init_window()

    def _init_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        
        # Position over virtual desktop bounding box across all screens
        self.setGeometry(self.bbox.min_x, self.bbox.min_y, self.bbox.width, self.bbox.height)
        self.show()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Draw underlying desktop snapshot
        painter.drawPixmap(0, 0, self.full_pixmap)

        # 2. Draw dark dimming mask over entire screen
        dim_color = QColor(10, 14, 20, 130)
        painter.fillRect(self.rect(), dim_color)

        # 3. Draw clear selection rectangle without dimming
        if not self.begin.isNull() and not self.end.isNull():
            selection_rect = QRect(self.begin, self.end).normalized()
            
            # Draw un-dimmed cropped snapshot in the selection rect
            if selection_rect.width() > 0 and selection_rect.height() > 0:
                painter.drawPixmap(selection_rect, self.full_pixmap, selection_rect)

                # Draw glowing cyan border
                pen = QPen(QColor("#00e5ff"), 2)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(selection_rect)

                # Draw dimensions tag (e.g. "800 x 600")
                dim_text = f"{selection_rect.width()} × {selection_rect.height()} px"
                font = QFont("Segoe UI", 9, QFont.Weight.Bold)
                painter.setFont(font)

                # Background badge for text
                badge_w = 110
                badge_h = 22
                badge_x = min(self.width() - badge_w - 10, selection_rect.right() - badge_w)
                badge_y = min(self.height() - badge_h - 10, selection_rect.bottom() + 6)
                
                if badge_y + badge_h > self.height():
                    badge_y = selection_rect.top() - badge_h - 6

                badge_rect = QRect(max(10, badge_x), max(10, badge_y), badge_w, badge_h)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(13, 17, 23, 220))
                painter.drawRoundedRect(badge_rect, 4, 4)

                painter.setPen(QColor("#00e5ff"))
                painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, dim_text)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin = event.pos()
            self.end = event.pos()
            self.is_selecting = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self._cancel()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.is_selecting:
            self.end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.end = event.pos()
            
            selection_rect = QRect(self.begin, self.end).normalized()
            selection_rect = selection_rect.intersected(self.full_pixmap.rect())
            # If region is valid (greater than 8x8 pixels)
            if selection_rect.width() > 8 and selection_rect.height() > 8:
                cropped = self.full_pixmap.copy(selection_rect)
                self.close()
                self.snip_completed.emit(cropped)
            else:
                self._cancel()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()

    def _cancel(self) -> None:
        self.close()
        self.snip_cancelled.emit()

"""Opaque, compositor-independent glass surfaces for HUD and report containers."""

from PyQt6.QtCore import QRectF, Qt, pyqtProperty
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath
from PyQt6.QtWidgets import QFrame

from ui.styles.noise import generate_noise_pixmap


class GlassPanel(QFrame):
    """Paint a theme-coloured gradient and shared grain without desktop alpha."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_color = QColor("#0d1117")
        self._intensity = 5
        self._noise = generate_noise_pixmap()

    @pyqtProperty(QColor)
    def glassColor(self):
        return self._base_color

    @glassColor.setter
    def glassColor(self, color):
        self._base_color = QColor(color)
        self._base_color.setAlpha(255)
        self.update()

    @pyqtProperty(int)
    def glassIntensity(self):
        return self._intensity

    @glassIntensity.setter
    def glassIntensity(self, value):
        self._intensity = max(0, min(30, value))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Fill even the corners: this surface never exposes the desktop.
        painter.fillRect(self.rect(), self._base_color)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.setClipPath(path)
        gradient = QLinearGradient(0, 0, 0, max(1, self.height()))
        # Keep light palettes light; only dark palettes brighten with intensity.
        light = self._base_color.lightnessF() > 0.5
        lift = 3 + self._intensity // 2
        top = (
            self._base_color
            if light
            else QColor(
                min(255, self._base_color.red() + lift),
                min(255, self._base_color.green() + lift),
                min(255, self._base_color.blue() + lift),
            )
        )
        bottom = self._base_color.darker(103 + self._intensity // 3 if light else 115)
        gradient.setColorAt(0, top)
        gradient.setColorAt(1, bottom)
        painter.fillRect(rect, gradient)
        painter.setOpacity(0.035)
        painter.fillRect(rect, QBrush(self._noise))
        painter.setOpacity(1)
        painter.setPen(QColor(255, 255, 255, 30))
        painter.drawLine(4, 1, self.width() - 4, 1)
        painter.setClipping(False)
        painter.setPen(QColor(255, 255, 255, 18))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 8, 8)

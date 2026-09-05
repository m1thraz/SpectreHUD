"""Opaque, compositor-independent glass surfaces for HUD and report containers."""

from PyQt6.QtCore import QRectF, Qt, pyqtProperty
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QRadialGradient
from PyQt6.QtWidgets import QFrame

from ui.styles.noise import generate_coarse_noise_pixmap, generate_noise_pixmap


class GlassPanel(QFrame):
    """Paint a theme-coloured gradient and shared grain without desktop alpha."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_color = QColor("#0d1117")
        self._intensity = 5
        self._noise = generate_noise_pixmap()
        self._coarse_noise = generate_coarse_noise_pixmap()

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
        if self._intensity == 0:
            return
        strength = self._intensity / 30.0
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.setClipPath(path)
        gradient = QLinearGradient(0, 0, max(1, self.width()), max(1, self.height()))
        # Keep light palettes light; only dark palettes brighten with intensity.
        light = self._base_color.lightnessF() > 0.5
        lift = 27
        top = (
            self._base_color
            if light
            else QColor(
                min(255, self._base_color.red() + lift),
                min(255, self._base_color.green() + lift),
                min(255, self._base_color.blue() + lift),
            )
        )
        bottom = self._base_color.darker(118 if light else 135)
        gradient.setColorAt(0, top)
        gradient.setColorAt(0.32, self._base_color.lighter(104) if light else top.darker(112))
        gradient.setColorAt(0.68, self._base_color.darker(104 if light else 110))
        gradient.setColorAt(1, bottom)
        painter.setOpacity(strength)
        painter.fillRect(rect, gradient)

        sheen = QRadialGradient(
            self.width() * 0.22, self.height() * 0.12, max(1, self.width() * 0.65)
        )
        sheen.setColorAt(0, QColor(255, 255, 255, 24))
        sheen.setColorAt(0.4, QColor(255, 255, 255, 7))
        sheen.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(rect, sheen)

        painter.setOpacity(0.045 * strength)
        painter.fillRect(rect, QBrush(self._coarse_noise))
        painter.setOpacity(0.055 * strength)
        painter.fillRect(rect, QBrush(self._noise))
        painter.setOpacity(strength)
        painter.setPen(QColor(255, 255, 255, 30))
        painter.drawLine(4, 1, self.width() - 4, 1)
        painter.setClipping(False)
        painter.setPen(QColor(255, 255, 255, 18))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 8, 8)

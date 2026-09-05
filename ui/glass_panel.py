"""Opaque, compositor-independent glass surfaces for HUD and report containers."""

from PyQt6.QtCore import QRectF, Qt, pyqtProperty
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QRadialGradient
from PyQt6.QtWidgets import QFrame

from ui.styles.noise import generate_coarse_noise_pixmap, generate_noise_pixmap


class GlassPanel(QFrame):
    """Paint a theme-coloured gradient and shared grain with optional background bleed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_base_color = QColor("#0d1117")
        self._base_color = QColor("#0d1117")
        self._intensity = 5
        self._real_alpha = 0
        self._panel_opacity = 1.0
        self._noise = generate_noise_pixmap()
        self._coarse_noise = generate_coarse_noise_pixmap()

    def _sync_base_color(self) -> None:
        self._base_color = QColor(self._raw_base_color)
        if self._real_alpha > 0:
            alpha = int(255 * (100 - self._real_alpha) / 100.0)
            self._base_color.setAlpha(min(self._base_color.alpha(), max(0, min(255, alpha))))

    @pyqtProperty(QColor)
    def glassColor(self):
        return self._base_color

    @glassColor.setter
    def glassColor(self, color):
        self._raw_base_color = QColor(color)
        self._sync_base_color()
        self.update()

    @pyqtProperty(int)
    def glassIntensity(self):
        return self._intensity

    @glassIntensity.setter
    def glassIntensity(self, value):
        self._intensity = max(0, min(30, value))
        self.update()

    def set_bleed_through(self, value: int) -> None:
        self._real_alpha = max(0, min(30, int(value)))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, self._real_alpha > 0)
        top = self.window()
        if top is not None and top is not self:
            top.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, self._real_alpha > 0)
        # Fake-Glass-Deckkraft sinkt, wenn echter Bleed steigt
        self._panel_opacity = max(0.5, 1.0 - (self._real_alpha / 30.0) * 0.5)
        self._sync_base_color()
        self.update()
        if top is not None and top is not self:
            top.update()

    @pyqtProperty(int)
    def bleedThrough(self):
        return self._real_alpha

    @bleedThrough.setter
    def bleedThrough(self, value):
        self.set_bleed_through(value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._real_alpha > 0 or self._base_color.alpha() < 255:
            rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            path = QPainterPath()
            path.addRoundedRect(rect, 14, 14)
            painter.fillPath(path, self._base_color)
        else:
            painter.fillRect(self.rect(), self._base_color)
            path = None
        if self._intensity == 0:
            return
        strength = self._intensity / 30.0
        if path is None:
            rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            path = QPainterPath()
            path.addRoundedRect(rect, 14, 14)
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
        painter.setOpacity(strength * self._panel_opacity)
        painter.fillRect(rect, gradient)

        sheen = QRadialGradient(
            self.width() * 0.22, self.height() * 0.12, max(1, self.width() * 0.65)
        )
        sheen.setColorAt(0, QColor(255, 255, 255, int(24 * self._panel_opacity)))
        sheen.setColorAt(0.4, QColor(255, 255, 255, int(7 * self._panel_opacity)))
        sheen.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(rect, sheen)

        painter.setOpacity(0.045 * strength * self._panel_opacity)
        painter.fillRect(rect, QBrush(self._coarse_noise))
        painter.setOpacity(0.055 * strength * self._panel_opacity)
        painter.fillRect(rect, QBrush(self._noise))
        painter.setOpacity(strength * self._panel_opacity)
        painter.setPen(QColor(255, 255, 255, int(30 * self._panel_opacity)))
        painter.drawLine(4, 1, self.width() - 4, 1)
        painter.setClipping(False)
        painter.setPen(QColor(255, 255, 255, 18))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 14, 14)

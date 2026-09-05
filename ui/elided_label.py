"""Elided label and badge helper utilities for responsive card headers."""

from typing import Optional
from PyQt6.QtCore import Qt, QObject, QEvent, QTimer
from PyQt6.QtWidgets import QLabel, QSizePolicy, QWidget


class ElidedLabel(QLabel):
    """QLabel that automatically elides overflowing text with an ellipsis."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setToolTip(text)

    def setText(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._update_elision()

    def text(self) -> str:
        """Returns the full unelided text to preserve caller expectations."""
        return self._full_text

    def full_text(self) -> str:
        """Explicit getter for original unelided string."""
        return self._full_text

    def elided_text(self) -> str:
        """Returns currently rendered text (which may contain ellipsis)."""
        return super().text()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elision()

    def _update_elision(self) -> None:
        if not self._full_text:
            super().setText("")
            return
        width = max(0, self.width())
        if width <= 0:
            super().setText(self._full_text)
            return
        elided = self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, width)
        super().setText(elided)


class _BadgeMetricsGuard(QObject):
    """Refresh badge bounds after Qt applies the actual theme font and padding."""

    def __init__(self, label, padding):
        super().__init__(label)
        self.label = label
        self.padding = padding

    def refresh(self):
        label = self.label
        width = max(label.fontMetrics().horizontalAdvance(label.text()) + self.padding,
                    label.sizeHint().width())
        label.setMinimumWidth(width)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Polish, QEvent.Type.FontChange, QEvent.Type.StyleChange):
            QTimer.singleShot(0, self.refresh)
        return False


def configure_badge_label(label: QLabel, text: str, padding: int = 14) -> QLabel:
    """Configures a badge label with dynamic minimum width and fixed vertical policy.

    Guarantees that badges (e.g. 'TARGET', categories, types) never get compressed
    or truncated into partial words ('TARC') when card widths are constrained.
    """
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    min_width = label.fontMetrics().horizontalAdvance(text) + padding
    label.setMinimumWidth(min_width)
    guard = _BadgeMetricsGuard(label, padding)
    label.installEventFilter(guard)
    label._badge_metrics_guard = guard
    return label

"""Compact QLineEdit with an embedded circular clipboard copy button on the trailing edge."""

from typing import Optional
from PyQt6.QtWidgets import QLineEdit, QPushButton, QWidget, QApplication
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from PyQt6.QtCore import Qt, QRectF, QTimer
from core.i18n import t


class CircularCopyButton(QPushButton):
    """
    Sleek circular icon button that renders a crisp vector copy icon
    and transitions to a glowing green checkmark upon click.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.retranslate()
        self.copied = False
        self._hovered = False

    def retranslate(self) -> None:
        self.setToolTip(t("varbar.copy_tip", "In Zwischenablage kopieren"))

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def trigger_success(self) -> None:
        self.copied = True
        self.update()
        QTimer.singleShot(1100, self.reset_state)

    def reset_state(self) -> None:
        self.copied = False
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = float(self.width()), float(self.height())
        rect = QRectF(1.0, 1.0, w - 2.0, h - 2.0)

        if self.copied:
            # Success: glowing green circular badge + checkmark
            painter.setPen(QPen(QColor("#00ff9d"), 1.2))
            painter.setBrush(QBrush(QColor(0, 255, 157, 45)))
            painter.drawEllipse(rect)

            painter.setPen(
                QPen(
                    QColor("#00ff9d"),
                    1.6,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(4, 8, 7, 11)
            painter.drawLine(7, 11, 12, 5)

        elif self._hovered:
            # Hover: active cyan circular badge + crisp copy sheets
            painter.setPen(QPen(QColor("#00f0ff"), 1.2))
            painter.setBrush(QBrush(QColor(0, 240, 255, 35)))
            painter.drawEllipse(rect)

            painter.setPen(QPen(QColor("#00f0ff"), 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # Front sheet
            painter.drawRoundedRect(QRectF(5.5, 5.5, 6.0, 6.0), 1.0, 1.0)
            # Back sheet lines (top and left)
            painter.drawLine(4, 9, 4, 4)
            painter.drawLine(4, 4, 9, 4)

        else:
            # Idle: subtle translucent circle ring + muted copy sheets
            painter.setPen(QPen(QColor(255, 255, 255, 40), 1.0))
            painter.setBrush(QBrush(QColor(255, 255, 255, 10)))
            painter.drawEllipse(rect)

            painter.setPen(QPen(QColor("#8b949e"), 1.1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # Front sheet
            painter.drawRoundedRect(QRectF(5.5, 5.5, 6.0, 6.0), 1.0, 1.0)
            # Back sheet lines (top and left)
            painter.drawLine(4, 9, 4, 4)
            painter.drawLine(4, 4, 9, 4)


class CopyableLineEdit(QLineEdit):
    """
    Compact QLineEdit with an embedded circular 1-click clipboard copy button on the right edge.
    Emits visual feedback (green circular checkmark) when clicked.
    """

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.btn_copy = CircularCopyButton(self)
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        self.setTextMargins(2, 0, 20, 0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        btn_w = self.btn_copy.width()
        btn_h = self.btn_copy.height()
        x = max(0, self.width() - btn_w - 3)
        y = max(0, (self.height() - btn_h) // 2)
        self.btn_copy.move(x, y)

    def copy_to_clipboard(self) -> None:
        val = self.text().strip()
        if not val:
            return
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(val)
        try:
            import pyperclip

            pyperclip.copy(val)
        except Exception:
            pass

        self.btn_copy.trigger_success()

    def retranslate(self) -> None:
        self.btn_copy.retranslate()

"""Small layout widgets used by the Report Workspace shell."""

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QStackedWidget


class ResponsiveStackedWidget(QStackedWidget):
    """Size the stack from its active inspector instead of every child."""

    def minimumSizeHint(self) -> QSize:
        current = self.currentWidget()
        if current is not None and current.isVisible():
            hint = current.minimumSizeHint()
            if hint.isValid() and hint.width() > 0:
                return QSize(min(hint.width(), 320), hint.height())
        return QSize(200, 100)

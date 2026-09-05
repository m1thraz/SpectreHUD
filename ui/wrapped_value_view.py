"""Fully expanded, selectable loot text with reliable wrapping of long tokens."""

from math import ceil

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import QTextEdit


class WrappedValueView(QTextEdit):
    """Read-only text surface; the enclosing column owns scrolling."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAcceptRichText(False)
        self.setPlainText(text)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def text(self) -> str:
        return self.toPlainText()

    def sizeHint(self) -> QSize:
        return QSize(160, self.heightForWidth(self.width()))

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.heightForWidth(self.width()))

    def heightForWidth(self, width: int) -> int:
        # Account for the actual styled frame and viewport, including QSS padding.
        horizontal_chrome = self.width() - self.viewport().width()
        vertical_chrome = self.height() - self.viewport().height()
        document = self.document().clone()
        document.setTextWidth(max(1, width - horizontal_chrome))
        height = ceil(document.size().height()) + vertical_chrome + 2
        return height

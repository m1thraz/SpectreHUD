"""Markdown source editor with protected, optionally visible Spectre metadata."""

import re

from PyQt6.QtWidgets import QPlainTextEdit


_SPECTRE_META_RE = re.compile(r"^<!--\s*spectre:[^<>]*-->\s*$", re.IGNORECASE)
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def _metadata_block_numbers(text: str) -> set[int]:
    blocks: set[int] = set()
    fence_char = ""
    fence_length = 0
    for number, line in enumerate(text.splitlines()):
        fence = _FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if not fence_char:
                fence_char = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char = ""
                fence_length = 0
        elif not fence_char and _SPECTRE_META_RE.fullmatch(line.strip()):
            blocks.add(number)
    return blocks


def _metadata_lines(text: str) -> tuple[str, ...]:
    block_numbers = _metadata_block_numbers(text)
    return tuple(
        line
        for number, line in enumerate(text.splitlines())
        if number in block_numbers
    )


class ReportSourceEditor(QPlainTextEdit):
    """Keep internal markers in the document while hiding and protecting them."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._metadata_visible = False
        self._changing_text = False
        self._protected_metadata: tuple[str, ...] = ()
        self._last_safe_text = ""
        self.textChanged.connect(self._validate_protected_metadata)

    def setPlainText(self, text: str) -> None:
        self._changing_text = True
        try:
            super().setPlainText(text)
            self._protected_metadata = _metadata_lines(text)
            self._last_safe_text = text
            self._apply_metadata_visibility()
        finally:
            self._changing_text = False

    def metadata_visible(self) -> bool:
        return self._metadata_visible

    def set_metadata_visible(self, visible: bool) -> None:
        visible = bool(visible)
        if self._metadata_visible == visible:
            return
        self._metadata_visible = visible
        self._protected_metadata = _metadata_lines(self.toPlainText())
        self._last_safe_text = self.toPlainText()
        if not visible:
            self.document().clearUndoRedoStacks()
        self._apply_metadata_visibility()

    def _validate_protected_metadata(self) -> None:
        if self._changing_text:
            return
        current = self.toPlainText()
        if not self._metadata_visible and _metadata_lines(current) != self._protected_metadata:
            cursor_position = self.textCursor().position()
            self._changing_text = True
            try:
                super().setPlainText(self._last_safe_text)
                cursor = self.textCursor()
                cursor.setPosition(min(cursor_position, len(self._last_safe_text)))
                self.setTextCursor(cursor)
            finally:
                self._changing_text = False
            self._apply_metadata_visibility()
            return
        self._protected_metadata = _metadata_lines(current)
        self._last_safe_text = current
        self._apply_metadata_visibility()

    def _apply_metadata_visibility(self) -> None:
        hidden_blocks = (
            set() if self._metadata_visible else _metadata_block_numbers(self.toPlainText())
        )
        block = self.document().firstBlock()
        while block.isValid():
            was_visible = block.isVisible()
            visible = block.blockNumber() not in hidden_blocks
            block.setVisible(visible)
            if not visible:
                block.setLineCount(0)
            elif not was_visible:
                block.setLineCount(1)
            block = block.next()
        self.document().markContentsDirty(0, self.document().characterCount())
        self.viewport().update()

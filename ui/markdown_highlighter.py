"""Fast, palette-driven Markdown syntax highlighting for the report source editor."""

import re

from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QSyntaxHighlighter

from ui.styles.palette import CYBER_BLUE_LIGHT, CYBER_CYAN, STATUS_GREEN_LIGHT, TEXT_CODE, TEXT_MUTED


class MarkdownHighlighter(QSyntaxHighlighter):
    """Regex highlighter with an explicit state for multiline fenced code blocks."""

    CODE_FENCE_STATE = 1
    HEADER_RE = re.compile(r"^#{1,6}\s+.*")
    FENCE_RE = re.compile(r"^\s*```")
    BOLD_RE = re.compile(r"\*\*.+?\*\*")
    ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(?:[^*\n]+)\*(?!\*)|(?<!_)_(?!_)(?:[^_\n]+)_(?!_)")
    INLINE_CODE_RE = re.compile(r"`[^`]+`")
    LINK_RE = re.compile(r"\[[^\]]+\]\([^\)]+\)")
    LIST_RE = re.compile(r"^\s*(?:[-*]\s+|\d+\.\s+)")

    def __init__(self, document):
        super().__init__(document)
        self.header_format = self._format(CYBER_BLUE_LIGHT, bold=True)
        self.bold_format = self._format(CYBER_CYAN, bold=True)
        self.italic_format = self._format(TEXT_MUTED, italic=True)
        self.code_format = self._format(TEXT_CODE, font_family="Consolas")
        self.link_format = self._format(CYBER_CYAN)
        self.list_format = self._format(STATUS_GREEN_LIGHT)

    @staticmethod
    def _format(color: str, bold: bool = False, italic: bool = False, font_family: str = "") -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if italic:
            fmt.setFontItalic(True)
        if font_family:
            fmt.setFontFamilies([font_family, "monospace"])
        return fmt

    def _apply_matches(self, pattern: re.Pattern, text: str, fmt: QTextCharFormat) -> None:
        for match in pattern.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), fmt)

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt API name)
        previous_state = self.previousBlockState()
        is_fence = bool(self.FENCE_RE.match(text))
        if previous_state == self.CODE_FENCE_STATE:
            self.setFormat(0, len(text), self.code_format)
            self.setCurrentBlockState(0 if is_fence else self.CODE_FENCE_STATE)
            return
        if is_fence:
            self.setFormat(0, len(text), self.code_format)
            self.setCurrentBlockState(self.CODE_FENCE_STATE)
            return

        self.setCurrentBlockState(0)
        self._apply_matches(self.HEADER_RE, text, self.header_format)
        # Bold must be laid down first; italic intentionally excludes ** markers.
        self._apply_matches(self.BOLD_RE, text, self.bold_format)
        self._apply_matches(self.ITALIC_RE, text, self.italic_format)
        self._apply_matches(self.INLINE_CODE_RE, text, self.code_format)
        self._apply_matches(self.LINK_RE, text, self.link_format)
        self._apply_matches(self.LIST_RE, text, self.list_format)

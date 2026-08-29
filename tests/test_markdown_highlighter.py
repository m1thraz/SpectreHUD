from PyQt6.QtGui import QTextDocument

from ui.markdown_highlighter import MarkdownHighlighter
from ui.styles.palette import CYBER_BLUE_LIGHT, TEXT_CODE


def _format_at(block, position):
    for item in block.layout().formats():
        if item.start <= position < item.start + item.length:
            return item.format
    return None


def test_headers_bold_and_inline_code_receive_real_formats():
    document = QTextDocument("# Heading\n**bold** and `code`")
    highlighter = MarkdownHighlighter(document)
    highlighter.rehighlight()

    header_format = _format_at(document.firstBlock(), 1)
    assert header_format.foreground().color().name() == CYBER_BLUE_LIGHT
    assert header_format.fontWeight() > 50

    second = document.findBlockByNumber(1)
    bold_format = _format_at(second, 2)
    code_format = _format_at(second, 14)
    assert bold_format.fontWeight() > 50
    assert code_format.foreground().color().name() == TEXT_CODE


def test_fenced_code_tracks_multiline_state_and_unclosed_fence():
    document = QTextDocument("```python\nprint('x')\n```\n- item\n\n```\nleft open")
    highlighter = MarkdownHighlighter(document)
    highlighter.rehighlight()

    inside_fence = document.findBlockByNumber(1)
    closing_fence = document.findBlockByNumber(2)
    open_ended = document.findBlockByNumber(6)
    assert _format_at(inside_fence, 0).foreground().color().name() == TEXT_CODE
    assert _format_at(closing_fence, 0).foreground().color().name() == TEXT_CODE
    assert _format_at(open_ended, 0).foreground().color().name() == TEXT_CODE


def test_nested_bold_and_italic_does_not_break_highlighting():
    document = QTextDocument("**bold *and italic* text**\n\n1. first")
    highlighter = MarkdownHighlighter(document)
    highlighter.rehighlight()
    block = document.firstBlock()
    italic_format = _format_at(block, 8)
    assert italic_format.fontItalic()

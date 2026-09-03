from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtGui import QTextCursor

from ui.markdown_toolbar_actions import (
    build_table,
    insert_link,
    prefix_lines,
    set_heading,
    wrap_selection,
)


def test_wrap_toggles_selection_and_selects_placeholder(qapp):
    edit = QPlainTextEdit("word")
    cursor = edit.textCursor()
    cursor.select(QTextCursor.SelectionType.WordUnderCursor)
    edit.setTextCursor(cursor)
    wrap_selection(edit, "**", "**")
    assert edit.toPlainText() == "**word**"
    cursor = edit.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    edit.setTextCursor(cursor)
    wrap_selection(edit, "**", "**")
    assert edit.toPlainText() == "word"


def test_heading_lists_link_and_table(qapp):
    edit = QPlainTextEdit("## old\na\nb")
    set_heading(edit, 1)
    assert edit.toPlainText().startswith("# old")
    cursor = edit.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(len(edit.toPlainText()), QTextCursor.MoveMode.KeepAnchor)
    edit.setTextCursor(cursor)
    prefix_lines(edit, numbered=True)
    assert "1. a" in edit.toPlainText() and "2. b" in edit.toPlainText()
    edit.clear()
    insert_link(edit)
    assert edit.toPlainText() == "[Linktext](url)"
    assert build_table(2, 3).count("\n") == 3


def test_extended_headings_h4_h6(qapp):
    edit = QPlainTextEdit("Title")
    set_heading(edit, 4)
    assert edit.toPlainText() == "#### Title"
    set_heading(edit, 6)
    assert edit.toPlainText() == "###### Title"
    set_heading(edit, 10)
    assert edit.toPlainText() == "###### Title"


def test_strikethrough_wrap_and_toggle(qapp):
    edit = QPlainTextEdit("deprecated")
    cursor = edit.textCursor()
    cursor.select(QTextCursor.SelectionType.WordUnderCursor)
    edit.setTextCursor(cursor)
    wrap_selection(edit, "~~", "~~")
    assert edit.toPlainText() == "~~deprecated~~"
    cursor = edit.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    edit.setTextCursor(cursor)
    wrap_selection(edit, "~~", "~~")
    assert edit.toPlainText() == "deprecated"


def test_insert_blockquote_and_toggle(qapp):
    from ui.markdown_toolbar_actions import insert_blockquote

    edit = QPlainTextEdit("line1\nline2")
    cursor = edit.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    edit.setTextCursor(cursor)

    # First click: adds "> "
    insert_blockquote(edit)
    assert edit.toPlainText() == "> line1\n> line2"

    # Second click: removes "> "
    cursor = edit.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    edit.setTextCursor(cursor)
    insert_blockquote(edit)
    assert edit.toPlainText() == "line1\nline2"


def test_insert_horizontal_rule(qapp):
    from ui.markdown_toolbar_actions import insert_horizontal_rule

    edit = QPlainTextEdit("")
    insert_horizontal_rule(edit)
    assert "---\n" in edit.toPlainText()

    edit = QPlainTextEdit("Some text")
    insert_horizontal_rule(edit)
    assert "Some text\n\n---\n\n" == edit.toPlainText()


def test_insert_image(qapp):
    from ui.markdown_toolbar_actions import insert_image

    edit = QPlainTextEdit("")
    insert_image(edit, "screenshots/nmap.png", alt_text="nmap")
    assert edit.toPlainText() == "![nmap](screenshots/nmap.png)"
    assert edit.textCursor().selectedText() == "nmap"

    edit = QPlainTextEdit("Web Login Form")
    cursor = edit.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    edit.setTextCursor(cursor)
    insert_image(edit, "screenshots/login.png")
    assert edit.toPlainText() == "![Web Login Form](screenshots/login.png)"



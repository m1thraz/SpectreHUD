from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtGui import QTextCursor

from ui.markdown_toolbar_actions import build_table, insert_link, prefix_lines, set_heading, wrap_selection


def test_wrap_toggles_selection_and_selects_placeholder(qapp):
    edit = QPlainTextEdit("word")
    cursor = edit.textCursor(); cursor.select(QTextCursor.SelectionType.WordUnderCursor); edit.setTextCursor(cursor)
    wrap_selection(edit, "**", "**")
    assert edit.toPlainText() == "**word**"
    cursor = edit.textCursor(); cursor.select(QTextCursor.SelectionType.Document); edit.setTextCursor(cursor)
    wrap_selection(edit, "**", "**")
    assert edit.toPlainText() == "word"


def test_heading_lists_link_and_table(qapp):
    edit = QPlainTextEdit("## old\na\nb")
    set_heading(edit, 1)
    assert edit.toPlainText().startswith("# old")
    cursor = edit.textCursor(); cursor.setPosition(6); cursor.setPosition(len(edit.toPlainText()), QTextCursor.MoveMode.KeepAnchor); edit.setTextCursor(cursor)
    prefix_lines(edit, numbered=True)
    assert "1. a" in edit.toPlainText() and "2. b" in edit.toPlainText()
    edit.clear(); insert_link(edit)
    assert edit.toPlainText() == "[Linktext](url)"
    assert build_table(2, 3).count("\n") == 3

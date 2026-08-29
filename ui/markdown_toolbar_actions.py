"""Pure cursor operations used by the Report Editor Markdown toolbar."""

import re

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QPlainTextEdit


def _select_placeholder(editor: QPlainTextEdit, start: int, length: int) -> None:
    cursor = editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


def wrap_selection(editor: QPlainTextEdit, prefix: str, suffix: str, placeholder: str = "Text") -> None:
    cursor = editor.textCursor()
    if cursor.hasSelection():
        selected = cursor.selectedText().replace("\u2029", "\n")
        if selected.startswith(prefix) and selected.endswith(suffix):
            cursor.insertText(selected[len(prefix):-len(suffix)])
        else:
            cursor.insertText(f"{prefix}{selected}{suffix}")
    else:
        start = cursor.position() + len(prefix)
        cursor.insertText(f"{prefix}{placeholder}{suffix}")
        _select_placeholder(editor, start, len(placeholder))
    editor.setFocus()


def set_heading(editor: QPlainTextEdit, level: int) -> None:
    level = max(1, min(3, level))
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
    text = cursor.selectedText()
    content = re.sub(r"^#{1,6}\s*", "", text)
    cursor.insertText(f"{'#' * level} {content}")
    editor.setFocus()


def insert_fenced_code(editor: QPlainTextEdit) -> None:
    cursor = editor.textCursor()
    start = cursor.position() + 4
    cursor.insertText("```\n\n```")
    _select_placeholder(editor, start, 0)
    editor.setFocus()


def prefix_lines(editor: QPlainTextEdit, numbered: bool = False) -> None:
    cursor = editor.textCursor()
    start, end = cursor.selectionStart(), cursor.selectionEnd()
    document = editor.document()
    first = document.findBlock(start)
    last = document.findBlock(max(start, end - 1))
    positions = []
    block = first
    number = 1
    while block.isValid():
        positions.append((block.position(), f"{number}. " if numbered else "- "))
        if block == last:
            break
        block = block.next()
        number += 1
    for position, prefix in reversed(positions):
        insert = editor.textCursor()
        insert.setPosition(position)
        insert.insertText(prefix)
    editor.setFocus()


def insert_link(editor: QPlainTextEdit) -> None:
    cursor = editor.textCursor()
    text = cursor.selectedText().replace("\u2029", "\n") if cursor.hasSelection() else "Linktext"
    start = cursor.selectionStart() + len(text) + 3
    cursor.insertText(f"[{text}](url)")
    _select_placeholder(editor, start, 3)
    editor.setFocus()


def build_table(rows: int, columns: int) -> str:
    rows, columns = max(1, rows), max(1, columns)
    header = "| " + " | ".join(f"Spalte {index}" for index in range(1, columns + 1)) + " |"
    separator = "|" + "|".join("---" for _ in range(columns)) + "|"
    body = "\n".join("| " + " | ".join("" for _ in range(columns)) + " |" for _ in range(rows))
    return f"{header}\n{separator}\n{body}"


def insert_table(editor: QPlainTextEdit, rows: int, columns: int) -> None:
    editor.textCursor().insertText(build_table(rows, columns))
    editor.setFocus()

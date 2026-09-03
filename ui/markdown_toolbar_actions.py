"""Pure cursor operations used by the Report Editor Markdown toolbar."""

import re

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QPlainTextEdit


def _select_placeholder(editor: QPlainTextEdit, start: int, length: int) -> None:
    cursor = editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


def wrap_selection(
    editor: QPlainTextEdit, prefix: str, suffix: str, placeholder: str = "Text"
) -> None:
    cursor = editor.textCursor()
    if cursor.hasSelection():
        selected = cursor.selectedText().replace("\u2029", "\n")
        if selected.startswith(prefix) and selected.endswith(suffix):
            cursor.insertText(selected[len(prefix) : -len(suffix)])
        else:
            cursor.insertText(f"{prefix}{selected}{suffix}")
    else:
        start = cursor.position() + len(prefix)
        cursor.insertText(f"{prefix}{placeholder}{suffix}")
        _select_placeholder(editor, start, len(placeholder))
    editor.setFocus()


def set_heading(editor: QPlainTextEdit, level: int) -> None:
    level = max(1, min(6, level))
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


def prefix_lines(
    editor: QPlainTextEdit, numbered: bool = False, prefix_str: str | None = None
) -> None:
    cursor = editor.textCursor()
    start, end = cursor.selectionStart(), cursor.selectionEnd()
    document = editor.document()
    first = document.findBlock(start)
    last = document.findBlock(max(start, end - 1))
    positions = []
    block = first
    number = 1
    while block.isValid():
        if prefix_str is not None:
            p = prefix_str
        elif numbered:
            p = f"{number}. "
        else:
            p = "- "
        positions.append((block.position(), p))
        if block == last:
            break
        block = block.next()
        number += 1
    for position, prefix in reversed(positions):
        insert = editor.textCursor()
        insert.setPosition(position)
        insert.insertText(prefix)
    editor.setFocus()


def insert_blockquote(editor: QPlainTextEdit) -> None:
    """Toggles or inserts blockquote (> ) prefixes on selected lines."""
    cursor = editor.textCursor()
    start, end = cursor.selectionStart(), cursor.selectionEnd()
    document = editor.document()
    first = document.findBlock(start)
    last = document.findBlock(max(start, end - 1))

    all_quoted = True
    block = first
    while block.isValid():
        if not block.text().startswith("> "):
            all_quoted = False
            break
        if block == last:
            break
        block = block.next()

    positions_and_ops = []
    block = first
    while block.isValid():
        if all_quoted:
            positions_and_ops.append((block.position(), "remove"))
        else:
            if not block.text().startswith("> "):
                positions_and_ops.append((block.position(), "add"))
        if block == last:
            break
        block = block.next()

    for pos, op in reversed(positions_and_ops):
        c = editor.textCursor()
        c.setPosition(pos)
        if op == "add":
            c.insertText("> ")
        elif op == "remove":
            c.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 2)
            c.removeSelectedText()
    editor.setFocus()


def insert_horizontal_rule(editor: QPlainTextEdit) -> None:
    """Inserts a markdown horizontal rule (---) cleanly."""
    cursor = editor.textCursor()
    block_text = cursor.block().text().strip()
    if not block_text:
        cursor.insertText("---\n")
    else:
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        cursor.insertText("\n\n---\n\n")
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

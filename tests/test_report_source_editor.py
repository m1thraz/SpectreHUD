"""Contract tests for protected Spectre metadata in the report source editor."""

from PyQt6.QtGui import QTextCursor

from ui.report.source_editor import ReportSourceEditor


REPORT_TEXT = """<!-- spectre:section:start:executive_summary -->
## Summary

<!-- spectre:loot:loot_1:deadbeef1234 -->
Finding text

```html
<!-- spectre:pagebreak -->
```

<!-- spectre:section:end:executive_summary -->"""


def _blocks(editor: ReportSourceEditor):
    block = editor.document().firstBlock()
    result = []
    while block.isValid():
        result.append((block.text(), block.isVisible()))
        block = block.next()
    return result


def test_metadata_is_hidden_without_changing_source_text(qapp):
    editor = ReportSourceEditor()
    editor.setPlainText(REPORT_TEXT)

    blocks = _blocks(editor)
    assert editor.toPlainText() == REPORT_TEXT
    assert not next(visible for text, visible in blocks if "section:start" in text)
    assert not next(visible for text, visible in blocks if "spectre:loot" in text)
    assert next(visible for text, visible in blocks if "spectre:pagebreak" in text)


def test_visible_metadata_can_be_edited_and_hidden_again(qapp):
    editor = ReportSourceEditor()
    editor.setPlainText(REPORT_TEXT)
    editor.set_metadata_visible(True)

    assert all(visible for _text, visible in _blocks(editor))
    editor.setPlainText(REPORT_TEXT.replace("deadbeef1234", "cafebabe5678"))
    editor.set_metadata_visible(False)

    assert "cafebabe5678" in editor.toPlainText()
    assert not next(
        visible for text, visible in _blocks(editor) if "spectre:loot" in text
    )


def test_hidden_metadata_rejects_edits_that_would_remove_markers(qapp):
    editor = ReportSourceEditor()
    editor.setPlainText(REPORT_TEXT)
    cursor = editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    cursor.insertText("Accidental replacement")

    assert editor.toPlainText() == REPORT_TEXT


def test_hidden_metadata_allows_normal_content_edits(qapp):
    editor = ReportSourceEditor()
    editor.setPlainText(REPORT_TEXT)
    cursor = editor.textCursor()
    cursor.setPosition(editor.toPlainText().index("Finding text"))
    cursor.insertText("Manual ")

    assert "Manual Finding text" in editor.toPlainText()
    assert "spectre:loot:loot_1:deadbeef1234" in editor.toPlainText()

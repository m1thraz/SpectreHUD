"""Find-and-replace controls used by the report source editor."""

from PyQt6.QtGui import QTextCursor, QTextDocument
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QWidget


class FindReplaceBar(QWidget):
    """Owns the find/replace UI and operates on an injected source editor."""

    def __init__(self, editor: QPlainTextEdit, parent: QWidget | None = None):
        super().__init__(parent)
        self.editor = editor
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self.find_input = QLineEdit(self)
        self.find_input.setPlaceholderText("Suchen …")
        self.find_input.textChanged.connect(self.update_count)
        self.find_input.returnPressed.connect(self.find_next)
        self.replace_input = QLineEdit(self)
        self.replace_input.setPlaceholderText("Ersetzen durch …")
        self.count_label = QLabel("0 Treffer", self)
        previous = QPushButton("↑", self)
        previous.setToolTip("Vorheriger Treffer")
        previous.clicked.connect(self.find_previous)
        next_button = QPushButton("↓", self)
        next_button.setToolTip("Nächster Treffer")
        next_button.clicked.connect(self.find_next)
        replace = QPushButton("Ersetzen", self)
        replace.clicked.connect(self.replace_current)
        replace_all = QPushButton("Alle ersetzen", self)
        replace_all.clicked.connect(self.replace_all)
        close = QPushButton("×", self)
        close.setToolTip("Suche schließen (Esc)")
        close.clicked.connect(self.close_bar)
        for widget in (self.find_input, self.replace_input, self.count_label, previous,
                       next_button, replace, replace_all, close):
            layout.addWidget(widget)
        self.hide()

    def open(self) -> None:
        self.show()
        self.find_input.setFocus()
        self.find_input.selectAll()
        self.update_count()

    def close_bar(self) -> None:
        self.hide()
        self.editor.setFocus()

    def update_count(self) -> None:
        needle = self.find_input.text()
        if not needle:
            self.count_label.setText("0 Treffer")
            return
        document = self.editor.document()
        cursor = document.find(needle)
        count = 0
        while not cursor.isNull():
            count += 1
            cursor = document.find(needle, cursor)
        self.count_label.setText(f"{count} Treffer")

    def find(self, backwards: bool = False) -> None:
        needle = self.find_input.text()
        if not needle:
            return
        flags = QTextDocument.FindFlag.FindBackward if backwards else QTextDocument.FindFlag(0)
        cursor = self.editor.document().find(needle, self.editor.textCursor(), flags)
        if cursor.isNull():
            cursor = self.editor.document().find(needle, QTextCursor(), flags)
        if not cursor.isNull():
            self.editor.setTextCursor(cursor)

    def find_next(self) -> None:
        self.find(False)

    def find_previous(self) -> None:
        self.find(True)

    def replace_current(self) -> None:
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == self.find_input.text():
            cursor.insertText(self.replace_input.text())
        self.find_next()

    def replace_all(self) -> None:
        needle = self.find_input.text()
        if not needle:
            return
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(cursor.MoveOperation.Start)
        while True:
            match = self.editor.document().find(needle, cursor)
            if match.isNull():
                break
            match.insertText(self.replace_input.text())
            cursor = match
        cursor.endEditBlock()
        self.update_count()

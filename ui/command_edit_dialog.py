"""Comfortable pre-copy editor for rendered cheatsheet commands."""

from typing import Optional

from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QWidget

from ui.base_dialog import BaseHudDialog
from core.i18n import t


class CommandEditDialog(BaseHudDialog):
    """Lets the user adjust a command in a dedicated, multi-line editor."""

    def __init__(self, command: str, parent: Optional[QWidget] = None):
        super().__init__(title=t("command_edit.title", "SPECTRE // EDIT COMMAND"), parent=parent)
        self.setMinimumWidth(660)
        self.resize(720, 400)
        self._build_editor(command)

    def _build_editor(self, command: str) -> None:
        hint = QLabel(
            t("command_edit.description", "Adjust the rendered command. The original snippet is not changed.")
        )
        hint.setWordWrap(True)
        self.body_layout.addWidget(hint)

        self.txt_command = QPlainTextEdit(command)
        self.txt_command.setObjectName("CommandEditInput")
        self.txt_command.setPlaceholderText(t("command_edit.placeholder", "Adjust command before copying..."))
        self.txt_command.setMinimumHeight(210)
        self.body_layout.addWidget(self.txt_command)

        buttons = QHBoxLayout()
        buttons.addWidget(QLabel(t("command_edit.hint", "Ctrl+Enter: Copy  |  Esc: Cancel")))
        buttons.addStretch()

        btn_cancel = QPushButton(t("dialog.cancel", "Cancel"))
        btn_cancel.setProperty("class", "SecondaryBtn")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)

        self.btn_copy = QPushButton(t("command_edit.copy", "Apply & Copy"))
        self.btn_copy.setProperty("class", "PrimaryBtn")
        self.btn_copy.clicked.connect(self.accept)
        buttons.addWidget(self.btn_copy)
        self.body_layout.addLayout(buttons)

        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.accept)
        self.txt_command.setFocus()
        self.txt_command.selectAll()

    def get_command(self) -> str:
        """Returns the edited command using the previous copy behaviour's trimming."""
        return self.txt_command.toPlainText().strip()

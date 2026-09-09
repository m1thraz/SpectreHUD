"""Shared QMessageBox helpers for actionable error reporting."""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton, QWidget

from core.i18n import t


def _copy_text(message_box: QMessageBox) -> str:
    parts = [
        message_box.windowTitle(),
        message_box.text(),
        message_box.informativeText(),
        message_box.detailedText(),
    ]
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def add_copy_button(message_box: QMessageBox) -> QPushButton:
    """Attach a button that copies every visible and expanded error detail."""
    button = message_box.addButton(
        t("dialog.copy_error", "Copy Error"),
        QMessageBox.ButtonRole.ActionRole,
    )
    if button is None:
        raise RuntimeError("QMessageBox did not create the requested copy button.")
    button.setObjectName("copyErrorButton")

    def copy_error() -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(_copy_text(message_box))

    button.clicked.connect(copy_error)
    return button


def show_error_dialog(
    parent: Optional[QWidget],
    title: str,
    message: str,
    *,
    details: str = "",
) -> None:
    """Show a critical dialog whose complete diagnostic text can be copied."""
    dialog = QMessageBox(parent)
    dialog.setWindowTitle(title)
    dialog.setText(message)
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
    dialog.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    if details:
        dialog.setDetailedText(details)
    add_copy_button(dialog)
    dialog.exec()

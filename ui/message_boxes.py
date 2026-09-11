"""Shared QMessageBox helpers for actionable error reporting."""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton, QWidget

from core.i18n import t
from core.logger import get_log_diagnostics


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


def _show_dialog(
    parent: Optional[QWidget],
    title: str,
    message: str,
    *,
    icon: QMessageBox.Icon,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    default_button: Optional[QMessageBox.StandardButton] = None,
    details: str = "",
    copyable: bool = False,
) -> QMessageBox.StandardButton:
    dialog = QMessageBox(parent)
    dialog.setWindowTitle(title)
    dialog.setText(message)
    dialog.setIcon(icon)
    dialog.setStandardButtons(buttons)
    if default_button is not None:
        dialog.setDefaultButton(default_button)
    dialog.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    if copyable:
        diagnostics = get_log_diagnostics()
        log_detail = t(
            "dialog.log_file_detail"
            if diagnostics.is_active
            else "dialog.log_file_unavailable_detail",
            "Log file: {path}"
            if diagnostics.is_active
            else "File logging is unavailable. Expected log file: {path}",
            path=str(diagnostics.path),
        )
        dialog.setDetailedText(f"{details}\n\n{log_detail}" if details else log_detail)
        add_copy_button(dialog)
    elif details:
        dialog.setDetailedText(details)
    return dialog.exec()


def show_error_dialog(
    parent: Optional[QWidget],
    title: str,
    message: str,
    *,
    details: str = "",
) -> None:
    """Show a critical dialog whose complete diagnostic text can be copied."""
    _show_dialog(
        parent,
        title,
        message,
        icon=QMessageBox.Icon.Critical,
        details=details,
        copyable=True,
    )


def show_warning_dialog(
    parent: Optional[QWidget],
    title: str,
    message: str,
    *,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    default_button: Optional[QMessageBox.StandardButton] = None,
) -> QMessageBox.StandardButton:
    return _show_dialog(
        parent,
        title,
        message,
        icon=QMessageBox.Icon.Warning,
        buttons=buttons,
        default_button=default_button,
    )


def show_information_dialog(
    parent: Optional[QWidget], title: str, message: str
) -> QMessageBox.StandardButton:
    return _show_dialog(parent, title, message, icon=QMessageBox.Icon.Information)


def ask_confirmation(
    parent: Optional[QWidget],
    title: str,
    message: str,
    *,
    buttons: QMessageBox.StandardButton = (
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    ),
    default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.No,
) -> QMessageBox.StandardButton:
    return _show_dialog(
        parent,
        title,
        message,
        icon=QMessageBox.Icon.Question,
        buttons=buttons,
        default_button=default_button,
    )

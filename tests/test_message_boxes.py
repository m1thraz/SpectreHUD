from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QMessageBox

from ui.message_boxes import add_copy_button, show_error_dialog


def test_error_copy_button_copies_title_message_and_details(qapp):
    dialog = QMessageBox()
    dialog.setWindowTitle("Save failed")
    dialog.setText("The project could not be saved.")
    dialog.setInformativeText("Permission denied")
    dialog.setDetailedText("C:/projects/Box/project_state.json")

    button = add_copy_button(dialog)
    button.click()

    assert button.objectName() == "copyErrorButton"
    assert QApplication.clipboard().text() == (
        "Save failed\n\n"
        "The project could not be saved.\n\n"
        "Permission denied\n\n"
        "C:/projects/Box/project_state.json"
    )


from pathlib import Path
from core.logger import LogDiagnostics


def test_error_dialog_includes_expected_log_path_when_file_logging_is_unavailable(qapp):
    captured_details = []
    diagnostics = LogDiagnostics(
        path=Path("C:/Diagnostics/spectrehud.log"),
        is_active=False,
    )
    with (
        patch.object(QMessageBox, "exec"),
        patch(
            "ui.message_boxes.get_log_diagnostics", return_value=diagnostics
        ),
        patch.object(
            QMessageBox,
            "setDetailedText",
            new=lambda _dialog, text: captured_details.append(text),
        ),
    ):
        show_error_dialog(None, "Failure", "Something failed", details="Traceback")

    details = captured_details[0]
    assert "Traceback" in details
    assert str(diagnostics.path) in details

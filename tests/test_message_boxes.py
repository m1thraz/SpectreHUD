from PyQt6.QtWidgets import QApplication, QMessageBox

from ui.message_boxes import add_copy_button


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

"""Focused tests for ReportController note appends."""

from unittest.mock import MagicMock

from ui.controllers.report_controller import ReportController


def _controller() -> ReportController:
    project_manager = MagicMock()
    project_manager.get_active_project.return_value = "Blue"
    controller = ReportController(project_manager, MagicMock(), MagicMock())
    controller.report_file_manager = MagicMock()
    return controller


def test_append_note_persists_without_initializing_editor(qapp):
    controller = _controller()
    controller.report_file_manager.load.return_value = "# Existing\n"
    controller.report_file_manager.save.return_value = True

    result = controller.append_note(
        {"text": "Finding", "category": "recon", "target_ip": "10.10.10.5"}
    )

    assert result is True
    controller.report_file_manager.save.assert_called_once_with(
        "# Existing\n\n### Note (RECON) - [10.10.10.5]\n\nFinding\n"
    )
    assert controller.report_editor_tab is None


def test_append_note_updates_existing_editor(qapp):
    controller = _controller()
    editor_tab = MagicMock()
    editor_tab.editor.toPlainText.return_value = ""
    controller.report_editor_tab = editor_tab

    result = controller.append_note({"text": "Finding"})

    assert result is True
    editor_tab.editor.setPlainText.assert_called_once_with(
        "# CTF Report - Blue\n\n### Note (MISC)\n\nFinding\n"
    )
    editor_tab.save.assert_called_once_with()
    controller.report_file_manager.load.assert_not_called()


def test_append_note_rejects_blank_content(qapp):
    controller = _controller()

    assert controller.append_note({"text": "  "}) is False
    controller.report_file_manager.save.assert_not_called()

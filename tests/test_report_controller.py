"""Focused tests for ReportController note appends."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.reporting import ReportReadError, ReportReadResult, ReportReadStatus
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
    editor_tab.is_write_blocked.return_value = False
    editor_tab.current_markdown.return_value = ""
    editor_tab.save.return_value = True
    controller.report_editor_tab = editor_tab

    result = controller.append_note({"text": "Finding"})

    assert result is True
    editor_tab.replace_markdown.assert_called_once_with(
        "# CTF Report - Blue\n\n### Note (MISC)\n\nFinding\n"
    )
    editor_tab.save.assert_called_once_with()
    controller.report_file_manager.load.assert_not_called()


def test_append_note_fails_closed_when_existing_report_cannot_be_read(qapp):
    controller = _controller()
    failure = ReportReadResult(
        ReportReadStatus.READ_FAILED,
        Path("report.md"),
        detail="access denied",
    )
    controller.report_file_manager.load.side_effect = ReportReadError(failure)

    with patch("ui.controllers.report_controller.show_error_dialog") as show_error:
        result = controller.append_note({"text": "Must not overwrite"})

    assert result is False
    controller.report_file_manager.save.assert_not_called()
    show_error.assert_called_once()


def test_project_switch_validates_report_even_before_editor_is_initialized(qapp):
    controller = _controller()
    failure = ReportReadError(
        ReportReadResult(
            ReportReadStatus.READ_FAILED,
            Path("report.md"),
            detail="mount unavailable",
        )
    )
    controller.report_file_manager.load.side_effect = failure

    with pytest.raises(ReportReadError):
        controller.load_project("Blue")

    controller.report_file_manager.load.assert_called_once_with("Blue")
    assert controller.report_editor_tab is None


def test_append_note_rejects_blank_content(qapp):
    controller = _controller()

    assert controller.append_note({"text": "  "}) is False
    controller.report_file_manager.save.assert_not_called()


def test_refresh_loot_sync_state_does_not_initialize_editor(qapp):
    controller = _controller()

    controller.refresh_loot_sync_state()

    assert controller.report_editor_tab is None

    editor_tab = MagicMock()
    controller.report_editor_tab = editor_tab
    controller.refresh_loot_sync_state()
    editor_tab.refresh_loot_sync_state.assert_called_once_with()

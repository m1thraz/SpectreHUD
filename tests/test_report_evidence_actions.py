"""Focused tests for report evidence collection workflows."""

from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QDialog, QWidget

from ui.report.evidence_actions import ReportEvidenceActions


def _actions(
    *,
    loot_manager=None,
    clipboard_history=None,
    report_file_manager=None,
):
    attached = MagicMock()
    actions = ReportEvidenceActions(
        parent_widget=QWidget(),
        loot_manager_provider=lambda: loot_manager,
        clipboard_history_provider=lambda: clipboard_history,
        report_file_manager_provider=lambda: report_file_manager,
        current_project_provider=lambda: "Box",
        attach_evidence=attached,
    )
    return actions, attached


def test_attach_loot_screenshot_normalizes_markdown_image_target(qapp):
    loot_manager = MagicMock()
    entry = {
        "id": "loot-1",
        "type": "screenshot",
        "title": "Admin Panel",
        "content": "![Admin](screenshots/admin.png)",
    }
    loot_manager.get_all_entries.return_value = [entry]
    actions, attached = _actions(loot_manager=loot_manager)

    with patch("ui.report.evidence_actions.LootImagePickerDialog") as picker:
        picker.return_value.exec.return_value = QDialog.DialogCode.Accepted
        picker.return_value.selected_entry = entry
        actions.attach_loot_screenshot()

    evidence = attached.call_args.args[0]
    assert evidence.type == "screenshot"
    assert evidence.content == "screenshots/admin.png"
    assert evidence.source_loot_id == "loot-1"


def test_attach_clipboard_history_builds_bounded_terminal_caption(qapp):
    clipboard_history = MagicMock()
    entry = {"id": "history-1", "text": "x" * 50 + "\nresult"}
    clipboard_history.get_all_history.return_value = [entry]
    actions, attached = _actions(clipboard_history=clipboard_history)

    with patch("ui.report.evidence_actions.ClipboardHistoryPickerDialog") as picker:
        picker.return_value.exec.return_value = QDialog.DialogCode.Accepted
        picker.return_value.selected_entry = entry
        actions.attach_clipboard_history()

    evidence = attached.call_args.args[0]
    assert evidence.type == "terminal"
    assert evidence.caption == "x" * 37 + "..."
    assert evidence.source_loot_id == "history-1"


def test_attach_loot_entry_maps_credentials_to_evidence_type(qapp):
    loot_manager = MagicMock()
    entry = {
        "id": "loot-2",
        "type": "hash",
        "title": "Administrator NTLM",
        "content": "aad3...",
    }
    loot_manager.get_all_entries.return_value = [entry]
    actions, attached = _actions(loot_manager=loot_manager)

    with patch("ui.report.evidence_actions.LootEntryPickerDialog") as picker:
        picker.return_value.exec.return_value = QDialog.DialogCode.Accepted
        picker.return_value.selected_entry = entry
        actions.attach_loot_entry()

    evidence = attached.call_args.args[0]
    assert evidence.type == "credential"
    assert evidence.caption == "Administrator NTLM"


def test_attach_image_file_uses_project_import_result(qapp, tmp_path):
    image = tmp_path / "root-proof.png"
    image.write_bytes(b"image")
    report_file_manager = MagicMock()
    report_file_manager.resolve_project_name.return_value = "Box"
    report_file_manager.project_manager.get_project_dir.return_value = tmp_path
    report_file_manager.import_image.return_value = "screenshots/root-proof.png"
    actions, attached = _actions(report_file_manager=report_file_manager)

    with patch(
        "ui.report.evidence_actions.QFileDialog.getOpenFileName",
        return_value=(str(image), ""),
    ):
        actions.attach_image_file()

    evidence = attached.call_args.args[0]
    assert evidence.type == "screenshot"
    assert evidence.caption == "root-proof"
    assert evidence.content == "screenshots/root-proof.png"
    report_file_manager.import_image.assert_called_once_with(str(image), "Box")

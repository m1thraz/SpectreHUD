"""Focused tests for application-level export orchestration."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ui.coordinators.export_coordinator import ExportCoordinator
from core.project import ProjectState
from core.reporting import ReportExportProfile


def _coordinator(config_values, project_dir: Path) -> tuple[ExportCoordinator, MagicMock]:
    project_manager = MagicMock()
    project_manager.get_project_dir.return_value = project_dir
    project_manager.load_project_state.return_value = ProjectState(
        schema_version=1,
        name="Forest",
        target_ip="10.10.10.10",
        attacker_ip="10.10.14.5",
        port="4444",
        username="",
        password="",
        wordlist="/usr/share/wordlists/dirb/common.txt",
        created_at="2026-09-10 12:00:00",
        updated_at="2026-09-10 12:00:00",
        loot=[],
        clipboard_history=[],
        quick_notes=[],
        active_phase=None,
    )
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: config_values.get(key, default)
    coordinator = ExportCoordinator(
        project_manager=project_manager,
        loot_manager=MagicMock(),
        history_ctrl=MagicMock(),
        target_provider=lambda: "10.10.10.10",
        config_manager=config,
    )
    return coordinator, project_manager


def test_report_obsidian_export_uses_shared_coordinator_workflow(tmp_path):
    coordinator, project_manager = _coordinator(
        {
            "obsidian_vault_path": str(tmp_path / "vault"),
            "obsidian_export_folder": "CTF/SpectreHUD",
            "obsidian_open_after_export": True,
        },
        tmp_path / "project",
    )
    result = SimpleNamespace(
        note_path=tmp_path / "vault" / "Forest.md",
        warnings=(),
        obsidian_uri="obsidian://open?vault=Test&file=Forest",
    )

    with (
        patch("ui.coordinators.export_coordinator.ObsidianExporter") as exporter_class,
        patch("ui.coordinators.export_coordinator.show_information_dialog") as information,
        patch(
            "ui.coordinators.export_coordinator.QDesktopServices.openUrl", return_value=True
        ) as open_url,
    ):
        exporter_class.return_value.export_report.return_value = result

        coordinator.export_report_to_obsidian(None, "Forest", "# Current editor text")

    exporter_class.assert_called_once_with(str(tmp_path / "vault"), "CTF/SpectreHUD")
    exporter_class.return_value.export_report.assert_called_once_with(
        project_name="Forest",
        project_dir=tmp_path / "project",
        markdown="# Current editor text",
        project_state=project_manager.load_project_state.return_value.to_dict(),
        overwrite="copy",
    )
    project_manager.load_project_state.assert_called_once_with("Forest")
    information.assert_called_once()
    open_url.assert_called_once()


def test_report_obsidian_export_without_vault_stops_before_exporter(tmp_path):
    coordinator, project_manager = _coordinator({}, tmp_path / "project")

    with (
        patch("ui.coordinators.export_coordinator.ObsidianExporter") as exporter_class,
        patch("ui.coordinators.export_coordinator.show_information_dialog") as information,
    ):
        coordinator.export_report_to_obsidian(None, "Forest", "# Report")

    exporter_class.assert_not_called()
    project_manager.get_project_dir.assert_not_called()
    information.assert_called_once()


def test_markdown_report_export_uses_atomic_writer(tmp_path):
    coordinator, _ = _coordinator({}, tmp_path / "project")
    target = tmp_path / "report.md"

    with patch(
        "ui.coordinators.export_coordinator.atomic_write_text",
        return_value=True,
    ) as write_text:
        coordinator.export_report_markdown(target, "# Report")

    write_text.assert_called_once_with(target, "# Report")


def test_html_report_export_resolves_project_through_coordinator(tmp_path):
    coordinator, project_manager = _coordinator({}, tmp_path / "project")
    target = tmp_path / "report.html"

    with patch(
        "ui.coordinators.export_coordinator.HtmlReportExporter.export_to_file",
        return_value=True,
    ) as export_to_file:
        coordinator.export_report_html(
            target=target,
            project_name="Forest",
            markdown="# Report",
            theme="light",
            report_font="inter",
        )

    project_manager.get_project_dir.assert_called_once_with("Forest")
    export_to_file.assert_called_once_with(
        markdown_content="# Report",
        output_path=target,
        project_dir=tmp_path / "project",
        project_name="Forest",
        target_ip="",
        theme="light",
        report_font="inter",
        language="en",
        profile=ReportExportProfile.INTERACTIVE,
        category=None,
    )


def test_cherrytree_report_export_uses_shared_project_and_loot_state(tmp_path):
    coordinator, project_manager = _coordinator({}, tmp_path / "project")
    coordinator.loot_manager.get_all_entries.return_value = [{"id": "loot-1"}]
    result = SimpleNamespace(note_path=tmp_path / "export" / "Forest.html", warnings=())

    with patch("ui.coordinators.export_coordinator.CherryTreeExporter") as exporter_class:
        exporter_class.return_value.export_package.return_value = result
        actual = coordinator.export_report_to_cherrytree(
            destination=tmp_path / "export",
            project_name="Forest",
            markdown="# Report",
            report_font="inter",
        )

    assert actual is result
    project_manager.get_project_dir.assert_called_once_with("Forest")
    exporter_class.assert_called_once_with(tmp_path / "export")
    exporter_class.return_value.export_package.assert_called_once_with(
        project_name="Forest",
        project_dir=tmp_path / "project",
        report_markdown="# Report",
        loot_entries=[{"id": "loot-1"}],
        report_font="inter",
    )


def test_export_coordinator_export_loot_delegates_to_history_ctrl():
    coordinator, project_manager = _coordinator({}, Path("/tmp/project"))
    project_manager.get_active_project.return_value = "Forest"
    mock_window = MagicMock()

    coordinator.export_loot(mock_window)

    coordinator.history_ctrl.export_report_dialog.assert_called_once_with(
        mock_window, "10.10.10.10", "Forest"
    )


def test_present_export_result_cancelled_does_nothing():
    coordinator, _ = _coordinator({}, Path("/tmp/project"))
    from core.reporting import ExportResult

    res = ExportResult.cancelled()
    with (
        patch("ui.coordinators.export_coordinator.show_information_dialog") as mock_info,
        patch("ui.coordinators.export_coordinator.show_error_dialog") as mock_err,
    ):
        coordinator.present_export_result(None, res, title="Export")
        mock_info.assert_not_called()
        mock_err.assert_not_called()


def test_present_export_result_failure_shows_error_dialog():
    coordinator, _ = _coordinator({}, Path("/tmp/project"))
    from core.reporting import ExportError, ExportErrorCode, ExportResult

    res = ExportResult.failure(
        ExportError(code=ExportErrorCode.DESTINATION_ERROR, message="Permission denied")
    )
    with patch("ui.coordinators.export_coordinator.show_error_dialog") as mock_err:
        coordinator.present_export_result(None, res, title="Export Failed")
        mock_err.assert_called_once_with(None, "Export Failed", "Permission denied", details=None)


def test_present_export_result_success_shows_info_dialog_with_warnings(tmp_path):
    coordinator, _ = _coordinator({}, tmp_path)
    from core.reporting import ExportArtifact, ExportResult

    art = ExportArtifact(path=tmp_path / "report.html", format="html", bytes_written=100)
    res = ExportResult.success(artifacts=[art], warnings=["Uncopied image"])

    with patch("ui.coordinators.export_coordinator.show_information_dialog") as mock_info:
        coordinator.present_export_result(None, res, title="Done")
        mock_info.assert_called_once()
        args = mock_info.call_args[0]
        assert args[1] == "Done"
        assert "report.html" in args[2]
        assert "Some images could not be copied" in args[2]


"""Focused tests for application-level export orchestration."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ui.coordinators.export_coordinator import ExportCoordinator


def _coordinator(config_values, project_dir: Path) -> tuple[ExportCoordinator, MagicMock]:
    project_manager = MagicMock()
    project_manager.get_project_dir.return_value = project_dir
    project_manager.load_project_state.return_value = {"target_ip": "10.10.10.10"}
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
        patch("ui.coordinators.export_coordinator.QMessageBox.information") as information,
        patch("ui.coordinators.export_coordinator.QDesktopServices.openUrl", return_value=True) as open_url,
    ):
        exporter_class.return_value.export_report.return_value = result

        coordinator.export_report_to_obsidian(None, "Forest", "# Current editor text")

    exporter_class.assert_called_once_with(str(tmp_path / "vault"), "CTF/SpectreHUD")
    exporter_class.return_value.export_report.assert_called_once_with(
        project_name="Forest",
        project_dir=tmp_path / "project",
        markdown="# Current editor text",
        project_state={"target_ip": "10.10.10.10"},
        overwrite="copy",
    )
    project_manager.load_project_state.assert_called_once_with("Forest")
    information.assert_called_once()
    open_url.assert_called_once()


def test_report_obsidian_export_without_vault_stops_before_exporter(tmp_path):
    coordinator, project_manager = _coordinator({}, tmp_path / "project")

    with (
        patch("ui.coordinators.export_coordinator.ObsidianExporter") as exporter_class,
        patch("ui.coordinators.export_coordinator.QMessageBox.information") as information,
    ):
        coordinator.export_report_to_obsidian(None, "Forest", "# Report")

    exporter_class.assert_not_called()
    project_manager.get_project_dir.assert_not_called()
    information.assert_called_once()

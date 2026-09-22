"""Focused first-run entry tests without launching a production session."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QPushButton

from core.clipboard_history import ClipboardHistory
from core.config import ConfigManager
from core.loot import LootManager
from core.project import ProjectManager
from core.reporting import ReportFileManager
from core.screenshots import ScreenshotManager
from core.snippets import SnippetManager
from core.storage import InMemoryStorageBackend
from tests.window_factory import create_main_window
from ui.getting_started_dialog import GettingStartedDialog
from ui.main_window import MainWindow
from ui.report_editor_tab import ReportEditorTab


def test_only_a_new_config_enables_first_run_prompts() -> None:
    fresh_storage = InMemoryStorageBackend()
    fresh = ConfigManager(storage=fresh_storage)
    assert fresh.get("getting_started_pending") is True
    assert fresh.get("report_editing_hint_pending") is True
    assert ConfigManager(storage=fresh_storage).get("getting_started_pending") is True

    existing = ConfigManager(storage=InMemoryStorageBackend(initial_data={"config": {}}))
    assert existing.get("getting_started_pending") is False
    assert existing.get("report_editing_hint_pending") is False


def test_getting_started_dialog_offers_existing_project_routes(qapp) -> None:
    dialog = GettingStartedDialog("Ctrl+Alt+I")
    assert "Ctrl+Alt+I" in dialog.body_layout.itemAt(1).widget().text()
    assert dialog.dont_show_again.isChecked()
    assert "Clip" in dialog.body_layout.itemAt(1).widget().text()
    dialog.btn_open_project.click()
    assert dialog.selected_action == "open_project"
    dialog.deleteLater()

    new_dialog = GettingStartedDialog("Ctrl+Alt+I")
    new_dialog.btn_new_project.click()
    assert new_dialog.selected_action == "new_project"
    new_dialog.deleteLater()


def test_welcome_dismissal_uses_existing_project_menu(qapp) -> None:
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: (
        True if key == "getting_started_pending" else default
    )
    header = SimpleNamespace(btn_project=SimpleNamespace(click=MagicMock()))
    app = SimpleNamespace(_open_new_project_dialog=MagicMock())
    window = SimpleNamespace(config=config, header_panel=header, app=app)
    dialog = MagicMock()
    dialog.dont_show_again.isChecked.return_value = True
    dialog.selected_action = "open_project"

    with (
        patch("ui.getting_started_dialog.GettingStartedDialog", return_value=dialog),
        patch("ui.main_window.QTimer.singleShot") as defer,
    ):
        MainWindow.show_getting_started_if_needed(window)

    config.set.assert_called_once_with("getting_started_pending", False)
    defer.assert_called_once_with(0, header.btn_project.click)


def test_welcome_can_open_new_project_without_disabling_future_prompt(qapp) -> None:
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: (
        True if key == "getting_started_pending" else default
    )
    app = SimpleNamespace(_open_new_project_dialog=MagicMock())
    window = SimpleNamespace(config=config, app=app)
    dialog = MagicMock()
    dialog.dont_show_again.isChecked.return_value = False
    dialog.selected_action = "new_project"

    with (
        patch("ui.getting_started_dialog.GettingStartedDialog", return_value=dialog),
        patch("ui.main_window.QTimer.singleShot") as defer,
    ):
        MainWindow.show_getting_started_if_needed(window)

    config.set.assert_not_called()
    defer.assert_called_once_with(0, app._open_new_project_dialog)


def test_report_editing_hint_appears_once_and_does_not_touch_report(qapp) -> None:
    config = ConfigManager(storage=InMemoryStorageBackend())
    file_manager = MagicMock(spec=ReportFileManager)
    tab = ReportEditorTab(
        report_file_manager=file_manager,
        loot_manager=MagicMock(),
        clipboard_history=MagicMock(),
        config_manager=config,
    )

    hint = tab.findChild(QPushButton, "ReportEditingHintDismissBtn")
    assert hint is not None
    assert config.get("report_editing_hint_pending") is True
    hint.click()

    assert config.get("report_editing_hint_pending") is False
    file_manager.save.assert_not_called()
    tab.deleteLater()


@pytest.mark.integration
def test_fresh_user_path_reaches_capture_and_report_without_enabling_clip_implicitly(
    qapp, tmp_path
) -> None:
    config = ConfigManager(config_dir=tmp_path / "config")
    projects = ProjectManager(base_dir=tmp_path / "projects")
    history = ClipboardHistory(storage_file=tmp_path / "config" / "clipboard.json")
    window = create_main_window(
        config_manager=config,
        snippet_manager=SnippetManager(),
        loot_manager=LootManager(storage_file=tmp_path / "config" / "loot.json"),
        clipboard_watcher=history,
        project_manager=projects,
        screenshot_manager=ScreenshotManager(),
    )
    try:
        assert config.get("getting_started_pending") is True
        assert not window.clipboard_monitor.is_recording

        projects.create_project("DemoBox")
        window.app.switch_to_project("DemoBox")
        window.app.trigger_quick_ip()
        popup = window.app._quick_ip_popup
        popup.txt_target.setText("192.0.2.45")
        popup.txt_attacker.setText("198.51.100.23")
        assert window.var_bar.txt_target.text() == "192.0.2.45"
        assert window.var_bar.txt_attacker.text() == "198.51.100.23"
        popup.close()

        window.app.switch_mode("cheatsheet")
        assert window.cards
        assert not history.get_all_history()

        window.app.clipboard_coord.toggle_pause()
        assert window.clipboard_monitor.is_recording
        history.add_entry("PORT STATE SERVICE VERSION\n21/tcp open ftp vsftpd 3.0.5")
        window.app.switch_mode("history")
        assert history.get_all_history()

        window.app.switch_mode("report")
        report = window.report_editor_tab
        assert report.findChild(QPushButton, "ReportEditingHintDismissBtn") is not None
        assert report.action_toolbar.btn_export.isEnabled()
    finally:
        with patch("PyQt6.QtWidgets.QMessageBox.exec", return_value=0):
            window.close()

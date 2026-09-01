"""Focused tests for runtime settings orchestration."""

from types import SimpleNamespace
from unittest.mock import Mock

from core.config import ConfigManager
from core.event_bus import EventType
from core.storage import InMemoryStorageBackend
from ui.app_controller import AppController
from ui.coordinators.settings_coordinator import SettingsCoordinator


def _coordinator() -> SettingsCoordinator:
    return SettingsCoordinator(
        config=ConfigManager(storage=InMemoryStorageBackend()),
        event_bus=Mock(),
        workspace_coord=Mock(),
        report_ctrl=Mock(),
        footer=Mock(),
        window=Mock(),
        loot_manager=Mock(),
        clipboard_watcher=Mock(),
        update_footer_status=Mock(),
        load_active_project_state=Mock(),
        refresh_filter_pills=Mock(),
        refresh_content=Mock(),
        retranslate_ui=Mock(),
    )


def test_app_controller_settings_boundary_only_delegates():
    settings_coord = Mock()
    controller = SimpleNamespace(settings_coord=settings_coord)
    settings = {"language": "de"}

    AppController._on_settings_applied(controller, settings)

    settings_coord.apply.assert_called_once_with(settings)


def test_runtime_settings_are_routed_to_existing_owners(tmp_path):
    coordinator = _coordinator()
    coordinator.apply(
        {
            "report_font": "georgia",
            "always_on_top": True,
            "hotkey": "<ctrl>+h",
            "snip_hotkey": "<ctrl>+s",
            "quit_hotkey": "<ctrl>+q",
            "workspace_dir": str(tmp_path),
            "time_format": "24h",
            "language": "de",
        }
    )

    coordinator.report_ctrl.refresh_font_configuration.assert_called_once_with()
    coordinator.footer.set_always_on_top.assert_called_once_with(True)
    coordinator.event_bus.publish.assert_called_once_with(
        EventType.HOTKEY_SETTINGS_CHANGED,
        {
            "hotkey": "<ctrl>+h",
            "snip_hotkey": "<ctrl>+s",
            "quit_hotkey": "<ctrl>+q",
        },
    )
    coordinator.workspace_coord.apply_workspace_setting.assert_called_once_with(
        workspace_dir=str(tmp_path),
        config=coordinator.config,
        window=coordinator.window,
        load_session=coordinator.load_active_project_state,
        refresh_filters=coordinator.refresh_filter_pills,
        refresh_content=coordinator.refresh_content,
    )
    coordinator.loot_manager.set_time_format.assert_called_once_with("24h")
    coordinator.clipboard_watcher.set_time_format.assert_called_once_with("24h")
    coordinator.retranslate_ui.assert_called_once_with("de")

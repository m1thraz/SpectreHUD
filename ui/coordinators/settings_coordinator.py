"""Runtime orchestration for settings accepted by the Settings dialog."""

from typing import Any, Callable, Dict

from PyQt6.QtWidgets import QApplication, QWidget

from core.clipboard_watcher import ClipboardWatcher
from core.config import ConfigManager
from core.event_bus import EventBus, EventType
from core.loot_manager import LootManager
from core.theme_loader import ThemeLoader
from ui.appearance import apply_application_style
from ui.controllers.report_controller import ReportController
from ui.panels.footer_panel import FooterPanel
from ui.coordinators.workspace_coordinator import WorkspaceCoordinator


class SettingsCoordinator:
    """Apply persisted settings to the running application and its services."""

    def __init__(
        self,
        *,
        config: ConfigManager,
        event_bus: EventBus,
        workspace_coord: WorkspaceCoordinator,
        report_ctrl: ReportController,
        footer: FooterPanel,
        window: QWidget,
        loot_manager: LootManager,
        clipboard_watcher: ClipboardWatcher,
        update_footer_status: Callable[[], None],
        load_active_project_state: Callable[[], None],
        refresh_filter_pills: Callable[[], None],
        refresh_content: Callable[[], None],
        retranslate_ui: Callable[[str], None],
    ) -> None:
        self.config = config
        self.event_bus = event_bus
        self.workspace_coord = workspace_coord
        self.report_ctrl = report_ctrl
        self.footer = footer
        self.window = window
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher
        self.update_footer_status = update_footer_status
        self.load_active_project_state = load_active_project_state
        self.refresh_filter_pills = refresh_filter_pills
        self.refresh_content = refresh_content
        self.retranslate_ui = retranslate_ui

        self.applied_theme = self.config.get(
            "theme", ThemeLoader.FALLBACK_THEME_ID
        )
        self.applied_ui_font = self.config.get("ui_font", "segoe_ui")
        self.applied_code_font = self.config.get("code_font", "consolas")

    def apply(self, new_settings: Dict[str, Any]) -> None:
        """Apply one persisted settings payload to runtime state."""
        selected_theme = new_settings.get(
            "theme", self.config.get("theme", ThemeLoader.FALLBACK_THEME_ID)
        )
        selected_ui_font = new_settings.get(
            "ui_font", self.config.get("ui_font", "segoe_ui")
        )
        selected_code_font = new_settings.get(
            "code_font", self.config.get("code_font", "consolas")
        )
        appearance_changed = (
            selected_ui_font != self.applied_ui_font
            or selected_code_font != self.applied_code_font
            or "hud_transparency" in new_settings
            or "report_transparency" in new_settings
        )
        if appearance_changed:
            # A selected theme still activates only through controlled restart.
            active_theme = (
                self.applied_theme
                if selected_theme != self.applied_theme
                else selected_theme
            )
            self.apply_application_style(theme_id=active_theme)

        if "report_font" in new_settings:
            self.report_ctrl.refresh_font_configuration()
        if "always_on_top" in new_settings:
            self.footer.set_always_on_top(bool(new_settings["always_on_top"]))
        if any(
            key in new_settings
            for key in ("hotkey", "snip_hotkey", "quit_hotkey")
        ):
            self.update_footer_status()
            self.event_bus.publish(
                EventType.HOTKEY_SETTINGS_CHANGED,
                {
                    "hotkey": new_settings.get(
                        "hotkey", self.config.get("hotkey", "<ctrl>+<cmd>+<")
                    ),
                    "snip_hotkey": new_settings.get(
                        "snip_hotkey",
                        self.config.get("snip_hotkey", "<ctrl>+<cmd>+x"),
                    ),
                    "quit_hotkey": new_settings.get(
                        "quit_hotkey",
                        self.config.get("quit_hotkey", "<ctrl>+<cmd>+q"),
                    ),
                },
            )
        if new_settings.get("workspace_dir"):
            self.workspace_coord.apply_workspace_setting(
                workspace_dir=new_settings["workspace_dir"],
                config=self.config,
                window=self.window,
                load_session=self.load_active_project_state,
                refresh_filters=self.refresh_filter_pills,
                refresh_content=self.refresh_content,
            )
        if "time_format" in new_settings:
            time_format = new_settings["time_format"]
            if hasattr(self.loot_manager, "set_time_format"):
                self.loot_manager.set_time_format(time_format)
            if hasattr(self.clipboard_watcher, "set_time_format"):
                self.clipboard_watcher.set_time_format(time_format)
        if "language" in new_settings:
            self.retranslate_ui(new_settings["language"])
        else:
            self.update_footer_status()

    def apply_application_style(self, theme_id: str | None = None) -> None:
        """Rebuild QSS while retaining the palette active before restart."""
        app = QApplication.instance()
        if app is None:
            return

        active_theme = theme_id or self.config.get(
            "theme", ThemeLoader.FALLBACK_THEME_ID
        )
        self.applied_theme = apply_application_style(
            app,
            self.config,
            theme_id=active_theme,
        )
        self.applied_ui_font = self.config.get("ui_font", "segoe_ui")
        self.applied_code_font = self.config.get("code_font", "consolas")

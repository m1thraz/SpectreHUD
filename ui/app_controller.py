"""
Central Application Orchestrator for SpectreHUD.

Orchestrates UI panels, domain managers, and specialized coordinators.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QPushButton, QMessageBox

from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
from core.screenshot_manager import ScreenshotManager
from core.project_session_service import ProjectSessionService
from core.i18n import get_i18n, get_locale, t
from core.logger import get_logger
from core.event_bus import EventBus, EventType, get_event_bus
from core.container import ServiceContainer

from ui.variable_bar import VariableBar
from ui.panels.header_panel import HeaderPanel
from ui.panels.search_panel import SearchPanel
from ui.panels.content_panel import ContentPanel
from ui.panels.footer_panel import FooterPanel
from ui.settings_dialog import SettingsDialog
from ui.controllers import (
    CheatsheetController,
    LootController,
    HistoryController,
    ReportController,
    ProjectController
)
from ui.coordinators import (
    WorkspaceCoordinator,
    NavigationCoordinator,
    ClipboardCoordinator,
    ExportCoordinator,
    EXPORT_COPY_TOOLTIP
)

logger = get_logger(__name__)


class AppController(QObject):
    """
    Lean central orchestrator coordinating UI panels and workflow coordinators.
    """

    mode_changed = pyqtSignal(str)
    content_refreshed = pyqtSignal()

    def __init__(
        self,
        window: QWidget,
        header_panel: HeaderPanel,
        search_panel: SearchPanel,
        var_bar: VariableBar,
        content_panel: ContentPanel,
        footer_panel: FooterPanel,
        config_manager: Optional[ConfigManager] = None,
        snippet_manager: Optional[SnippetManager] = None,
        loot_manager: Optional[LootManager] = None,
        clipboard_watcher: Optional[ClipboardWatcher] = None,
        project_manager: Optional[ProjectManager] = None,
        screenshot_manager: Optional[ScreenshotManager] = None,
        event_bus: Optional[EventBus] = None,
        container: Optional[ServiceContainer] = None
    ):
        super().__init__(window)
        self.window = window
        self.header = header_panel
        self.search = search_panel
        self.var_bar = var_bar
        self.content = content_panel
        self.footer = footer_panel

        if container is not None:
            self.container = container
            self.config = container.config_manager
            self.snippet_manager = container.snippet_manager
            self.project_manager = container.project_manager
            self.loot_manager = container.loot_manager
            self.clipboard_watcher = container.clipboard_watcher
            self.screenshot_manager = container.screenshot_manager
            self.event_bus = container.event_bus
        else:
            self.container = None
            self.config = config_manager if config_manager is not None else ConfigManager()
            self.snippet_manager = snippet_manager if snippet_manager is not None else SnippetManager()
            self.project_manager = project_manager if project_manager is not None else ProjectManager()
            self.loot_manager = loot_manager if loot_manager is not None else LootManager()
            self.clipboard_watcher = clipboard_watcher if clipboard_watcher is not None else ClipboardWatcher()
            self.screenshot_manager = screenshot_manager if screenshot_manager is not None else ScreenshotManager()
            self.event_bus = event_bus or get_event_bus()

        self.session_service = ProjectSessionService(
            project_manager=self.project_manager,
            loot_manager=self.loot_manager,
            clipboard_watcher=self.clipboard_watcher
        )
        self.cards: List[QWidget] = []

        # Domain Controllers
        self.cheatsheet_ctrl = CheatsheetController(self.snippet_manager, event_bus=self.event_bus, parent=self)
        self.loot_ctrl = LootController(self.loot_manager, self.project_manager, event_bus=self.event_bus, parent=self)
        self.history_ctrl = HistoryController(self.clipboard_watcher, self.loot_manager, self.project_manager, event_bus=self.event_bus, parent=self)
        self.report_ctrl = ReportController(self.project_manager, self.loot_manager, self.clipboard_watcher, parent_widget=self.window)
        self.project_ctrl = ProjectController(self.project_manager, event_bus=self.event_bus, parent=self)

        # Specialized Coordinators
        self._target_provider = lambda: self.var_bar.txt_target.text().strip() if hasattr(self.var_bar, 'txt_target') else ""

        self.navigation_coord = NavigationCoordinator(
            header=self.header, search=self.search, var_bar=self.var_bar, content=self.content,
            report_ctrl=self.report_ctrl, event_bus=self.event_bus,
            on_mode_switched=self._on_mode_switched, parent=self
        )
        self.workspace_coord = WorkspaceCoordinator(
            project_manager=self.project_manager, session_service=self.session_service,
            project_ctrl=self.project_ctrl, report_ctrl=self.report_ctrl, event_bus=self.event_bus, parent=self
        )
        self.clipboard_coord = ClipboardCoordinator(
            clipboard_watcher=self.clipboard_watcher, history_ctrl=self.history_ctrl,
            loot_ctrl=self.loot_ctrl, target_provider=self._target_provider, parent=self
        )
        self.export_coord = ExportCoordinator(
            project_manager=self.project_manager, loot_manager=self.loot_manager,
            history_ctrl=self.history_ctrl, target_provider=self._target_provider, parent=self
        )

        self._wire_signals()

        # Synchronize initial language
        initial_lang = self.config.get("language", "en")
        get_i18n().set_locale(initial_lang)
        self.snippet_manager.set_language(initial_lang)

    @property
    def active_mode(self) -> str:
        return self.navigation_coord.active_mode

    @active_mode.setter
    def active_mode(self, mode: str) -> None:
        self.navigation_coord._active_mode = mode

    def _wire_signals(self) -> None:
        # Header & Navigation
        self.header.mode_changed.connect(self.switch_mode)
        self.navigation_coord.mode_changed.connect(self.mode_changed.emit)
        self.header.project_menu_requested.connect(self._show_project_menu)
        self.header.screenshot_requested.connect(self.trigger_screenshot)
        self.header.toggle_rec_requested.connect(self.clipboard_coord.toggle_pause)
        self.header.settings_requested.connect(self.open_settings_dialog)
        self.header.minimize_requested.connect(self.window.hide)

        # Panels & Inputs
        self.search.search_changed.connect(lambda _: self.refresh_content())
        self.var_bar.variables_changed.connect(self._on_variables_changed)
        self.var_bar.add_snippet_clicked.connect(self._on_add_button_clicked)
        self.footer.always_on_top_toggled.connect(self._on_always_on_top_toggled)

        # Data & Controller Events
        self.cheatsheet_ctrl.snippets_updated.connect(self._on_data_updated)
        self.loot_ctrl.loot_updated.connect(self._on_loot_data_updated)
        self.history_ctrl.history_updated.connect(self._on_history_data_updated)
        self.clipboard_coord.history_mutated.connect(self._on_history_data_updated)
        self.clipboard_coord.loot_mutated.connect(self._on_loot_data_updated)

        self.screenshot_manager.screenshot_saved.connect(self._on_screenshot_saved)
        # Clipboard callbacks may originate outside the GUI thread.  Always
        # cross the Qt boundary before the coordinator touches UI state.
        self.clipboard_watcher.entry_added.connect(
            self._on_clipboard_entry_added,
            Qt.ConnectionType.QueuedConnection
        )
        self.clipboard_watcher.logging_state_changed.connect(self.header.update_rec_indicator)
        get_i18n().locale_changed.connect(self.retranslate_ui)

    def switch_mode(self, mode: str) -> None:
        self.navigation_coord.switch_mode(mode)

    def toggle_mode(self) -> None:
        self.navigation_coord.toggle_mode()

    def _on_mode_switched(self, mode: str) -> None:
        self.refresh_filter_pills()
        self.refresh_content()

    def refresh_filter_pills(self) -> None:
        self.search.clear_pills()
        pills_layout = self.search.get_pills_layout()
        if self.active_mode == "cheatsheet":
            self.cheatsheet_ctrl.build_filter_pills(pills_layout, self._select_category)
        elif self.active_mode == "loot":
            self.loot_ctrl.build_filter_pills(
                pills_layout, self._select_loot_type,
                lambda: self.export_coord.export_loot(self.window),
                self._clear_loot, EXPORT_COPY_TOOLTIP
            )
        elif self.active_mode == "history":
            self.history_ctrl.build_filter_pills(
                pills_layout, self._select_history_filter,
                lambda: self.export_coord.export_report(self.window),
                lambda: self.clipboard_coord.clear_history(self.window), EXPORT_COPY_TOOLTIP
            )

    def refresh_content(self) -> None:
        content_layout = self.content.get_layout()
        if self.active_mode == "report":
            self.cards = self.report_ctrl.render_content(content_layout)
            self.footer.set_count("Report Editor")
            self.content_refreshed.emit()
            return

        self.report_ctrl.detach_tab_if_needed(content_layout)
        self.content.clear_cards()
        self.cards.clear()
        query = self.search.get_query()
        variables = self.var_bar.get_variables() if self.var_bar else {}

        def _format_count(n: int) -> str:
            if n == 1:
                return t("footer.entry_count_single", "1 entry")
            return t("footer.entries_count", "{count} entries", count=n)

        if self.active_mode == "cheatsheet":
            self.cards = self.cheatsheet_ctrl.render_content(
                content_layout, query, variables, self._on_snippet_deleted, self.window, self.content.show_empty_state
            )
            self.footer.set_count(_format_count(len(self.cards)))
        elif self.active_mode == "loot":
            proj_dir = self.project_manager.get_project_dir(self.project_manager.get_active_project())
            self.cards = self.loot_ctrl.render_content(
                content_layout, query, proj_dir, self._on_loot_deleted, self._on_edit_loot_requested,
                self.window, self.content.show_empty_state
            )
            self.footer.set_count(_format_count(len(self.cards)))
        else:
            self.cards = self.history_ctrl.render_content(
                content_layout, query, variables.get("target_ip"),
                lambda item: self.clipboard_coord.add_history_to_loot(self.window, item),
                self.clipboard_coord.delete_history_entry, self.window, self.content.show_empty_state
            )
            self.footer.set_count(_format_count(len(self.cards)))
        self.content_refreshed.emit()

    def _select_category(self, cat_id: str) -> None:
        self.cheatsheet_ctrl.select_category(cat_id)
        self.refresh_content()

    def _select_loot_type(self, type_id: str) -> None:
        self.loot_ctrl.select_loot_type(type_id)
        self.refresh_content()

    def _select_history_filter(self, filter_id: str) -> None:
        self.history_ctrl.select_history_filter(filter_id)
        self.refresh_content()

    def _on_variables_changed(self, vars_dict: Dict[str, str]) -> None:
        if self.active_mode == "cheatsheet":
            self.cheatsheet_ctrl.update_variables(self.cards, vars_dict)

    def _on_add_button_clicked(self) -> None:
        target_ip = self._target_provider()
        if self.active_mode == "cheatsheet":
            if self.cheatsheet_ctrl.open_add_dialog(self.window):
                self._on_data_updated()
        elif self.active_mode == "loot":
            if self.loot_ctrl.open_add_dialog(self.window, target_ip=target_ip):
                self._on_loot_data_updated()
        else:
            if self.loot_ctrl.open_add_dialog(self.window, target_ip=target_ip, default_type="note", default_category="recon"):
                self._on_loot_data_updated()

    def _on_edit_loot_requested(self, entry: Dict[str, Any]) -> None:
        if self.loot_ctrl.open_edit_dialog(self.window, entry):
            self._on_loot_data_updated()

    def _on_snippet_deleted(self, snippet_id: str) -> None:
        self.cheatsheet_ctrl.delete_snippet(snippet_id)
        self._on_data_updated()

    def _on_loot_deleted(self, loot_id: str) -> None:
        self.loot_ctrl.delete_loot(loot_id)
        self._on_loot_data_updated()

    def _on_clipboard_entry_added(self, entry: Dict[str, Any]) -> None:
        self.clipboard_coord.on_clipboard_entry_added(entry)

    def _clear_loot(self) -> None:
        if self.loot_ctrl.clear_loot(self.window):
            self._on_loot_data_updated()

    def _on_data_updated(self) -> None:
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_loot_data_updated(self) -> None:
        self.save_current_project_state()
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_history_data_updated(self) -> None:
        self.save_current_project_state()
        if self.active_mode == "history":
            self.refresh_filter_pills()
            self.refresh_content()

    # Workspaces
    def _show_project_menu(self, btn_anchor: QPushButton) -> None:
        self.workspace_coord.show_project_menu(
            btn_anchor, self.window, self.switch_to_project, self._open_new_project_dialog
        )

    def _open_new_project_dialog(self) -> None:
        self.workspace_coord.open_new_project_dialog(
            self.window,
            self._target_provider(),
            self.var_bar.txt_attacker.text().strip() if hasattr(self.var_bar, 'txt_attacker') else "",
            self.var_bar.txt_port.text().strip() if hasattr(self.var_bar, 'txt_port') else "4444",
            self.switch_to_project
        )

    def load_active_project_state(self) -> None:
        active_proj = self.project_manager.get_active_project()
        self.header.set_project_title(active_proj)
        state = self.workspace_coord.load_active_project_session()
        if self.var_bar:
            self.var_bar.set_variables(state)

    def save_current_project_state(self) -> bool:
        vars_dict = self.var_bar.get_variables() if self.var_bar else {}
        return self.workspace_coord.save_current_project_session(vars_dict)

    def switch_to_project(self, project_name: str) -> None:
        def on_switched(pname: str):
            self.load_active_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

        self.workspace_coord.switch_to_project(
            project_name=project_name, window=self.window,
            variables_provider=lambda: self.var_bar.get_variables() if self.var_bar else {},
            on_success_callback=on_switched
        )

    # Screenshots & Settings
    def trigger_screenshot(self) -> None:
        self.screenshot_manager.start_capture(
            self.window, self.project_manager, self.loot_manager, target_ip=self._target_provider()
        )

    def _on_screenshot_saved(self, loot_entry: Dict[str, Any]) -> None:
        # AppController is the sole owner of project state persistence after screenshot.
        # ScreenshotManager only saves the PNG and emits the signal.
        if not self.save_current_project_state():
            logger.error("Project state save failed after screenshot capture.")
            screenshot_id = loot_entry.get("id")
            if screenshot_id:
                entries_before_screenshot = [
                    entry for entry in self.loot_manager.get_all_entries()
                    if entry.get("id") != screenshot_id
                ]
                self.loot_manager.replace_entries(entries_before_screenshot)

            file_path = loot_entry.get("file_path")
            if file_path:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except OSError as exc:
                    logger.error("Failed to remove screenshot PNG after session rollback: %s", exc)
            return
        self.switch_mode("loot")
        self.event_bus.publish(EventType.SCREENSHOT_SAVED, {"entry": loot_entry})

    def open_settings_dialog(self) -> None:
        dlg = SettingsDialog(self.config, parent=self.window)
        dlg.settings_applied.connect(self._on_settings_applied)
        dlg.exec()

    def _on_settings_applied(self, new_settings: Dict[str, Any]) -> None:
        if "always_on_top" in new_settings:
            self.footer.set_always_on_top(bool(new_settings["always_on_top"]))
        if any(key in new_settings for key in ("hotkey", "snip_hotkey", "quit_hotkey")):
            self._update_footer_status()
            self.event_bus.publish(EventType.HOTKEY_SETTINGS_CHANGED, {
                "hotkey": new_settings.get("hotkey", self.config.get("hotkey", "<ctrl>+<cmd>+<")),
                "snip_hotkey": new_settings.get("snip_hotkey", self.config.get("snip_hotkey", "<ctrl>+<cmd>+x")),
                "quit_hotkey": new_settings.get("quit_hotkey", self.config.get("quit_hotkey", "<ctrl>+<cmd>+q")),
            })
        if "workspace_dir" in new_settings and new_settings["workspace_dir"]:
            from core.project.validator import validate_workspace_directory, WorkspaceError
            from core.project import ProjectNotFoundError
            try:
                new_ws = validate_workspace_directory(new_settings["workspace_dir"])
                if new_ws != self.project_manager.base_dir.resolve():
                    old_base = self.project_manager.base_dir
                    old_active = self.project_manager.get_active_project()
                    try:
                        # 1. Switch workspace
                        self.project_manager.base_dir = new_ws
                        # 2. Discover projects in new workspace
                        # Discovery and its registry update are explicit so the
                        # in-memory registry cannot diverge from the persisted one.
                        available = self.project_manager.sync_registry()
                        # Registered projects may live outside the configured default
                        # workspace.  A workspace change, however, must select a
                        # project physically contained in the new workspace.
                        workspace_projects = [
                            name for name in available
                            if (new_ws / name).is_dir() and not (new_ws / name).is_symlink()
                        ]
                        # 3. Validate or reset active project
                        if old_active not in workspace_projects:
                            if workspace_projects:
                                self.project_manager.activate_project(workspace_projects[0])
                                logger.info(
                                    f"Active project '{old_active}' not found in new workspace; "
                                    f"switched to '{workspace_projects[0]}'."
                                )
                            else:
                                # A freshly selected workspace starts with a real Default
                                # project, never a dangling active-project reference.
                                self.project_manager.create_project("Default", allow_existing=True)
                                self.project_manager.sync_registry()
                                self.project_manager.activate_project("Default")
                        # 4. Reload session into UI
                        self.load_active_project_state()
                        self.refresh_filter_pills()
                        self.refresh_content()
                        # Persist only after every runtime operation completed.
                        self.config.set("workspace_dir", str(new_ws))
                    except Exception as switch_err:
                        # Rollback: restore previous workspace and active project
                        logger.error(f"Workspace switch failed, rolling back: {switch_err}")
                        self.project_manager.base_dir = old_base
                        try:
                            self.project_manager.activate_project(old_active)
                        except Exception:
                            pass
                        QMessageBox.warning(
                            self.window,
                            t("general.workspace_error", "Workspace Error"),
                            t("general.workspace_switch_failed",
                              f"Failed to switch workspace directory:\n{switch_err}\n\nThe previous workspace has been restored.")
                        )
            except WorkspaceError as e:
                logger.error(f"Failed to switch to new workspace directory: {e}")
                QMessageBox.warning(
                    self.window,
                    t("general.workspace_error", "Workspace Error"),
                    f"Failed to set workspace directory:\n{e}"
                )
        if "time_format" in new_settings:
            fmt = new_settings["time_format"]
            if hasattr(self, "loot_manager") and hasattr(self.loot_manager, "set_time_format"):
                self.loot_manager.set_time_format(fmt)
            if hasattr(self, "clipboard_watcher") and hasattr(self.clipboard_watcher, "set_time_format"):
                self.clipboard_watcher.set_time_format(fmt)
        if "language" in new_settings:
            self.retranslate_ui(new_settings["language"])
        else:
            self._update_footer_status()

    def _on_always_on_top_toggled(self, checked: bool) -> None:
        self.config.set("always_on_top", checked)
        flags = self.window.windowFlags()
        flags = (flags | Qt.WindowType.WindowStaysOnTopHint) if checked else (flags & ~Qt.WindowType.WindowStaysOnTopHint)
        was_visible = self.window.isVisible()
        self.window.setWindowFlags(flags)
        if was_visible:
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()

    def retranslate_ui(self, locale_code: str = "") -> None:
        active_lang = locale_code or get_locale()
        if hasattr(self, "snippet_manager") and self.snippet_manager:
            self.snippet_manager.set_language(active_lang)
        self.header.retranslate()
        if self.var_bar:
            self.var_bar.retranslate()
        self._update_footer_status()
        self.search.update_placeholder(self.active_mode)
        self.refresh_filter_pills()
        self.refresh_content()
        self.event_bus.publish(EventType.LANGUAGE_CHANGED, {"locale": active_lang})

    def _update_footer_status(self) -> None:
        hotkey_raw = self.config.get("hotkey", "<ctrl>+<cmd>+<")
        quit_hotkey_raw = self.config.get("quit_hotkey", "<ctrl>+<cmd>+q")
        self.footer.update_hotkey_display(hotkey_raw, quit_hotkey_raw)

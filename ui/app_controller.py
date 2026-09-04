"""
Central Application Orchestrator for SpectreHUD.

Orchestrates UI panels, domain managers, and specialized coordinators.
"""

from typing import Dict, Any, List, Optional
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QPushButton, QMessageBox

from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project import ProjectManager
from core.screenshot_manager import ScreenshotManager
from core.screenshot_transaction_service import ScreenshotTransactionService
from core.project_session_service import ProjectSessionService
from core.i18n import get_i18n, get_locale, t
from core.logger import get_logger
from core.event_bus import EventBus, EventType
from core.storage import PersistenceError

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
    QuickNoteController,
    ReportController,
    ProjectController,
)
from ui.coordinators import (
    WorkspaceCoordinator,
    NavigationCoordinator,
    ClipboardCoordinator,
    ExportCoordinator,
    SettingsCoordinator,
)

logger = get_logger(__name__)


class AppController(QObject):
    """
    Lean central orchestrator coordinating UI panels and workflow coordinators.
    """

    mode_changed = pyqtSignal(str)
    content_refreshed = pyqtSignal()
    restart_requested = pyqtSignal()

    def __init__(
        self,
        window: QWidget,
        header_panel: HeaderPanel,
        search_panel: SearchPanel,
        var_bar: VariableBar,
        content_panel: ContentPanel,
        footer_panel: FooterPanel,
        config_manager: ConfigManager,
        snippet_manager: SnippetManager,
        loot_manager: LootManager,
        clipboard_watcher: ClipboardWatcher,
        project_manager: ProjectManager,
        screenshot_manager: ScreenshotManager,
        event_bus: EventBus,
        quick_note_manager: Optional[Any] = None,
    ):
        super().__init__(window)
        self.window = window
        self.header = header_panel
        self.search = search_panel
        self.var_bar = var_bar
        self.content = content_panel
        self.footer = footer_panel

        self.config = config_manager
        self.snippet_manager = snippet_manager
        self.project_manager = project_manager
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher
        self.quick_note_manager = quick_note_manager
        self.screenshot_manager = screenshot_manager
        self.event_bus = event_bus

        self.session_service = ProjectSessionService(
            project_manager=self.project_manager,
            loot_manager=self.loot_manager,
            clipboard_watcher=self.clipboard_watcher,
            quick_note_manager=self.quick_note_manager,
        )
        self.cards: List[QWidget] = []

        # Specialized Coordinators & Providers
        self._target_provider = lambda: (
            self.var_bar.txt_target.text().strip() if hasattr(self.var_bar, "txt_target") else ""
        )

        # Domain Controllers
        self.cheatsheet_ctrl = CheatsheetController(
            self.snippet_manager, event_bus=self.event_bus, parent=self
        )
        self.loot_ctrl = LootController(
            self.loot_manager, self.project_manager, event_bus=self.event_bus, parent=self
        )
        self.report_ctrl = ReportController(
            self.project_manager,
            self.loot_manager,
            self.clipboard_watcher,
            parent_widget=self.window,
            config_manager=self.config,
        )
        self.quick_note_ctrl = QuickNoteController(
            quick_note_manager=self.quick_note_manager,
            loot_controller=self.loot_ctrl,
            report_controller=self.report_ctrl,
            target_provider=self._target_provider,
            event_bus=self.event_bus,
            parent=self,
        )
        self.history_ctrl = HistoryController(
            self.clipboard_watcher,
            self.loot_manager,
            self.project_manager,
            event_bus=self.event_bus,
            parent=self,
        )
        self.project_ctrl = ProjectController(
            self.project_manager, event_bus=self.event_bus, parent=self
        )

        self.navigation_coord = NavigationCoordinator(
            header=self.header,
            search=self.search,
            var_bar=self.var_bar,
            content=self.content,
            report_ctrl=self.report_ctrl,
            event_bus=self.event_bus,
            on_mode_switched=self._on_mode_switched,
            parent=self,
        )
        self.workspace_coord = WorkspaceCoordinator(
            project_manager=self.project_manager,
            session_service=self.session_service,
            project_ctrl=self.project_ctrl,
            report_ctrl=self.report_ctrl,
            event_bus=self.event_bus,
            parent=self,
        )
        self.clipboard_coord = ClipboardCoordinator(
            clipboard_watcher=self.clipboard_watcher,
            history_ctrl=self.history_ctrl,
            loot_ctrl=self.loot_ctrl,
            target_provider=self._target_provider,
            quick_note_ctrl=self.quick_note_ctrl,
            parent=self,
        )
        self.export_coord = ExportCoordinator(
            project_manager=self.project_manager,
            loot_manager=self.loot_manager,
            history_ctrl=self.history_ctrl,
            target_provider=self._target_provider,
            config_manager=self.config,
            parent=self,
        )
        self.report_ctrl.set_export_coordinator(self.export_coord)
        self.screenshot_transaction = ScreenshotTransactionService(
            loot_manager=self.loot_manager,
            persist_project_state=self.save_current_project_state,
        )
        self.settings_coord = SettingsCoordinator(
            config=self.config,
            event_bus=self.event_bus,
            workspace_coord=self.workspace_coord,
            report_ctrl=self.report_ctrl,
            footer=self.footer,
            window=self.window,
            loot_manager=self.loot_manager,
            clipboard_watcher=self.clipboard_watcher,
            # Resolve callbacks at invocation time so tests and runtime
            # extensions can replace the controller boundary deliberately.
            update_footer_status=lambda: self._update_footer_status(),
            load_active_project_state=lambda: self.load_active_project_state(),
            refresh_filter_pills=lambda: self.refresh_filter_pills(),
            refresh_content=lambda: self.refresh_content(),
            retranslate_ui=lambda locale: self.retranslate_ui(locale),
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
        self.header.quick_note_requested.connect(self.trigger_quick_note)
        self.header.toggle_rec_requested.connect(self.clipboard_coord.toggle_pause)
        self.header.settings_requested.connect(self.open_settings_dialog)
        self.header.minimize_requested.connect(self.window.hide)
        # request_quit(quit_app=True) must not receive QPushButton.clicked's bool
        self.header.close_requested.connect(lambda: self.window.request_quit())

        # Panels & Inputs
        self.search.search_changed.connect(lambda _: self.refresh_content())
        self.search.pills_width_changed.connect(self._on_pills_width_changed)
        self.var_bar.variables_changed.connect(self._on_variables_changed)
        self.var_bar.add_snippet_clicked.connect(self._on_add_button_clicked)
        self.footer.always_on_top_toggled.connect(self._on_always_on_top_toggled)

        # Data & Controller Events
        self.cheatsheet_ctrl.snippets_updated.connect(self._on_data_updated)
        self.loot_ctrl.loot_updated.connect(self._on_loot_data_updated)
        self.history_ctrl.history_updated.connect(self._on_history_data_updated)
        self.quick_note_ctrl.notes_updated.connect(self._on_notes_updated)
        self.clipboard_coord.history_mutated.connect(self._on_history_data_updated)
        self.clipboard_coord.loot_mutated.connect(self._on_loot_data_updated)
        self.clipboard_coord.notes_mutated.connect(self._on_notes_updated)

        self.screenshot_manager.screenshot_saved.connect(self._on_screenshot_saved)
        # Clipboard callbacks may originate outside the GUI thread.  Always
        # cross the Qt boundary before the coordinator touches UI state.
        self.clipboard_watcher.entry_added.connect(
            self._on_clipboard_entry_added, Qt.ConnectionType.QueuedConnection
        )
        if self.quick_note_manager and hasattr(self.quick_note_manager, "entry_added"):
            self.quick_note_manager.entry_added.connect(
                lambda _: self._on_notes_updated(), Qt.ConnectionType.QueuedConnection
            )
        self.clipboard_watcher.logging_state_changed.connect(self.header.update_rec_indicator)
        get_i18n().locale_changed.connect(self.retranslate_ui)

    def trigger_quick_note(self) -> None:
        """Opens the lightweight quick note capture popup."""
        if hasattr(self, "quick_note_ctrl") and self.quick_note_ctrl:
            self.quick_note_ctrl.show_popup()

    def trigger_quick_ip(self) -> None:
        """Opens the lightweight quick IP popup."""
        self._open_quick_ip_popup()

    def trigger_quick_loot(self) -> None:
        """Opens the Add-Loot dialog non-modally as a floating remote control."""
        target_ip = self._target_provider()
        self.loot_ctrl.open_add_dialog(
            parent_widget=None,
            target_ip=target_ip,
            modal=False,
            on_accepted=lambda _data: self._on_loot_data_updated(),
        )

    def _open_quick_ip_popup(self) -> None:
        if not self.var_bar:
            return
        from ui.quick_ip_popup import QuickIpPopup

        if not hasattr(self, "_quick_ip_popup") or self._quick_ip_popup is None:
            self._quick_ip_popup = QuickIpPopup(parent=None)
            self._quick_ip_popup.target_changed.connect(self._on_quick_ip_target_changed)
            self._quick_ip_popup.attacker_changed.connect(self._on_quick_ip_attacker_changed)

        vars_dict = self.var_bar.get_variables() if hasattr(self.var_bar, "get_variables") else {}
        target_ip = str(vars_dict.get("target_ip", ""))
        attacker_ip = str(vars_dict.get("attacker_ip", ""))

        self._quick_ip_popup.show_at_cursor(target_ip, attacker_ip)

    def _on_quick_ip_target_changed(self, text: str) -> None:
        if self.var_bar and hasattr(self.var_bar, "txt_target"):
            if self.var_bar.txt_target.text() != text:
                self.var_bar.txt_target.setText(text)

    def _on_quick_ip_attacker_changed(self, text: str) -> None:
        if self.var_bar and hasattr(self.var_bar, "txt_attacker"):
            if self.var_bar.txt_attacker.text() != text:
                self.var_bar.txt_attacker.setText(text)

    def _on_notes_updated(self) -> None:
        self._update_notes_badge()
        if self.active_mode == "notes":
            self.refresh_filter_pills()
            self.refresh_content()

    def _update_notes_badge(self) -> None:
        count = len(self.quick_note_manager.get_all_entries()) if self.quick_note_manager else 0
        self.header.update_notes_badge(count)

    def switch_mode(self, mode: str) -> None:
        self.navigation_coord.switch_mode(mode)

    def toggle_mode(self) -> None:
        self.navigation_coord.toggle_mode()

    def _toggle_pause_history(self) -> None:
        """Toggle clipboard history logging pause state (Ctrl+P / tray action)."""
        self.clipboard_coord.toggle_pause()

    def _on_pills_width_changed(self, width: int) -> None:
        if self.active_mode == "cheatsheet":
            self.cheatsheet_ctrl.update_pills_width(
                width, self._select_category, self.search.get_pills_layout()
            )

    def _on_mode_switched(self, mode: str) -> None:
        self.refresh_filter_pills()
        self.refresh_content()

    def refresh_filter_pills(self) -> None:
        self.search.clear_pills()
        pills_layout = self.search.get_pills_layout()
        if self.active_mode == "cheatsheet":
            self.cheatsheet_ctrl.build_filter_pills(
                pills_layout,
                self._select_category,
                available_width=self.search.get_pills_available_width(),
            )
        elif self.active_mode == "loot":
            loot_view_mode = self.config.get("loot_view_mode", "list")
            export_tooltip = t(
                "report.export_copy_tip",
                "Creates a new copy based on current session loot",
            )
            self.loot_ctrl.build_filter_pills(
                pills_layout,
                self._select_loot_type,
                lambda: self.export_coord.export_loot(self.window),
                self._clear_loot,
                export_tooltip,
                lambda: self.export_coord.export_loot_to_obsidian(self.window),
                self._toggle_loot_view,
                loot_view_mode,
            )
        elif self.active_mode == "history":
            export_tooltip = t(
                "report.export_copy_tip",
                "Creates a new copy based on current session loot",
            )
            self.history_ctrl.build_filter_pills(
                pills_layout,
                self._select_history_filter,
                lambda: self.export_coord.export_report(self.window),
                lambda: self.clipboard_coord.clear_history(self.window),
                export_tooltip,
            )
        elif self.active_mode == "notes":
            self.quick_note_ctrl.build_filter_pills(
                pills_layout,
                self._select_notes_filter,
                self._clear_notes,
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
                content_layout,
                query,
                variables,
                self._on_snippet_deleted,
                self.window,
                self.content.show_empty_state,
                self._on_content_copied,
            )
            self.footer.set_count(_format_count(len(self.cards)))
        elif self.active_mode == "loot":
            proj_dir = self.project_manager.get_project_dir(
                self.project_manager.get_active_project()
            )
            if self.config.get("loot_view_mode", "list") == "board":
                self.cards = self.loot_ctrl.render_board_content(
                    content_layout,
                    query,
                    proj_dir,
                    self._on_loot_deleted,
                    self._on_edit_loot_requested,
                    self._on_export_loot_entry,
                    self._on_move_loot_category,
                    self.window,
                    on_export_obsidian=lambda entry_id: (
                        self.export_coord.export_single_loot_to_obsidian(self.window, entry_id)
                    ),
                    on_copied=self._on_content_copied,
                )
            else:
                self.cards = self.loot_ctrl.render_content(
                    content_layout,
                    query,
                    proj_dir,
                    self._on_loot_deleted,
                    self._on_edit_loot_requested,
                    self._on_export_loot_entry,
                    self.window,
                    self.content.show_empty_state,
                    on_export_obsidian=lambda entry_id: (
                        self.export_coord.export_single_loot_to_obsidian(self.window, entry_id)
                    ),
                    on_copied=self._on_content_copied,
                )
            self.footer.set_count(_format_count(len(self.cards)))
        elif self.active_mode == "notes":
            self.cards = self.quick_note_ctrl.render_content(
                content_layout,
                query,
                self._on_content_copied,
                self.window,
                self.content.show_empty_state,
                on_edit_note=self._on_edit_note_requested,
            )
            self.footer.set_count(_format_count(len(self.cards)))
        else:
            self.cards = self.history_ctrl.render_content(
                content_layout,
                query,
                variables.get("target_ip"),
                lambda item: self.clipboard_coord.add_history_to_loot(self.window, item),
                self.clipboard_coord.delete_history_entry,
                self.window,
                self.content.show_empty_state,
                self._on_content_copied,
                on_add_to_note=lambda item: self.clipboard_coord.add_history_to_note(
                    self.window, item
                ),
                on_edit_history=self._on_edit_history_requested,
            )
            self.footer.set_count(_format_count(len(self.cards)))
        self.content.refresh_content_geometry()
        self.content.schedule_content_geometry_refresh()
        self.content_refreshed.emit()

    def _on_content_copied(self, _text: str) -> None:
        """Minimize the overlay after an intentional card copy when configured."""
        if self.config.get("auto_hide_on_copy", False):
            self.window.showMinimized()

    def _select_category(self, cat_id: str) -> None:
        self.cheatsheet_ctrl.select_category(cat_id)
        self.refresh_content()

    def _select_loot_type(self, type_id: str) -> None:
        self.loot_ctrl.select_loot_type(type_id)
        self.refresh_content()

    def _toggle_loot_view(self) -> None:
        """Persist and immediately apply the alternate Loot presentation."""
        current_mode = self.config.get("loot_view_mode", "list")
        next_mode = "list" if current_mode == "board" else "board"
        try:
            self.config.set("loot_view_mode", next_mode)
        except PersistenceError as exc:
            logger.error(f"Could not persist Loot view mode: {exc}")
            QMessageBox.critical(
                self.window,
                t("loot.view_switch_failed_title", "View switch failed"),
                t(
                    "loot.view_switch_failed",
                    "The Loot view could not be changed:\n{error}",
                    error=str(exc),
                ),
            )
            return
        self.refresh_filter_pills()
        self.refresh_content()

    def _select_notes_filter(self, filter_id: str) -> None:
        self.quick_note_ctrl.select_filter(filter_id)
        self.refresh_content()

    def _clear_notes(self) -> None:
        if self.quick_note_ctrl.clear_all_notes(self.window):
            self._on_notes_updated()

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
        elif self.active_mode in ("notes", "history"):
            self.quick_note_ctrl.show_popup()

    def _on_edit_loot_requested(self, entry: Dict[str, Any]) -> None:
        if self.loot_ctrl.open_edit_dialog(self.window, entry):
            self._on_loot_data_updated()

    def _on_edit_history_requested(self, entry: Dict[str, Any]) -> None:
        if self.history_ctrl.open_edit_dialog(self.window, entry):
            self._on_history_data_updated()

    def _on_edit_note_requested(self, entry: Dict[str, Any]) -> None:
        if self.quick_note_ctrl.open_edit_dialog(self.window, entry):
            self._on_notes_updated()

    def _on_export_loot_entry(self, entry_id: str) -> None:
        self.loot_ctrl.export_entry_to_file_with_feedback(entry_id, self.window)

    def _on_move_loot_category(self, entry_id: str, category: str, target_index: int) -> bool:
        return self.loot_ctrl.move_entry_to_category(entry_id, category, target_index, self.window)

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
            self.var_bar.txt_attacker.text().strip()
            if hasattr(self.var_bar, "txt_attacker")
            else "",
            self.var_bar.txt_port.text().strip() if hasattr(self.var_bar, "txt_port") else "4444",
            self.switch_to_project,
        )

    def load_active_project_state(self) -> None:
        active_proj = self.project_manager.get_active_project()
        self.header.set_project_title(active_proj)
        state = self.workspace_coord.load_active_project_session(self.window)
        if self.var_bar:
            self.var_bar.set_variables(state)
        self._update_notes_badge()

    def save_current_project_state(self) -> bool:
        vars_dict = self.var_bar.get_variables() if self.var_bar else {}
        return self.workspace_coord.save_current_project_session(vars_dict)

    def switch_to_project(self, project_name: str) -> None:
        def on_switched(pname: str):
            self.load_active_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

        self.workspace_coord.switch_to_project(
            project_name=project_name,
            window=self.window,
            variables_provider=lambda: self.var_bar.get_variables() if self.var_bar else {},
            on_success_callback=on_switched,
        )

    # Screenshots & Settings
    def trigger_screenshot(self) -> None:
        if not self.screenshot_manager.is_capture_available():
            if self.screenshot_manager.capabilities.wayland:
                msg = t(
                    "header.snip_wayland_unavailable",
                    "Bereichs-Screenshot ist unter Wayland derzeit nicht verfügbar.",
                )
            else:
                msg = t(
                    "header.snip_unavailable",
                    "Bereichs-Screenshot ist auf dieser Plattform nicht verfügbar.",
                )
            logger.warning(msg)
            if hasattr(self, "header") and hasattr(self.header, "btn_screenshot") and self.header.btn_screenshot:
                from PyQt6.QtWidgets import QToolTip
                btn = self.header.btn_screenshot
                QToolTip.showText(btn.mapToGlobal(btn.rect().bottomLeft()), msg, btn)
            return

        self.screenshot_manager.start_capture(
            self.window, self.project_manager, self.loot_manager, target_ip=self._target_provider()
        )

    def _on_screenshot_saved(self, loot_entry: Dict[str, Any]) -> None:
        result = self.screenshot_transaction.commit(loot_entry)
        if not result.ok:
            return
        self.switch_mode("loot")
        self.event_bus.publish(EventType.SCREENSHOT_SAVED, {"entry": loot_entry})

    def open_settings_dialog(self) -> None:
        previous_theme = self.config.get("theme", "cyber_dark")
        applied_settings: Dict[str, Any] = {}
        dlg = SettingsDialog(self.config, parent=self.window)

        def apply_settings(settings: Dict[str, Any]) -> None:
            applied_settings.update(settings)
            self._on_settings_applied(settings)

        dlg.settings_applied.connect(apply_settings)
        accepted = bool(dlg.exec())
        if accepted and applied_settings.get("theme", previous_theme) != previous_theme:
            self.restart_requested.emit()

    def _on_settings_applied(self, new_settings: Dict[str, Any]) -> None:
        self.settings_coord.apply(new_settings)

    def _on_always_on_top_toggled(self, checked: bool) -> None:
        self.config.set("always_on_top", checked)
        flags = self.window.windowFlags()
        flags = (
            (flags | Qt.WindowType.WindowStaysOnTopHint)
            if checked
            else (flags & ~Qt.WindowType.WindowStaysOnTopHint)
        )
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
        self._update_notes_badge()
        if self.var_bar:
            self.var_bar.retranslate()
        self._update_footer_status()
        self.search.update_placeholder(self.active_mode)
        self.refresh_filter_pills()
        self.refresh_content()
        self.event_bus.publish(EventType.LANGUAGE_CHANGED, {"locale": active_lang})

    def _update_footer_status(self) -> None:
        hotkey_raw = self.config.get("hotkey", "<ctrl>+<alt>+h")
        quit_hotkey_raw = self.config.get("quit_hotkey", "<ctrl>+<alt>+q")
        quick_note_hotkey_raw = self.config.get("quick_note_hotkey", "<ctrl>+<alt>+n")
        quick_ip_hotkey_raw = self.config.get("quick_ip_hotkey", "<ctrl>+<alt>+i")
        quick_loot_hotkey_raw = self.config.get("quick_loot_hotkey", "<ctrl>+<alt>+l")
        self.footer.update_hotkey_display(
            hotkey_raw,
            quit_hotkey_raw,
            quick_note_hotkey_raw=quick_note_hotkey_raw,
            quick_ip_hotkey_raw=quick_ip_hotkey_raw,
            quick_loot_hotkey_raw=quick_loot_hotkey_raw,
        )

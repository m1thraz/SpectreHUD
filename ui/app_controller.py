import sys
from typing import Dict, Any, List, Optional
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QMessageBox, QPushButton

from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
from core.screenshot_manager import ScreenshotManager
from core.project_session_service import ProjectSessionService
from core.report_file_manager import ReportFileManager
from core.i18n import get_i18n, get_locale, t
from core.logger import get_logger
from core.event_bus import EventBus, EventType, get_event_bus

from ui.variable_bar import VariableBar
from ui.panels.header_panel import HeaderPanel
from ui.panels.search_panel import SearchPanel
from ui.panels.content_panel import ContentPanel
from ui.panels.footer_panel import FooterPanel
from ui.settings_dialog import SettingsDialog
from ui.styles import CYBER_DARK_QSS
from ui.controllers import (
    CheatsheetController,
    LootController,
    HistoryController,
    ReportController,
    ProjectController
)

logger = get_logger("app_controller")

EXPORT_COPY_TOOLTIP = (
    "Erstellt eine neue Kopie basierend auf dem aktuellen Loot. "
    "Für die bearbeitbare Version siehe Report-Tab."
)
from core.container import ServiceContainer


class AppController(QObject):
    """
    Central application coordinator connecting UI panels, domain services, and workflow controllers.
    Manages mode navigation, workspace lifecycles, signal dispatching, and settings synchronization.
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

        # Domain Session Service
        self.session_service = ProjectSessionService(
            project_manager=self.project_manager,
            loot_manager=self.loot_manager,
            clipboard_watcher=self.clipboard_watcher
        )

        self.active_mode = "cheatsheet"  # 'cheatsheet', 'loot', 'history', or 'report'
        self.cards: List[QWidget] = []

        # Domain Controllers
        self.cheatsheet_ctrl = CheatsheetController(self.snippet_manager, event_bus=self.event_bus, parent=self)
        self.loot_ctrl = LootController(self.loot_manager, self.project_manager, event_bus=self.event_bus, parent=self)
        self.history_ctrl = HistoryController(self.clipboard_watcher, self.loot_manager, self.project_manager, event_bus=self.event_bus, parent=self)
        self.report_ctrl = ReportController(self.project_manager, self.loot_manager, self.clipboard_watcher, parent_widget=self.window)
        self.project_ctrl = ProjectController(self.project_manager, event_bus=self.event_bus, parent=self)

        # Wire all events and listeners
        self._wire_signals()

        # Synchronize initial language from config
        initial_lang = self.config.get("language", "en")
        get_i18n().set_locale(initial_lang)
        self.snippet_manager.set_language(initial_lang)

    def _wire_signals(self) -> None:
        # Header Panel signals
        self.header.mode_changed.connect(self.switch_mode)
        self.header.project_menu_requested.connect(self._show_project_menu)
        self.header.screenshot_requested.connect(self.trigger_screenshot)
        self.header.toggle_rec_requested.connect(self._toggle_pause_history)
        self.header.settings_requested.connect(self.open_settings_dialog)
        self.header.minimize_requested.connect(self.window.hide)

        # Search Panel signals
        self.search.search_changed.connect(self._on_search_changed)

        # Variable Bar signals
        self.var_bar.variables_changed.connect(self._on_variables_changed)
        self.var_bar.add_snippet_clicked.connect(self._on_add_button_clicked)

        # Footer Panel signals
        self.footer.always_on_top_toggled.connect(self._on_always_on_top_toggled)

        # Controller signals
        self.cheatsheet_ctrl.snippets_updated.connect(self._on_data_updated)
        self.loot_ctrl.loot_updated.connect(self._on_loot_data_updated)
        self.history_ctrl.history_updated.connect(self._on_history_data_updated)

        # Screenshot & Clipboard Watcher signals
        self.screenshot_manager.screenshot_saved.connect(self._on_screenshot_saved)
        self.clipboard_watcher.set_target_provider(lambda: self.var_bar.txt_target.text().strip() if hasattr(self.var_bar, 'txt_target') else "")
        self.clipboard_watcher.entry_added.connect(self._on_clipboard_entry_added)
        self.clipboard_watcher.logging_state_changed.connect(self._on_logging_state_changed)

        # i18n
        get_i18n().locale_changed.connect(self.retranslate_ui)

    # -------------------------------------------------------------
    # Navigation & Mode Switching
    # -------------------------------------------------------------
    def switch_mode(self, mode: str) -> None:
        """Switches between 'cheatsheet', 'loot', 'history', and 'report' modes."""
        if self.active_mode == "report" and mode != "report":
            if not self.report_ctrl.confirm_discard_if_dirty():
                return

        self.active_mode = mode
        self.header.set_active_mode(mode)

        self.content.set_privacy_banner_visible(mode == "history")
        self.search.setVisible(mode != "report")
        self.var_bar.setVisible(mode != "report")

        self.search.update_placeholder(mode)
        self.refresh_filter_pills()
        self.refresh_content()

        if mode != "report":
            self.search.set_focus()

        self.mode_changed.emit(mode)
        self.event_bus.publish(EventType.MODE_CHANGED, {"mode": mode})

    def toggle_mode(self) -> None:
        """Cycles through modes via Tab shortcut (Report mode excluded from Tab cycle)."""
        modes = ["cheatsheet", "loot", "history"]
        idx = modes.index(self.active_mode) if self.active_mode in modes else 0
        next_mode = modes[(idx + 1) % len(modes)]
        self.switch_mode(next_mode)

    # -------------------------------------------------------------
    # Content & Filter Rendering
    # -------------------------------------------------------------
    def refresh_filter_pills(self) -> None:
        """Populates horizontal filter pills and contextual actions depending on active mode."""
        self.search.clear_pills()
        pills_layout = self.search.get_pills_layout()

        if self.active_mode == "report":
            return

        if self.active_mode == "cheatsheet":
            self.cheatsheet_ctrl.build_filter_pills(
                pills_layout, self._select_category
            )
        elif self.active_mode == "loot":
            self.loot_ctrl.build_filter_pills(
                pills_layout, self._select_loot_type,
                self._export_loot, self._clear_loot, EXPORT_COPY_TOOLTIP
            )
        elif self.active_mode == "history":
            self.history_ctrl.build_filter_pills(
                pills_layout, self._select_history_filter,
                self._export_report, self._clear_history, EXPORT_COPY_TOOLTIP
            )

    def refresh_content(self) -> None:
        """Rebuilds scrollable cards or displays ReportEditorTab based on active mode and query."""
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

        if self.active_mode == "cheatsheet":
            self.cards = self.cheatsheet_ctrl.render_content(
                content_layout, query, variables,
                self._on_snippet_deleted, self.window, self.content.show_empty_state
            )
            self.footer.set_count(f"{len(self.cards)} Befehle")
        elif self.active_mode == "loot":
            active_proj = self.project_manager.get_active_project()
            proj_dir = self.project_manager.get_project_dir(active_proj)
            self.cards = self.loot_ctrl.render_content(
                content_layout, query, proj_dir,
                self._on_loot_deleted, self._on_edit_loot_requested,
                self.window, self.content.show_empty_state
            )
            self.footer.set_count(f"{len(self.cards)} Loot-Einträge")
        else:
            target_ip = variables.get("target_ip")
            self.cards = self.history_ctrl.render_content(
                content_layout, query, target_ip,
                self._on_history_add_to_loot, self._on_history_entry_deleted,
                self.window, self.content.show_empty_state
            )
            self.footer.set_count(f"{len(self.cards)} Verlaufseinträge")

        self.content_refreshed.emit()

    # -------------------------------------------------------------
    # Event Handlers & Sub-Actions
    # -------------------------------------------------------------
    def _select_category(self, category_id: str) -> None:
        self.cheatsheet_ctrl.select_category(category_id)
        self.refresh_content()

    def _select_loot_type(self, type_id: str) -> None:
        self.loot_ctrl.select_loot_type(type_id)
        self.refresh_content()

    def _select_history_filter(self, filter_id: str) -> None:
        self.history_ctrl.select_history_filter(filter_id)
        self.refresh_content()

    def _on_search_changed(self, text: str) -> None:
        self.refresh_content()

    def _on_variables_changed(self, vars_dict: Dict[str, str]) -> None:
        if self.active_mode == "cheatsheet":
            self.cheatsheet_ctrl.update_variables(self.cards, vars_dict)

    def _on_add_button_clicked(self) -> None:
        if self.active_mode == "cheatsheet":
            if self.cheatsheet_ctrl.open_add_dialog(self.window):
                self.refresh_filter_pills()
                self.refresh_content()
        elif self.active_mode == "loot":
            target_ip = self.var_bar.txt_target.text().strip() if hasattr(self.var_bar, 'txt_target') else ""
            if self.loot_ctrl.open_add_dialog(self.window, target_ip=target_ip):
                self.save_current_project_state()
                self.refresh_filter_pills()
                self.refresh_content()
        else:
            target_ip = self.var_bar.txt_target.text().strip() if hasattr(self.var_bar, 'txt_target') else ""
            if self.loot_ctrl.open_add_dialog(self.window, target_ip=target_ip, default_type="note", default_category="recon"):
                self.save_current_project_state()
                self.refresh_filter_pills()
                self.refresh_content()

    def _on_edit_loot_requested(self, entry: Dict[str, Any]) -> None:
        if self.loot_ctrl.open_edit_dialog(self.window, entry):
            self.save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _on_snippet_deleted(self, snippet_id: str) -> None:
        self.cheatsheet_ctrl.delete_snippet(snippet_id)
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_loot_deleted(self, loot_id: str) -> None:
        self.loot_ctrl.delete_loot(loot_id)
        self.save_current_project_state()
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_clipboard_entry_added(self, entry: Dict[str, Any]) -> None:
        if self.active_mode == "history":
            self.refresh_filter_pills()
            self.refresh_content()
        self.save_current_project_state()

    def _on_history_entry_deleted(self, entry_id: str) -> None:
        self.history_ctrl.delete_entry(entry_id)
        self.save_current_project_state()
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_history_add_to_loot(self, history_item: Dict[str, Any]) -> None:
        target_ip = history_item.get("target_ip") or (self.var_bar.txt_target.text().strip() if hasattr(self.var_bar, 'txt_target') else "")
        if self.loot_ctrl.open_add_dialog(
            parent_widget=self.window,
            target_ip=target_ip,
            default_type="credentials" if history_item.get("is_command") else "note",
            default_category="access" if history_item.get("is_command") else "recon",
            default_title=f"Kopiert aus Terminal ({history_item.get('timestamp', '')})",
            default_content=history_item.get("text", "")
        ):
            self.save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _clear_loot(self) -> None:
        if self.loot_ctrl.clear_loot(self.window):
            self.save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _clear_history(self) -> None:
        if self.history_ctrl.clear_history(self.window):
            self.save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _export_loot(self) -> None:
        self._export_report()

    def _export_report(self) -> None:
        target_ip = self.var_bar.txt_target.text().strip() if hasattr(self.var_bar, 'txt_target') else ""
        active_proj = self.project_manager.get_active_project()
        self.history_ctrl.export_report(self.window, target_ip, active_proj)

    def _toggle_pause_history(self) -> None:
        self.history_ctrl.toggle_pause()

    def _on_logging_state_changed(self, is_active: bool) -> None:
        self.header.update_rec_indicator(is_active)

    def _on_data_updated(self) -> None:
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_loot_data_updated(self) -> None:
        self.save_current_project_state()
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_history_data_updated(self) -> None:
        self.save_current_project_state()
        self.refresh_filter_pills()
        self.refresh_content()

    # -------------------------------------------------------------
    # Project Workspaces
    # -------------------------------------------------------------
    def _show_project_menu(self, btn_anchor: QPushButton) -> None:
        self.project_ctrl.show_project_menu(
            btn_anchor, self.switch_to_project, self._open_new_project_dialog, self.window
        )

    def _open_new_project_dialog(self) -> None:
        curr_target = self.var_bar.txt_target.text().strip() if hasattr(self.var_bar, 'txt_target') else ""
        curr_attacker = self.var_bar.txt_attacker.text().strip() if hasattr(self.var_bar, 'txt_attacker') else ""
        curr_port = self.var_bar.txt_port.text().strip() if hasattr(self.var_bar, 'txt_port') else "4444"

        self.project_ctrl.open_new_project_dialog(
            self.window, curr_target, curr_attacker, curr_port, self.switch_to_project
        )

    def load_active_project_state(self) -> None:
        active_proj = self.project_manager.get_active_project()
        self.header.set_project_title(active_proj)

        state = self.session_service.load_project_session(active_proj)
        if self.var_bar:
            self.var_bar.set_variables(state)

    def save_current_project_state(self) -> bool:
        variables = self.var_bar.get_variables() if self.var_bar else {}
        return self.session_service.save_project_session(variables)

    def switch_to_project(self, project_name: str) -> None:
        if project_name == self.project_manager.get_active_project():
            return
        
        if not self.report_ctrl.confirm_discard_if_dirty():
            return

        current_proj = self.project_manager.get_active_project()
        if not self.save_current_project_state():
            logger.error(f"Failed to persist state for project '{current_proj}' before switching to '{project_name}'")
            msg = QMessageBox(self.window)
            msg.setWindowTitle(t("general.save_failed", "Speichern fehlgeschlagen"))
            msg.setText(
                f"Der Zustand des aktuellen Projekts '{current_proj}' konnte nicht auf der Festplatte gespeichert werden.\n\n"
                "Möchtest du den Projektwechsel trotzdem fortsetzen und ungespeicherte Änderungen verwerfen?"
            )
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
            msg.setStyleSheet(CYBER_DARK_QSS)
            if msg.exec() != QMessageBox.StandardButton.Yes:
                if hasattr(self, 'project_ctrl'):
                    self.project_ctrl.update_project_combo()
                return

        self.project_manager.set_active_project(project_name)
        self.load_active_project_state()
        self.report_ctrl.load_project(project_name)
        self.refresh_filter_pills()
        self.refresh_content()
        self.event_bus.publish(EventType.PROJECT_CHANGED, {"project_name": project_name})

    # -------------------------------------------------------------
    # Screenshots, Settings & Retranslation
    # -------------------------------------------------------------
    def trigger_screenshot(self) -> None:
        target_ip = self.var_bar.txt_target.text().strip() if hasattr(self.var_bar, 'txt_target') else ""
        self.screenshot_manager.start_capture(self.window, self.project_manager, self.loot_manager, target_ip=target_ip)

    def _on_screenshot_saved(self, loot_entry: Dict[str, Any]) -> None:
        self.save_current_project_state()
        self.switch_mode("loot")
        self.event_bus.publish(EventType.SCREENSHOT_SAVED, {"entry": loot_entry})

    def open_settings_dialog(self) -> None:
        """Opens the modular settings and options dialog."""
        dlg = SettingsDialog(self.config, parent=self.window)
        dlg.settings_applied.connect(self._on_settings_applied)
        dlg.exec()

    def _on_settings_applied(self, new_settings: Dict[str, Any]) -> None:
        if "always_on_top" in new_settings:
            is_top = bool(new_settings["always_on_top"])
            self.footer.set_always_on_top(is_top)

        if "language" in new_settings:
            self.retranslate_ui(new_settings["language"])
        else:
            self._update_footer_status()

    def _on_always_on_top_toggled(self, checked: bool) -> None:
        self.config.set("always_on_top", checked)
        flags = self.window.windowFlags()
        if checked:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        
        was_visible = self.window.isVisible()
        self.window.setWindowFlags(flags)
        if was_visible:
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()

    def retranslate_ui(self, locale_code: str = "") -> None:
        """Dynamically re-translates all HUD texts and tooltips upon language switch."""
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
        self.footer.update_hotkey_display(hotkey_raw)

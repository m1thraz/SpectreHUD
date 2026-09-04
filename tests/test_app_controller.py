"""
Comprehensive Unit Tests for AppController.
Validates central application orchestration, signal wiring, mode switching,
content refresh across all modes, dialog triggers, and project state management.
"""

import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton

app = QApplication.instance()
if app is None:
    app = QApplication([])

from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_history import ClipboardHistory
from core.project import ProjectManager
from core.event_bus import EventBus, EventType
from core.storage import PersistenceError
from ui.app_controller import AppController
from ui.clipboard_monitor import ClipboardMonitor


class TestAppController(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path)

        self.event_bus = EventBus()
        self.config = ConfigManager(config_dir=self.temp_path)
        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.project_mgr.create_project("TestBox", target_ip="10.10.10.55")
        self.project_mgr.active_project = "TestBox"

        self.snippet_mgr = SnippetManager(user_snippets_path=self.temp_path / "snippets.json")
        self.loot_mgr = LootManager(
            storage_file=self.temp_path / "loot.json", event_bus=self.event_bus
        )
        self.clip_watcher = ClipboardHistory(
            storage_file=self.temp_path / "clipboard.json", event_bus=self.event_bus
        )
        self.clipboard_monitor = ClipboardMonitor(self.clip_watcher)
        self.screenshot_mgr = MagicMock()
        self.screenshot_mgr.is_capture_available.return_value = True
        self.screenshot_mgr.capabilities.wayland = False

        self.quick_note_mgr = MagicMock()
        self.quick_note_mgr.get_all_entries.return_value = []

        # UI Panels & Widgets
        self.window = QWidget()

        self.header = MagicMock()
        self.search = MagicMock()
        self.pills_layout = QHBoxLayout()
        self.search.get_pills_layout.return_value = self.pills_layout
        self.search.get_pills_available_width.return_value = 800
        self.search.get_query.return_value = ""

        self.var_bar = MagicMock()
        self.var_bar.txt_target = MagicMock()
        self.var_bar.txt_target.text.return_value = "10.10.10.55"
        self.var_bar.txt_attacker = MagicMock()
        self.var_bar.txt_attacker.text.return_value = "10.10.14.2"
        self.var_bar.txt_port = MagicMock()
        self.var_bar.txt_port.text.return_value = "4444"
        self.var_bar.get_variables.return_value = {
            "target_ip": "10.10.10.55",
            "attacker_ip": "10.10.14.2",
            "port": "4444",
        }

        self.content = MagicMock()
        self.content_layout = QVBoxLayout()
        self.content.get_layout.return_value = self.content_layout

        self.footer = MagicMock()

        self.controller = AppController(
            window=self.window,
            header_panel=self.header,
            search_panel=self.search,
            var_bar=self.var_bar,
            content_panel=self.content,
            footer_panel=self.footer,
            config_manager=self.config,
            snippet_manager=self.snippet_mgr,
            loot_manager=self.loot_mgr,
            clipboard_history=self.clip_watcher,
            clipboard_monitor=self.clipboard_monitor,
            project_manager=self.project_mgr,
            screenshot_manager=self.screenshot_mgr,
            event_bus=self.event_bus,
            quick_note_manager=self.quick_note_mgr,
        )

    def tearDown(self):
        self.event_bus.clear()
        self.window.deleteLater()
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        self.temp_dir.cleanup()

    def test_initialization_and_active_mode(self):
        """AppController initializes coordinators, wires signals, and tracks mode."""
        self.assertEqual(self.controller.active_mode, "cheatsheet")
        self.controller.active_mode = "loot"
        self.assertEqual(self.controller.active_mode, "loot")

    def test_mode_switching_and_toggling(self):
        """switch_mode and toggle_mode update navigation coordinator and refresh UI."""
        with patch.object(self.controller, "refresh_filter_pills") as mock_pills:
            with patch.object(self.controller, "refresh_content") as mock_content:
                self.controller.switch_mode("loot")
                self.assertEqual(self.controller.active_mode, "loot")
                mock_pills.assert_called()
                mock_content.assert_called()

        with patch.object(self.controller, "refresh_filter_pills") as mock_pills:
            with patch.object(self.controller, "refresh_content") as mock_content:
                self.controller.toggle_mode()
                # Toggles to next mode in sequence
                mock_pills.assert_called()
                mock_content.assert_called()

    def test_refresh_filter_pills_across_all_modes(self):
        """refresh_filter_pills populates pills layout for each mode."""
        # 1. Cheatsheet mode
        self.controller.active_mode = "cheatsheet"
        self.controller.refresh_filter_pills()
        self.search.clear_pills.assert_called()

        # 2. Loot mode (list)
        self.controller.active_mode = "loot"
        self.controller.refresh_filter_pills()
        self.assertTrue(len(self.controller.loot_ctrl.filter_buttons) > 0)

        # 3. History mode
        self.controller.active_mode = "history"
        self.controller.refresh_filter_pills()

        # 4. Notes mode
        self.controller.active_mode = "notes"
        self.controller.refresh_filter_pills()

    def test_refresh_content_across_all_modes(self):
        """refresh_content delegates rendering to respective controller."""
        # 1. Report mode
        self.controller.active_mode = "report"
        with patch.object(self.controller.report_ctrl, "render_content", return_value=[QWidget()]):
            self.controller.refresh_content()
            self.footer.set_count.assert_called_with("Report Editor")

        # 2. Cheatsheet mode
        self.controller.active_mode = "cheatsheet"
        with patch.object(self.controller.cheatsheet_ctrl, "render_content", return_value=[QWidget(), QWidget()]):
            self.controller.refresh_content()
            self.footer.set_count.assert_called_with("2 entries")

        # 3. Loot mode (list)
        self.controller.active_mode = "loot"
        self.config.set("loot_view_mode", "list")
        with patch.object(self.controller.loot_ctrl, "render_content", return_value=[QWidget()]):
            self.controller.refresh_content()
            self.footer.set_count.assert_called_with("1 entry")

        # 4. Loot mode (board)
        self.config.set("loot_view_mode", "board")
        with patch.object(self.controller.loot_ctrl, "render_board_content", return_value=[QWidget()]):
            self.controller.refresh_content()
            self.footer.set_count.assert_called_with("1 entry")

        # 5. Notes mode
        self.controller.active_mode = "notes"
        with patch.object(self.controller.quick_note_ctrl, "render_content", return_value=[]):
            self.controller.refresh_content()
            self.footer.set_count.assert_called_with("0 entries")

        # 6. History mode
        self.controller.active_mode = "history"
        with patch.object(self.controller.history_ctrl, "render_content", return_value=[]):
            self.controller.refresh_content()
            self.footer.set_count.assert_called_with("0 entries")

    def test_on_content_copied_auto_hide(self):
        """_on_content_copied minimizes window only when auto_hide_on_copy is True."""
        with patch.object(self.window, "showMinimized") as mock_min:
            self.config.set("auto_hide_on_copy", False)
            self.controller._on_content_copied("some text")
            mock_min.assert_not_called()

            self.config.set("auto_hide_on_copy", True)
            self.controller._on_content_copied("some text")
            mock_min.assert_called_once()

    def test_toggle_loot_view(self):
        """_toggle_loot_view toggles between list and board, persisting to config."""
        self.config.set("loot_view_mode", "list")
        with patch.object(self.controller, "refresh_content"):
            with patch.object(self.controller, "refresh_filter_pills"):
                self.controller._toggle_loot_view()
                self.assertEqual(self.config.get("loot_view_mode"), "board")

                self.controller._toggle_loot_view()
                self.assertEqual(self.config.get("loot_view_mode"), "list")

    def test_toggle_loot_view_persistence_error(self):
        """_toggle_loot_view shows error dialog on persistence failure."""
        with patch.object(self.config, "set", side_effect=PersistenceError("disk read-only")):
            with patch("ui.app_controller.QMessageBox.critical") as mock_crit:
                self.controller._toggle_loot_view()
                mock_crit.assert_called_once()

    def test_on_add_button_clicked_routing(self):
        """_on_add_button_clicked routes based on active_mode."""
        # 1. Cheatsheet
        self.controller.active_mode = "cheatsheet"
        with patch.object(self.controller.cheatsheet_ctrl, "open_add_dialog", return_value=True) as mock_add:
            with patch.object(self.controller, "_on_data_updated") as mock_update:
                self.controller._on_add_button_clicked()
                mock_add.assert_called_once()
                mock_update.assert_called_once()

        # 2. Loot
        self.controller.active_mode = "loot"
        with patch.object(self.controller.loot_ctrl, "open_add_dialog", return_value=True) as mock_add:
            with patch.object(self.controller, "_on_loot_data_updated") as mock_update:
                self.controller._on_add_button_clicked()
                mock_add.assert_called_once()
                mock_update.assert_called_once()

        # 3. Notes / History
        self.controller.active_mode = "notes"
        with patch.object(self.controller.quick_note_ctrl, "show_popup") as mock_popup:
            self.controller._on_add_button_clicked()
            mock_popup.assert_called_once()

    def test_edit_callbacks(self):
        """Edit callbacks delegate to respective controller and refresh data."""
        sample_entry = {"id": "test_1", "title": "Test"}

        # Loot edit
        with patch.object(self.controller.loot_ctrl, "open_edit_dialog", return_value=True):
            with patch.object(self.controller, "_on_loot_data_updated") as mock_up:
                self.controller._on_edit_loot_requested(sample_entry)
                mock_up.assert_called_once()

        # History edit
        with patch.object(self.controller.history_ctrl, "open_edit_dialog", return_value=True):
            with patch.object(self.controller, "_on_history_data_updated") as mock_up:
                self.controller._on_edit_history_requested(sample_entry)
                mock_up.assert_called_once()

        # Note edit
        with patch.object(self.controller.quick_note_ctrl, "open_edit_dialog", return_value=True):
            with patch.object(self.controller, "_on_notes_updated") as mock_up:
                self.controller._on_edit_note_requested(sample_entry)
                mock_up.assert_called_once()

    def test_delete_and_clear_callbacks(self):
        """Snippet and loot deletion callbacks delegate and refresh."""
        with patch.object(self.controller.cheatsheet_ctrl, "delete_snippet") as mock_del:
            with patch.object(self.controller, "_on_data_updated") as mock_up:
                self.controller._on_snippet_deleted("snip_123")
                mock_del.assert_called_with("snip_123")
                mock_up.assert_called_once()

        with patch.object(self.controller.loot_ctrl, "delete_loot") as mock_del:
            with patch.object(self.controller, "_on_loot_data_updated") as mock_up:
                self.controller._on_loot_deleted("loot_123")
                mock_del.assert_called_with("loot_123")
                mock_up.assert_called_once()

        with patch.object(self.controller.loot_ctrl, "clear_loot", return_value=True) as mock_clr:
            with patch.object(self.controller, "_on_loot_data_updated") as mock_up:
                self.controller._clear_loot()
                mock_clr.assert_called_once()
                mock_up.assert_called_once()

        with patch.object(self.controller.quick_note_ctrl, "clear_all_notes", return_value=True) as mock_clr:
            with patch.object(self.controller, "_update_notes_badge"):
                with patch.object(self.controller, "refresh_filter_pills") as mock_rfp:
                    with patch.object(self.controller, "refresh_content") as mock_rfc:
                        self.controller.active_mode = "notes"
                        self.controller._clear_notes()
                        mock_clr.assert_called_once()
                        mock_rfp.assert_called_once()
                        mock_rfc.assert_called_once()

    def test_quick_actions(self):
        """Quick note, quick IP, and quick loot triggers operate correctly."""
        # Quick note
        with patch.object(self.controller.quick_note_ctrl, "show_popup") as mock_pop:
            self.controller.trigger_quick_note()
            mock_pop.assert_called_once()

        # Quick loot
        with patch.object(self.controller.loot_ctrl, "open_add_dialog") as mock_add:
            self.controller.trigger_quick_loot()
            mock_add.assert_called_once_with(
                parent_widget=None,
                target_ip="10.10.10.55",
                modal=False,
                on_accepted=unittest.mock.ANY,
            )

        # Quick IP
        with patch("ui.quick_ip_popup.QuickIpPopup") as MockPopup:
            mock_inst = MagicMock()
            MockPopup.return_value = mock_inst
            self.controller.trigger_quick_ip()
            mock_inst.show_at_cursor.assert_called_once()

    def test_quick_ip_changes_propagate_to_var_bar(self):
        """_on_quick_ip_target_changed and attacker changed update var_bar."""
        self.controller._on_quick_ip_target_changed("192.168.1.50")
        self.var_bar.txt_target.setText.assert_called_with("192.168.1.50")

        self.controller._on_quick_ip_attacker_changed("192.168.1.100")
        self.var_bar.txt_attacker.setText.assert_called_with("192.168.1.100")

    def test_project_state_load_and_save(self):
        """load_active_project_state and save_current_project_state coordinate session."""
        with patch.object(self.controller.workspace_coord, "load_active_project_session", return_value={"target_ip": "10.10.10.99"}):
            self.controller.load_active_project_state()
            self.header.set_project_title.assert_called_with("TestBox")
            self.var_bar.set_variables.assert_called_with({"target_ip": "10.10.10.99"})

        with patch.object(self.controller.workspace_coord, "save_current_project_session", return_value=True) as mock_save:
            res = self.controller.save_current_project_state()
            self.assertTrue(res)
            mock_save.assert_called_once()

    def test_switch_to_project(self):
        """switch_to_project delegates to workspace_coord and updates state."""
        with patch.object(self.controller.workspace_coord, "switch_to_project") as mock_sw:
            self.controller.switch_to_project("NewBox")
            mock_sw.assert_called_once()
            # Invoke the on_success_callback passed to workspace_coord
            callback = mock_sw.call_args[1]["on_success_callback"]
            with patch.object(self.controller, "load_active_project_state") as mock_load:
                with patch.object(self.controller, "refresh_content") as mock_content:
                    callback("NewBox")
                    mock_load.assert_called_once()
                    mock_content.assert_called_once()

    def test_screenshot_trigger_and_saved(self):
        """trigger_screenshot initiates capture, _on_screenshot_saved commits and switches mode."""
        # Available capture
        self.controller.trigger_screenshot()
        self.screenshot_mgr.start_capture.assert_called_once()

        # Unavailable capture shows warning
        self.screenshot_mgr.is_capture_available.return_value = False
        with patch("PyQt6.QtWidgets.QToolTip.showText") as mock_tt:
            with patch("ui.app_controller.logger.warning") as mock_log:
                # 1. Non-wayland
                self.screenshot_mgr.capabilities.wayland = False
                self.controller.trigger_screenshot()
                mock_log.assert_called()

                # 2. Wayland
                self.screenshot_mgr.capabilities.wayland = True
                self.controller.trigger_screenshot()
                mock_tt.assert_called()

        # Screenshot saved commit
        loot_entry = {"id": "loot_sc_1", "type": "screenshot", "title": "Sc"}
        with patch.object(self.controller.screenshot_transaction, "commit", return_value=MagicMock(ok=True)):
            with patch.object(self.controller, "switch_mode") as mock_sw:
                self.controller._on_screenshot_saved(loot_entry)
                mock_sw.assert_called_with("loot")

    def test_settings_dialog_and_always_on_top(self):
        """open_settings_dialog emits restart on theme change, always_on_top sets flags."""
        with patch("ui.app_controller.SettingsDialog") as MockSettings:
            dlg = MagicMock()
            dlg.exec.return_value = 1
            MockSettings.return_value = dlg

            restarts = []
            self.controller.restart_requested.connect(lambda: restarts.append(True))

            # Trigger apply callback with theme change
            def fake_exec():
                connect_calls = [c[0][0] for c in dlg.settings_applied.connect.call_args_list]
                for cb in connect_calls:
                    cb({"theme": "cyber_light"})
                return 1

            dlg.exec.side_effect = fake_exec
            self.controller.open_settings_dialog()
            self.assertEqual(len(restarts), 1)

        # Always on top
        with patch.object(self.window, "setWindowFlags") as mock_flags:
            self.controller._on_always_on_top_toggled(True)
            self.assertTrue(self.config.get("always_on_top"))
            mock_flags.assert_called()

    def test_retranslate_ui_and_footer(self):
        """retranslate_ui updates header, search, footer, and publishes event."""
        languages = []
        self.event_bus.subscribe(EventType.LANGUAGE_CHANGED, lambda d: languages.append(d["locale"]))

        self.controller.retranslate_ui("de")
        self.header.retranslate.assert_called()
        self.var_bar.retranslate.assert_called()
        self.footer.update_hotkey_display.assert_called()
        self.assertEqual(languages, ["de"])

    def test_auxiliary_orchestration_callbacks(self):
        """Covers filter selectors, project dialogs, event handlers, and visibility restore."""
        # 1. Pause history toggle
        with patch.object(self.controller.clipboard_coord, "toggle_pause") as mock_pause:
            self.controller._toggle_pause_history()
            mock_pause.assert_called_once()

        # 2. Pills width changed
        self.controller.active_mode = "cheatsheet"
        with patch.object(self.controller.cheatsheet_ctrl, "update_pills_width") as mock_width:
            self.controller._on_pills_width_changed(500)
            mock_width.assert_called_once()

        # 3. Filter selections & variables changed
        with patch.object(self.controller, "refresh_content") as mock_rc:
            with patch.object(self.controller.cheatsheet_ctrl, "select_category"):
                self.controller._select_category("recon")
            with patch.object(self.controller.loot_ctrl, "select_loot_type"):
                self.controller._select_loot_type("credentials")
            with patch.object(self.controller.quick_note_ctrl, "select_filter"):
                self.controller._select_notes_filter("flag")
            with patch.object(self.controller.history_ctrl, "select_history_filter"):
                self.controller._select_history_filter("recent")
            self.assertEqual(mock_rc.call_count, 4)

        with patch.object(self.controller.cheatsheet_ctrl, "update_variables") as mock_uv:
            self.controller._on_variables_changed({"target_ip": "1.2.3.4"})
            mock_uv.assert_called_once()

        # 4. Export loot & move loot category
        with patch.object(self.controller.loot_ctrl, "export_entry_to_file_with_feedback") as mock_exp:
            self.controller._on_export_loot_entry("loot_abc")
            mock_exp.assert_called_with("loot_abc", self.window)

        with patch.object(self.controller.loot_ctrl, "move_entry_to_category", return_value=True) as mock_mov:
            res = self.controller._on_move_loot_category("loot_abc", "recon", 1)
            self.assertTrue(res)
            mock_mov.assert_called_with("loot_abc", "recon", 1, self.window)

        # 5. Clipboard entry added
        with patch.object(self.controller.clipboard_coord, "on_clipboard_entry_added") as mock_cb:
            self.controller._on_clipboard_entry_added({"text": "copied text"})
            mock_cb.assert_called_once_with({"text": "copied text"})

        # 6. Data updated callbacks
        with patch.object(self.controller, "refresh_filter_pills") as mock_rfp:
            with patch.object(self.controller, "refresh_content") as mock_rfc:
                self.controller._on_data_updated()
                mock_rfp.assert_called_once()
                mock_rfc.assert_called_once()

        with patch.object(self.controller, "save_current_project_state") as mock_save:
            with patch.object(self.controller, "refresh_filter_pills"):
                with patch.object(self.controller, "refresh_content"):
                    self.controller._on_loot_data_updated()
                    mock_save.assert_called_once()

                    self.controller.active_mode = "history"
                    self.controller._on_history_data_updated()
                    self.assertEqual(mock_save.call_count, 2)

        # 7. Project menu & dialogs
        btn_anchor = QPushButton()
        with patch.object(self.controller.workspace_coord, "show_project_menu") as mock_menu:
            self.controller._show_project_menu(btn_anchor)
            mock_menu.assert_called_once()

        with patch.object(self.controller.workspace_coord, "open_new_project_dialog") as mock_new_proj:
            self.controller._open_new_project_dialog()
            mock_new_proj.assert_called_once()

        # 8. Failed screenshot transaction commit
        with patch.object(self.controller.screenshot_transaction, "commit", return_value=MagicMock(ok=False)):
            with patch.object(self.controller, "switch_mode") as mock_sw:
                self.controller._on_screenshot_saved({"id": "sc"})
                mock_sw.assert_not_called()

        # 9. Always on top when window was visible
        with patch.object(self.window, "isVisible", return_value=True):
            with patch.object(self.window, "show") as mock_show:
                with patch.object(self.window, "raise_") as mock_raise:
                    with patch.object(self.window, "activateWindow") as mock_act:
                        self.controller._on_always_on_top_toggled(False)
                        mock_show.assert_called_once()
                        mock_raise.assert_called_once()
                        mock_act.assert_called_once()


if __name__ == "__main__":
    unittest.main()

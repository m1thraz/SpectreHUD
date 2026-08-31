import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from core.config import ConfigManager
from ui.settings_dialog import (
    SettingsDialog, HotkeySettingsPage, 
    LanguageSettingsPage, GeneralSettingsPage, AppearanceSettingsPage
)

app = QApplication.instance() or QApplication([])

class TestSettingsDialog(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        workspace_dir = temp_path / "projects"
        workspace_dir.mkdir()
        self.config_manager = ConfigManager(config_dir=temp_path)
        self.config_manager.set("workspace_dir", str(workspace_dir))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_hotkey_page_get_settings_and_reset(self):
        page = HotkeySettingsPage(self.config_manager)
        page.combo_toggle.setCurrentIndex(2) # <ctrl>+<alt>+s
        page.combo_quit.setCurrentIndex(1) # <ctrl>+<alt>+q
        
        settings = page.get_settings()
        self.assertEqual(settings["hotkey"], "<ctrl>+<alt>+s")
        self.assertEqual(settings["quit_hotkey"], "<ctrl>+<alt>+q")
        
        page._reset_defaults()
        self.assertEqual(page.combo_toggle.currentData(), "<ctrl>+<cmd>+<")
        self.assertEqual(page.combo_quit.currentData(), "<ctrl>+<cmd>+q")

    def test_language_page_get_settings(self):
        page = LanguageSettingsPage(self.config_manager)
        page.combo_lang.setCurrentIndex(1) # en
        
        settings = page.get_settings()
        self.assertEqual(settings["language"], "en")
        self.assertEqual(settings["time_format"], "24h")

    def test_general_page_get_settings(self):
        page = GeneralSettingsPage(self.config_manager)
        page.chk_always_on_top.setChecked(False)
        page.chk_auto_hide.setChecked(True)
        page.txt_default_target.setText("192.168.1.100")
        
        settings = page.get_settings()
        self.assertFalse(settings["always_on_top"])
        self.assertTrue(settings["auto_hide_on_copy"])
        self.assertEqual(settings["target_ip"], "192.168.1.100")
        self.assertNotIn("theme", settings)
        self.assertNotIn("loot_view_mode", settings)

    def test_appearance_page_get_settings(self):
        page = AppearanceSettingsPage(self.config_manager)
        page.combo_ui_font.setCurrentIndex(1)
        page.combo_code_font.setCurrentIndex(3)
        page.combo_report_font.setCurrentIndex(3)

        settings = page.get_settings()
        self.assertNotIn("loot_view_mode", settings)
        self.assertEqual(settings["ui_font"], "inter")
        self.assertEqual(settings["code_font"], "jetbrains_mono")
        self.assertEqual(settings["report_font"], "georgia")
        self.assertEqual(settings["theme"], "cyber_dark")

    def test_appearance_page_has_no_redundant_loot_view_switch(self):
        page = AppearanceSettingsPage(self.config_manager)

        self.assertFalse(hasattr(page, "chk_loot_board"))
        self.assertNotIn("loot_view_mode", page.get_settings())

    def test_unavailable_fonts_are_marked_and_disabled(self):
        with patch(
            "ui.settings_dialog.QFontDatabase.families",
            return_value=["Segoe UI", "Consolas", "Arial", "Georgia"],
        ):
            page = AppearanceSettingsPage(self.config_manager)

        inter_index = page.combo_ui_font.findData("inter")
        jetbrains_index = page.combo_code_font.findData("jetbrains_mono")
        self.assertIn("install", page.combo_ui_font.itemText(inter_index).casefold())
        self.assertFalse(page.combo_ui_font.model().item(inter_index).isEnabled())
        self.assertIn("install", page.combo_code_font.itemText(jetbrains_index).casefold())
        self.assertFalse(page.combo_code_font.model().item(jetbrains_index).isEnabled())

    def test_settings_dialog_exposes_separate_appearance_tab(self):
        dlg = SettingsDialog(self.config_manager)

        self.assertEqual(dlg.stack.count(), 4)
        dlg.btn_nav_appearance.click()
        self.assertEqual(dlg.stack.currentWidget(), dlg.page_appearance)
        self.assertEqual(dlg.btn_nav_appearance.property("class"), "SettingsNavBtnActive")
        self.assertEqual(dlg.btn_nav_general.property("class"), "SettingsNavBtn")
        dlg.close()

    def test_settings_dialog_save_and_apply(self):
        dlg = SettingsDialog(self.config_manager)
        dlg.switch_page(1)
        self.assertEqual(dlg.stack.currentIndex(), 1)
        
        dlg.page_hotkeys.combo_toggle.setCurrentIndex(1) # <ctrl>+<cmd>+<space>
        dlg.page_hotkeys.combo_quit.setCurrentIndex(2) # <ctrl>+<shift>+q
        
        received_signal = []
        dlg.settings_applied.connect(lambda s: received_signal.append(s))
        
        dlg._on_save_settings()
        
        self.assertEqual(len(received_signal), 1)
        self.assertEqual(received_signal[0]["hotkey"], "<ctrl>+<cmd>+<space>")
        self.assertEqual(received_signal[0]["quit_hotkey"], "<ctrl>+<shift>+q")
        self.assertEqual(self.config_manager.get("hotkey"), "<ctrl>+<cmd>+<space>")
        self.assertEqual(self.config_manager.get("quit_hotkey"), "<ctrl>+<shift>+q")
        self.assertEqual(self.config_manager.get("theme"), "cyber_dark")
        dlg.close()

    def test_settings_dialog_defers_workspace_persistence_until_runtime_switch(self):
        """The dialog must not commit a workspace before AppController accepts it."""
        old_workspace = self.config_manager.get("workspace_dir")
        new_workspace = Path(self.temp_dir.name) / "new_workspace"
        new_workspace.mkdir()
        dlg = SettingsDialog(self.config_manager)
        emitted_settings = []
        dlg.settings_applied.connect(emitted_settings.append)
        dlg.page_general.txt_workspace.setText(str(new_workspace))

        dlg._on_save_settings()

        self.assertEqual(self.config_manager.get("workspace_dir"), old_workspace)
        self.assertEqual(emitted_settings[0]["workspace_dir"], str(new_workspace))
        dlg.close()

if __name__ == '__main__':
    unittest.main()

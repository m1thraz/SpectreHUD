import unittest
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from core.config import ConfigManager
from ui.settings_dialog import (
    SettingsDialog, HotkeySettingsPage, 
    LanguageSettingsPage, GeneralSettingsPage
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
        dlg.close()

if __name__ == '__main__':
    unittest.main()

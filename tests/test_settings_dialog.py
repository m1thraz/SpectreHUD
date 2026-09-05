import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from core.config import ConfigManager
from ui.settings_dialog import (
    SettingsDialog,
    HotkeySettingsPage,
    LanguageSettingsPage,
    GeneralSettingsPage,
    AppearanceSettingsPage,
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
        page.combo_toggle.setCurrentIndex(2)  # <ctrl>+<alt>+s
        page.combo_quit.setCurrentIndex(0)  # <ctrl>+<alt>+q

        settings = page.get_settings()
        self.assertEqual(settings["hotkey"], "<ctrl>+<alt>+s")
        self.assertEqual(settings["quit_hotkey"], "<ctrl>+<alt>+q")

        page._reset_defaults()
        self.assertEqual(page.combo_toggle.currentData(), "<ctrl>+<alt>+h")
        self.assertEqual(page.combo_quick_ip.currentData(), "<ctrl>+<alt>+i")
        self.assertEqual(page.combo_quit.currentData(), "<ctrl>+<alt>+q")

    def test_language_page_get_settings(self):
        page = LanguageSettingsPage(self.config_manager)
        page.combo_lang.setCurrentIndex(1)  # en

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
        page.combo_ui_font.setCurrentIndex(page.combo_ui_font.findData("inter"))
        page.combo_code_font.setCurrentIndex(page.combo_code_font.findData("jetbrains_mono"))
        page.combo_report_font.setCurrentIndex(page.combo_report_font.findData("georgia"))
        page.slider_hud_transparency.setValue(20)
        page.spin_report_transparency.setValue(10)
        page.slider_bleed_through.setValue(12)

        settings = page.get_settings()
        self.assertNotIn("loot_view_mode", settings)
        self.assertEqual(settings["ui_font"], "inter")
        self.assertEqual(settings["code_font"], "jetbrains_mono")
        self.assertEqual(settings["report_font"], "georgia")
        self.assertEqual(settings["theme"], "cyber_dark")
        self.assertEqual(settings["hud_transparency"], 20)
        self.assertEqual(settings["report_transparency"], 10)
        self.assertEqual(settings["bleed_through"], 12)

    def test_appearance_transparency_controls_are_independent_and_bounded(self):
        page = AppearanceSettingsPage(self.config_manager)

        self.assertEqual(page.slider_hud_transparency.minimum(), 0)
        self.assertEqual(page.slider_hud_transparency.maximum(), 30)
        self.assertEqual(page.slider_hud_transparency.value(), 5)
        self.assertEqual(page.slider_report_transparency.value(), 0)
        self.assertEqual(page.slider_bleed_through.value(), 0)
        self.assertEqual(page.slider_bleed_through.minimum(), 0)
        self.assertEqual(page.slider_bleed_through.maximum(), 30)

        page.spin_hud_transparency.setValue(17)
        self.assertEqual(page.slider_hud_transparency.value(), 17)
        self.assertEqual(page.slider_report_transparency.value(), 0)
        self.assertEqual(page.slider_bleed_through.value(), 0)

        page.slider_report_transparency.setValue(9)
        self.assertEqual(page.spin_report_transparency.value(), 9)
        self.assertEqual(page.slider_hud_transparency.value(), 17)
        self.assertEqual(page.slider_bleed_through.value(), 0)

        page.spin_bleed_through.setValue(25)
        self.assertEqual(page.slider_bleed_through.value(), 25)
        self.assertEqual(page.slider_hud_transparency.value(), 17)
        self.assertEqual(page.slider_report_transparency.value(), 9)

    def test_appearance_page_has_no_redundant_loot_view_switch(self):
        page = AppearanceSettingsPage(self.config_manager)

        self.assertFalse(hasattr(page, "chk_loot_board"))
        self.assertNotIn("loot_view_mode", page.get_settings())

    def test_appearance_theme_dropdown_shows_only_theme_names(self):
        page = AppearanceSettingsPage(self.config_manager)
        themes_by_id = {theme["id"]: theme for theme in page.theme_loader.list_themes()}

        for index in range(page.combo_theme.count()):
            theme_id = page.combo_theme.itemData(index)
            self.assertEqual(
                page.combo_theme.itemText(index),
                themes_by_id[theme_id]["name"],
            )

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

        dlg.page_hotkeys.combo_toggle.setCurrentIndex(1)  # <ctrl>+<cmd>+<space>
        dlg.page_hotkeys.combo_quit.setCurrentIndex(2)  # <ctrl>+<shift>+q

        received_signal = []
        dlg.settings_applied.connect(lambda s: received_signal.append(s))

        dlg._on_save_settings()

        self.assertEqual(len(received_signal), 1)
        self.assertEqual(received_signal[0]["hotkey"], "<ctrl>+<cmd>+<space>")
        self.assertEqual(received_signal[0]["quit_hotkey"], "<ctrl>+<shift>+q")
        self.assertEqual(self.config_manager.get("hotkey"), "<ctrl>+<cmd>+<space>")
        self.assertEqual(self.config_manager.get("quit_hotkey"), "<ctrl>+<shift>+q")
        self.assertEqual(self.config_manager.get("theme"), "cyber_dark")
        self.assertEqual(self.config_manager.get("hud_transparency"), 5)
        self.assertEqual(self.config_manager.get("report_transparency"), 0)
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

    def test_hotkey_page_renders_unavailable_notice_on_wayland(self):
        """Ticket 24: HotkeySettingsPage displays notice when global hotkeys are unavailable."""
        from core.platform import PlatformCapabilities
        from PyQt6.QtWidgets import QLabel

        wayland_caps = PlatformCapabilities(
            system="linux",
            global_hotkeys=False,
            screen_capture=False,
            wayland=True,
            x11=False,
        )
        page = HotkeySettingsPage(self.config_manager, capabilities=wayland_caps)
        labels = [lbl.text() for lbl in page.findChildren(QLabel)]
        self.assertTrue(any("Wayland" in text or "Globale" in text or "Global" in text for text in labels))

    def test_settings_dialog_applies_transparency_only_on_save(self):
        """Transparency sliders update settings applied only upon saving."""
        dlg = SettingsDialog(self.config_manager)
        applied = []
        dlg.settings_applied.connect(applied.append)

        dlg.page_appearance.slider_bleed_through.setValue(22)
        dlg.page_appearance.slider_hud_transparency.setValue(14)
        dlg.page_appearance.slider_report_transparency.setValue(8)

        # No settings applied yet before saving
        self.assertEqual(len(applied), 0)

        dlg._on_save_settings()

        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["bleed_through"], 22)
        self.assertEqual(applied[0]["hud_transparency"], 14)
        self.assertEqual(applied[0]["report_transparency"], 8)
        self.assertEqual(self.config_manager.get("bleed_through"), 22)

        dlg.close()


if __name__ == "__main__":
    unittest.main()


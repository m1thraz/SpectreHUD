import unittest
import tempfile
from pathlib import Path
import pytest
from core.config import ConfigManager, DEFAULT_CONFIG
from core.i18n import set_locale, DEFAULT_LOCALE
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project import ProjectManager


class TestI18nSnippets(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.config_dir = self.temp_path / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.user_snippets_file = self.config_dir / "user_snippets.json"
        self.favorites_file = self.config_dir / "user_favorites.json"
        self.projects_dir = self.temp_path / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.loot_file = self.temp_path / "loot.json"
        self.clip_file = self.temp_path / "history.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_language_is_english(self):
        self.assertEqual(DEFAULT_CONFIG["language"], "en")
        self.assertEqual(DEFAULT_LOCALE, "en")

    def test_cheatsheet_category_buttons_follow_active_locale(self):
        from ui.controllers.cheatsheet_controller import _category_short_name

        try:
            set_locale("en")
            self.assertEqual(_category_short_name("network_scanning"), "Network")
            self.assertEqual(_category_short_name("custom_snippets"), "Custom")

            set_locale("de")
            self.assertEqual(_category_short_name("network_scanning"), "Netzwerk")
            self.assertEqual(_category_short_name("custom_snippets"), "Eigene")
        finally:
            set_locale("en")

    def test_snippet_manager_language_switching(self):
        # 1. Initialize SnippetManager with English
        mgr = SnippetManager(
            user_snippets_path=self.user_snippets_file,
            favorites_path=self.favorites_file,
            language="en",
        )
        self.assertEqual(mgr.language, "en")
        self.assertIn(" - EN", str(mgr.default_snippets_path))

        # Add a custom snippet and favorite
        custom_snip = mgr.add_custom_snippet(
            title="My Custom Test Snippet",
            template="echo 'test'",
            description="A custom snippet",
            category="Custom Notes & Snippets",
            tags=["test"],
        )
        mgr.toggle_favorite(custom_snip["id"])
        self.assertTrue(mgr.is_favorite(custom_snip["id"]))

        en_snippets_count = len(mgr.snippets)
        self.assertGreater(en_snippets_count, 0)

        # 2. Switch to German
        mgr.set_language("de")
        self.assertEqual(mgr.language, "de")
        self.assertNotIn(" - EN", str(mgr.default_snippets_path))

        # Custom snippet and favorite MUST be preserved!
        self.assertTrue(mgr.is_favorite(custom_snip["id"]))
        custom_found = [s for s in mgr.snippets if s.get("id") == custom_snip["id"]]
        self.assertEqual(len(custom_found), 1)

        # 3. Switch back to English
        mgr.set_language("en")
        self.assertEqual(mgr.language, "en")
        self.assertIn(" - EN", str(mgr.default_snippets_path))
        self.assertTrue(mgr.is_favorite(custom_snip["id"]))

    @pytest.mark.integration
    def test_main_window_i18n_runtime_switch(self):
        from PyQt6.QtWidgets import QApplication
        from ui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])

        cfg_mgr = ConfigManager(config_dir=self.config_dir)
        cfg_mgr.set("language", "en")

        snip_mgr = SnippetManager(
            user_snippets_path=self.user_snippets_file,
            favorites_path=self.favorites_file,
            language="en",
        )
        loot_mgr = LootManager(storage_file=self.loot_file)
        clip_watcher = ClipboardWatcher(storage_file=self.clip_file)
        proj_mgr = ProjectManager(base_dir=self.projects_dir)

        window = MainWindow(
            config_manager=cfg_mgr,
            snippet_manager=snip_mgr,
            loot_manager=loot_mgr,
            clipboard_watcher=clip_watcher,
            project_manager=proj_mgr,
        )

        # Initial state should be English
        self.assertEqual(window.snippet_manager.language, "en")
        self.assertIn("Search", window.search_panel.search_bar.txt_search.placeholderText())

        # Switch to German
        set_locale("de")
        self.assertEqual(window.snippet_manager.language, "de")
        self.assertIn("suchen", window.search_panel.search_bar.txt_search.placeholderText().lower())

        # Switch back to English
        set_locale("en")
        self.assertEqual(window.snippet_manager.language, "en")
        self.assertIn("Search", window.search_panel.search_bar.txt_search.placeholderText())

        window.close()


if __name__ == "__main__":
    unittest.main()

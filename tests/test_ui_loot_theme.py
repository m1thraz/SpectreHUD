import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QPushButton
from core.config import ConfigManager
from core.snippets.manager import SnippetManager
from core.loot.manager import LootManager
from core.clipboard_history import ClipboardHistory
from core.project import ProjectManager
from tests.window_factory import create_main_window


class TestUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.temp_path = Path(self.temp_dir.name)

        # Set environment variables as fallback safety shield
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path / "config")
        os.environ["SPECTRE_PROJECTS_DIR"] = str(self.temp_path / "projects")

        self.config_dir = self.temp_path / "config"
        self.custom_snippets_path = self.temp_path / "config" / "user_snippets.json"
        self.projects_dir = self.temp_path / "projects"
        self.loot_file = self.temp_path / "config" / "loot.json"
        self.clip_file = self.temp_path / "config" / "clip.json"

    def tearDown(self):
        # Reset environment safety shield
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        os.environ.pop("SPECTRE_PROJECTS_DIR", None)
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    @pytest.mark.integration
    def test_loot_grouped_by_category_with_headers(self):
        """Verifies that loot view displays section headers only for non-empty categories in CATEGORIES order."""
        from PyQt6.QtWidgets import QLabel
        from ui.loot_card import LootCard

        config_manager = ConfigManager(config_dir=self.config_dir)
        snippet_manager = SnippetManager(user_snippets_path=self.custom_snippets_path)
        project_manager = ProjectManager(base_dir=self.projects_dir)
        loot_manager = LootManager(storage_file=self.loot_file)
        clipboard_watcher = ClipboardHistory(storage_file=self.clip_file)

        window = create_main_window(
            config_manager=config_manager,
            snippet_manager=snippet_manager,
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            project_manager=project_manager,
        )

        # Add entries into exactly 3 categories (recon, access, misc)
        loot_manager.add_entry("directory", "Web Root", "http://10.10.10.10/", category="recon")
        loot_manager.add_entry("credentials", "Admin SSH", "root:secret", category="access")
        loot_manager.add_entry("note", "General Hint", "Check port 8080", category="misc")

        window.app.switch_mode("loot")

        def get_current_headers():
            return [
                window.content_panel.content_layout.itemAt(i).widget()
                for i in range(window.content_panel.content_layout.count())
                if isinstance(window.content_panel.content_layout.itemAt(i).widget(), QLabel)
                and window.content_panel.content_layout.itemAt(i).widget().property("class")
                == "LootSectionHeader"
            ]

        def get_current_cards():
            return [
                window.content_panel.content_layout.itemAt(i).widget()
                for i in range(window.content_panel.content_layout.count())
                if isinstance(window.content_panel.content_layout.itemAt(i).widget(), LootCard)
            ]

        headers = get_current_headers()

        # 1. Exactly 3 headers for 3 non-empty categories
        self.assertEqual(len(headers), 3)

        # 2. Ordered according to CATEGORIES (Recon -> Access -> Misc)
        self.assertIn("Reconnaissance", headers[0].text())
        self.assertIn("Initial Access", headers[1].text())
        self.assertIn("Miscellaneous", headers[2].text())

        # 3. Exactly 3 LootCards rendered
        cards = get_current_cards()
        self.assertEqual(len(cards), 3)

        # 4. Filter by credentials: only access category header should remain
        window.app._select_loot_type("credentials")
        filtered_headers = get_current_headers()
        self.assertEqual(len(filtered_headers), 1)
        self.assertIn("Initial Access", filtered_headers[0].text())

        # 5. Reset filter to 'all' -> all 3 headers return
        window.app._select_loot_type("all")
        reset_headers = get_current_headers()
        self.assertEqual(len(reset_headers), 3)

        window.close()

    @pytest.mark.integration
    def test_loot_board_view_uses_configured_alternate_presentation(self):
        from ui.loot_board import LootBoard

        config_manager = ConfigManager(config_dir=self.config_dir)
        config_manager.set("loot_view_mode", "board")
        snippet_manager = SnippetManager(user_snippets_path=self.custom_snippets_path)
        project_manager = ProjectManager(base_dir=self.projects_dir)
        loot_manager = LootManager(storage_file=self.loot_file)
        clipboard_watcher = ClipboardHistory(storage_file=self.clip_file)

        window = create_main_window(
            config_manager=config_manager,
            snippet_manager=snippet_manager,
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            project_manager=project_manager,
        )
        loot_manager.add_entry("note", "Board item", "visible in a column", category="access")
        window.app.switch_mode("loot")

        self.assertEqual(len(window.cards), 1)
        self.assertIsInstance(window.cards[0], LootBoard)
        self.assertEqual(
            window.cards[0].columns["access"].entry_ids, [loot_manager.get_entries()[0]["id"]]
        )
        window.close()

    @pytest.mark.integration
    def test_loot_view_button_toggles_and_persists_both_presentations(self):
        from ui.loot_board import LootBoard

        config_manager = ConfigManager(config_dir=self.config_dir)
        window = create_main_window(
            config_manager=config_manager,
            snippet_manager=SnippetManager(user_snippets_path=self.custom_snippets_path),
            loot_manager=LootManager(storage_file=self.loot_file),
            clipboard_watcher=ClipboardHistory(storage_file=self.clip_file),
            project_manager=ProjectManager(base_dir=self.projects_dir),
        )
        window.app.switch_mode("loot")

        button = window.search_panel.pills_frame.findChild(QPushButton, "LootViewToggleButton")
        self.assertIsNotNone(button)
        self.assertEqual(config_manager.get("loot_view_mode"), "list")

        button.click()
        self.assertEqual(config_manager.get("loot_view_mode"), "board")
        self.assertEqual(len(window.cards), 1)
        self.assertIsInstance(window.cards[0], LootBoard)

        button = window.search_panel.pills_frame.findChild(QPushButton, "LootViewToggleButton")
        self.assertIsNotNone(button)
        button.click()
        self.assertEqual(config_manager.get("loot_view_mode"), "list")
        self.assertFalse(any(isinstance(card, LootBoard) for card in window.cards))
        window.close()

    @pytest.mark.integration
    def test_loot_export_tooltip_uses_active_english_locale(self):
        window = create_main_window(
            config_manager=ConfigManager(config_dir=self.config_dir),
            snippet_manager=SnippetManager(user_snippets_path=self.custom_snippets_path),
            loot_manager=LootManager(storage_file=self.loot_file),
            clipboard_watcher=ClipboardHistory(storage_file=self.clip_file),
            project_manager=ProjectManager(base_dir=self.projects_dir),
        )
        window.app.switch_mode("loot")

        button = window.search_panel.pills_frame.findChild(QPushButton, "LootExportButton")
        self.assertIsNotNone(button)
        self.assertEqual(
            button.toolTip(),
            "Creates a new copy based on current session loot",
        )
        window.close()

    @pytest.mark.integration
    def test_theme_change_requests_restart_only_after_settings_dialog_closes(self):
        config_manager = ConfigManager(config_dir=self.config_dir)
        window = create_main_window(
            config_manager=config_manager,
            snippet_manager=SnippetManager(user_snippets_path=self.custom_snippets_path),
            loot_manager=LootManager(storage_file=self.loot_file),
            clipboard_watcher=ClipboardHistory(storage_file=self.clip_file),
            project_manager=ProjectManager(base_dir=self.projects_dir),
        )
        callbacks = []
        lifecycle = []
        window.app.restart_requested.connect(lambda: lifecycle.append("restart"))

        with patch("ui.app_controller.SettingsDialog") as dialog_class:
            dialog = dialog_class.return_value
            dialog.settings_applied.connect.side_effect = callbacks.append

            def execute_dialog():
                config_manager.set("theme", "nord")
                callbacks[0]({"theme": "nord"})
                lifecycle.append("dialog_closed")
                return 1

            dialog.exec.side_effect = execute_dialog
            window.app.open_settings_dialog()

        self.assertEqual(lifecycle, ["dialog_closed", "restart"])
        window.close()

    @pytest.mark.integration
    def test_unchanged_theme_does_not_request_restart(self):
        config_manager = ConfigManager(config_dir=self.config_dir)
        window = create_main_window(
            config_manager=config_manager,
            snippet_manager=SnippetManager(user_snippets_path=self.custom_snippets_path),
            loot_manager=LootManager(storage_file=self.loot_file),
            clipboard_watcher=ClipboardHistory(storage_file=self.clip_file),
            project_manager=ProjectManager(base_dir=self.projects_dir),
        )
        callbacks = []
        restarts = []
        window.app.restart_requested.connect(lambda: restarts.append(True))

        with patch("ui.app_controller.SettingsDialog") as dialog_class:
            dialog = dialog_class.return_value
            dialog.settings_applied.connect.side_effect = callbacks.append
            dialog.exec.side_effect = lambda: (callbacks[0]({"theme": "cyber_dark"}), 1)[1]
            window.app.open_settings_dialog()

        self.assertEqual(restarts, [])
        window.close()

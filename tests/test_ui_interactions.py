import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QPushButton
from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project import ProjectManager
from core.report_file_manager import ReportFileManager
from core.net_detector import NetDetector
from ui.main_window import MainWindow
from ui.report_editor_tab import ReportEditorTab

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
    def test_cheatsheet_favorites_ui_interaction(self):
        from ui.snippet_card import SnippetCard
        config_manager = ConfigManager(config_dir=self.config_dir)
        snippet_manager = SnippetManager(user_snippets_path=self.custom_snippets_path)
        project_manager = ProjectManager(base_dir=self.projects_dir)
        loot_manager = LootManager(storage_file=self.loot_file)
        clipboard_watcher = ClipboardWatcher(storage_file=self.clip_file)

        window = MainWindow(
            config_manager=config_manager,
            snippet_manager=snippet_manager,
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            project_manager=project_manager
        )

        window.app.switch_mode("cheatsheet")
        self.assertGreater(len(window.cards), 2)
        
        # Check that favorites filter pill exists
        self.assertIn("favorites", window.app.cheatsheet_ctrl.filter_buttons)
        fav_btn = window.app.cheatsheet_ctrl.filter_buttons["favorites"]
        self.assertIn("★", fav_btn.text())
        
        # Find a non-favorite card to toggle ON
        non_fav_card = next(c for c in window.cards if isinstance(c, SnippetCard) and not snippet_manager.is_favorite(c.snippet.get("id")))
        snippet_id = non_fav_card.snippet.get("id")
        
        self.assertFalse(snippet_manager.is_favorite(snippet_id))
        non_fav_card.btn_fav.click()
        
        # Check that it is now favorite in manager
        self.assertTrue(snippet_manager.is_favorite(snippet_id))
        
        # Filter by favorites
        window.app._select_category("favorites")
        fav_ids = [c.snippet.get("id") for c in window.cards if isinstance(c, SnippetCard)]
        self.assertIn(snippet_id, fav_ids)
        
        # Toggle off
        fav_card = next(c for c in window.cards if isinstance(c, SnippetCard) and c.snippet.get("id") == snippet_id)
        fav_card.btn_fav.click()
        self.assertFalse(snippet_manager.is_favorite(snippet_id))

        window.close()

    @pytest.mark.integration
    def test_inline_command_tweaker_interaction(self):
        from ui.snippet_card import SnippetCard
        from PyQt6.QtWidgets import QApplication, QDialog
        from unittest.mock import patch
        config_manager = ConfigManager(config_dir=self.config_dir)
        snippet_manager = SnippetManager(user_snippets_path=self.custom_snippets_path)
        project_manager = ProjectManager(base_dir=self.projects_dir)
        loot_manager = LootManager(storage_file=self.loot_file)
        clipboard_watcher = ClipboardWatcher(storage_file=self.clip_file)

        window = MainWindow(
            config_manager=config_manager,
            snippet_manager=snippet_manager,
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            project_manager=project_manager
        )

        window.app.switch_mode("cheatsheet")
        self.assertGreater(len(window.cards), 0)
        card = window.cards[0]
        self.assertIsInstance(card, SnippetCard)

        self.assertFalse(hasattr(card, "tweak_container"))

        # Edit and confirm the new modal command editor.
        tweaked_cmd = card._rendered_command + " --proxy socks5://127.0.0.1:9050"
        def accept_edited_command(dialog):
            dialog.txt_command.setPlainText(tweaked_cmd)
            return QDialog.DialogCode.Accepted

        with patch("ui.snippet_card.CommandEditDialog.exec", accept_edited_command):
            card.btn_tweak.click()

        # Check clipboard content
        clipboard = QApplication.clipboard()
        self.assertEqual(clipboard.text().strip(), tweaked_cmd.strip())

        window.close()

    @pytest.mark.integration
    def test_variable_bar_user_pass_and_visibility_toggle(self):
        from PyQt6.QtWidgets import QLineEdit
        config_manager = ConfigManager(config_dir=self.config_dir)
        snippet_manager = SnippetManager(user_snippets_path=self.custom_snippets_path)
        project_manager = ProjectManager(base_dir=self.projects_dir)
        loot_manager = LootManager(storage_file=self.loot_file)
        clipboard_watcher = ClipboardWatcher(storage_file=self.clip_file)

        window = MainWindow(
            config_manager=config_manager,
            snippet_manager=snippet_manager,
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            project_manager=project_manager
        )

        # Check fields exist on VariableBar
        self.assertTrue(hasattr(window.var_bar, "txt_user"))
        self.assertTrue(hasattr(window.var_bar, "txt_pass"))
        self.assertEqual(window.var_bar.txt_user.width(), window.var_bar.txt_target.width())
        self.assertEqual(window.var_bar.txt_pass.width(), window.var_bar.txt_target.width())
        self.assertTrue(hasattr(window.var_bar, "btn_toggle_pass"))

        # Password initially in Password mode
        self.assertEqual(window.var_bar.txt_pass.echoMode(), QLineEdit.EchoMode.Password)

        # Click eye button -> toggles to Normal
        window.var_bar.btn_toggle_pass.click()
        self.assertEqual(window.var_bar.txt_pass.echoMode(), QLineEdit.EchoMode.Normal)

        # Click again -> toggles back to Password
        window.var_bar.btn_toggle_pass.click()
        self.assertEqual(window.var_bar.txt_pass.echoMode(), QLineEdit.EchoMode.Password)

        # Test set_variables and get_variables
        test_vars = {
            "target_ip": "192.168.1.10",
            "attacker_ip": "192.168.1.5",
            "port": "8000",
            "username": "pentester",
            "password": "SuperSecretPassword123"
        }
        window.var_bar.set_variables(test_vars)
        retrieved = window.var_bar.get_variables()
        self.assertEqual(retrieved["username"], "pentester")
        self.assertEqual(retrieved["password"], "SuperSecretPassword123")

        window.close()

    @pytest.mark.integration
    def test_project_archive_ui_action(self):
        from unittest.mock import patch
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        config_manager = ConfigManager(config_dir=self.config_dir)
        snippet_manager = SnippetManager(user_snippets_path=self.custom_snippets_path)
        project_manager = ProjectManager(base_dir=self.projects_dir)
        loot_manager = LootManager(storage_file=self.loot_file)
        clipboard_watcher = ClipboardWatcher(storage_file=self.clip_file)

        project_manager.create_project("BoxToArchive", target_ip="10.10.10.99")
        project_manager.activate_project("BoxToArchive")

        window = MainWindow(
            config_manager=config_manager,
            snippet_manager=snippet_manager,
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            project_manager=project_manager
        )

        out_zip = self.temp_path / "BoxToArchive.zip"
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(out_zip), "ZIP Archives (*.zip)")), \
             patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.No):
            window.app.project_ctrl._on_archive_project(window)

        self.assertTrue(out_zip.exists())
        import zipfile
        self.assertTrue(zipfile.is_zipfile(out_zip))

        window.close()

    @pytest.mark.integration
    def test_search_fuzzy_and_result_capping(self):
        """Verifies that typing with typos finds matches and caps results at top 25 with expander."""
        config_manager = ConfigManager(config_dir=self.config_dir)
        snippet_manager = SnippetManager(user_snippets_path=self.custom_snippets_path)
        project_manager = ProjectManager(base_dir=self.projects_dir)
        loot_manager = LootManager(storage_file=self.loot_file)
        clipboard_watcher = ClipboardWatcher(storage_file=self.clip_file)

        window = MainWindow(
            config_manager=config_manager,
            snippet_manager=snippet_manager,
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            project_manager=project_manager
        )

        # 1. Typo Search: 'nmp' finds nmap (and snmp)
        window.search_panel.search_bar.txt_search.setText("nmp")
        window.search_panel.search_bar._emit_search_changed()

        self.assertGreater(len(window.cards), 0)
        found_nmap = any("nmap" in (c.snippet["title"] + c.snippet["template"]).lower() for c in window.cards if hasattr(c, "snippet"))
        self.assertTrue(found_nmap)

        # Exact Tool Search: 'nmap' puts nmap at the top
        window.search_panel.search_bar.txt_search.setText("nmap")
        window.search_panel.search_bar._emit_search_changed()
        self.assertGreater(len(window.cards), 0)
        first_card = window.cards[0]
        self.assertIn("nmap", first_card.snippet["title"].lower() + first_card.snippet["template"].lower())

        # 2. Broad search with > 25 matches triggers capping
        window.search_panel.search_bar.txt_search.setText("e")
        window.search_panel.search_bar._emit_search_changed()

        matching_total = len(snippet_manager.get_snippets(search_query="e"))
        if matching_total > 25:
            # 25 SnippetCards + 1 Expander Button = 26 widgets in cards
            self.assertEqual(len(window.cards), 26)
            expander_btn = window.cards[-1]
            from PyQt6.QtWidgets import QPushButton
            self.assertIsInstance(expander_btn, QPushButton)
            self.assertTrue("Weitere" in expander_btn.text() or "more" in expander_btn.text().lower())

            # Click expander -> now all matching items are rendered
            expander_btn.click()
            self.assertEqual(len(window.cards), matching_total)

        window.close()

if __name__ == "__main__":
    unittest.main()


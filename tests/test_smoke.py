import os
import sys
import unittest
import tempfile
from pathlib import Path

# Ensure Qt runs headlessly in test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
from core.screenshot_manager import ScreenshotManager
from core.report_builder import ReportBuilder
from ui.main_window import MainWindow


class TestAppSmoke(unittest.TestCase):
    """End-to-End Smoke Test verifying full application lifecycle and workflows."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        
        self.config_dir = self.base_path / "config"
        self.projects_dir = self.base_path / "projects"
        
        self.config_mgr = ConfigManager(config_dir=self.config_dir)
        self.snippet_mgr = SnippetManager()
        self.project_mgr = ProjectManager(base_dir=self.projects_dir)
        self.loot_mgr = LootManager(storage_file=self.config_dir / "loot.json")
        self.clip_watcher = ClipboardWatcher(storage_file=self.config_dir / "clipboard.json")
        self.screen_mgr = ScreenshotManager()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_app_lifecycle_smoke(self):
        """
        Comprehensive smoke test:
        1. MainWindow creation & initialization
        2. Cheatsheet search & snippet loading
        3. Project creation & switching
        4. Session loot creation (creds, notes, screenshots)
        5. Clipboard history logging & loot transfer
        6. Report generation & Markdown verification
        7. Clean shutdown
        """
        # 1. Instantiate MainWindow
        window = MainWindow(
            config_manager=self.config_mgr,
            snippet_manager=self.snippet_mgr,
            loot_manager=self.loot_mgr,
            clipboard_watcher=self.clip_watcher,
            project_manager=self.project_mgr,
            screenshot_manager=self.screen_mgr
        )
        self.assertIsNotNone(window)
        self.assertEqual(window.active_mode, "cheatsheet")

        # 2. Cheatsheet Mode: Check Snippets & Categories
        categories = self.snippet_mgr.get_categories()
        self.assertGreater(len(categories), 0)
        
        snippets = self.snippet_mgr.get_snippets(category_id="all")
        self.assertGreater(len(snippets), 0)
        
        # Test search filtering
        window.search_bar.txt_search.setText("nmap")
        window.refresh_content()
        self.assertGreater(len(window.cards), 0)

        # 3. Project / Box Management: Create & Switch to new Box
        new_box = "BoxSmokeTest"
        self.project_mgr.create_project(
            name=new_box,
            target_ip="10.10.11.200",
            attacker_ip="10.10.14.33",
            port="9001"
        )
        window._switch_to_project(new_box)
        self.assertEqual(self.project_mgr.get_active_project(), new_box)
        self.assertEqual(window.var_bar.txt_target.text(), "10.10.11.200")
        self.assertEqual(window.var_bar.txt_attacker.text(), "10.10.14.33")

        # 4. Loot Management: Add Findings into Box
        window.switch_mode("loot")
        window.search_bar.txt_search.setText("")
        self.assertEqual(window.active_mode, "loot")

        self.loot_mgr.add_entry(
            entry_type="credentials",
            category="access",
            title="Root SSH Key",
            content="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC...",
            target_ip="10.10.11.200"
        )
        self.loot_mgr.add_entry(
            entry_type="flag",
            category="post_exploit",
            title="User Flag",
            content="HTB{sm0k3_t3st_fl4g_1337}",
            target_ip="10.10.11.200"
        )
        window._save_current_project_state()
        window.refresh_filter_pills()
        window.refresh_content()
        self.assertGreaterEqual(len(window.cards), 2)

        # 5. History & Clipboard Recording
        window.switch_mode("history")
        window.search_bar.txt_search.setText("")
        self.assertEqual(window.active_mode, "history")

        self.clip_watcher.add_entry("curl http://10.10.11.200/secret.txt", target_ip="10.10.11.200")
        window.refresh_filter_pills()
        window.refresh_content()
        self.assertEqual(len(self.clip_watcher.get_history()), 1)

        # 6. Report Generation
        window.switch_mode("report")
        self.assertEqual(window.active_mode, "report")

        proj_dir = self.project_mgr.get_project_dir(new_box)
        report_file = proj_dir / "report.md"
        
        builder = ReportBuilder(
            loot_manager=self.loot_mgr,
            clipboard_watcher=self.clip_watcher,
            project_manager=self.project_mgr
        )
        builder.export(report_file, target_ip="10.10.11.200", project_name=new_box)
        
        self.assertTrue(report_file.exists())
        content = report_file.read_text(encoding="utf-8")
        self.assertIn("BoxSmokeTest", content)
        self.assertIn("HTB{sm0k3_t3st_fl4g_1337}", content)
        self.assertIn("Root SSH Key", content)

        # 7. Clean Shutdown
        window.close()
        self.clip_watcher.stop_listening() if hasattr(self.clip_watcher, 'stop_listening') else None


if __name__ == "__main__":
    unittest.main()

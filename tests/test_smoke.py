import os
import sys
import unittest
import tempfile
import uuid
from pathlib import Path

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from core.config import ConfigManager
from core.snippets.manager import SnippetManager
from core.loot.manager import LootManager
from core.clipboard_history import ClipboardHistory
from core.project import ProjectManager
from core.screenshots.manager import ScreenshotManager
from core.reporting.builder import ReportBuilder
from tests.window_factory import create_main_window

pytestmark = pytest.mark.integration


class TestAppSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

        self.config_dir = self.base_path / "config"
        self.projects_dir = self.base_path / "projects"
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.config_dir)

        self.config_mgr = ConfigManager(config_dir=self.config_dir)
        self.snippet_mgr = SnippetManager(user_snippets_path=self.config_dir / "user_snippets.json")
        self.project_mgr = ProjectManager(base_dir=self.projects_dir)
        self.loot_mgr = LootManager(storage_file=self.config_dir / "loot.json")
        self.clip_watcher = ClipboardHistory(storage_file=self.config_dir / "clipboard.json")
        self.screen_mgr = ScreenshotManager()

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        self.temp_dir.cleanup()

    def test_full_app_lifecycle_smoke(self):
        print("Smoke: 1. Instantiate MainWindow", flush=True)
        window = create_main_window(
            config_manager=self.config_mgr,
            snippet_manager=self.snippet_mgr,
            loot_manager=self.loot_mgr,
            clipboard_watcher=self.clip_watcher,
            project_manager=self.project_mgr,
            screenshot_manager=self.screen_mgr,
        )
        self.assertIsNotNone(window)

        print("Smoke: 2. Verify Initial Cheatsheet State", flush=True)
        self.assertEqual(window.app.active_mode, "cheatsheet")
        categories = self.snippet_mgr.get_categories()
        self.assertGreater(len(categories), 0)

        snippets = self.snippet_mgr.get_snippets(category_id="all")
        self.assertGreater(len(snippets), 0)

        window.search_panel.search_bar.txt_search.setText("nmap")
        window.app.refresh_content()
        self.assertGreater(len(window.cards), 0)

        print("Smoke: 3. Create project", flush=True)
        new_box = f"BoxSmoke_{uuid.uuid4().hex[:6]}"
        self.project_mgr.create_project(
            name=new_box, target_ip="10.10.11.200", attacker_ip="10.10.14.33", port="9001"
        )
        window.app.switch_to_project(new_box)
        self.assertEqual(self.project_mgr.get_active_project(), new_box)
        self.assertEqual(window.var_bar.txt_target.text(), "10.10.11.200")
        self.assertEqual(window.var_bar.txt_attacker.text(), "10.10.14.33")

        print("Smoke: 4. Loot mode", flush=True)
        window.app.switch_mode("loot")
        window.search_panel.search_bar.txt_search.setText("")
        self.assertEqual(window.app.active_mode, "loot")

        window.app.loot_ctrl.add_entry(
            entry_type="credentials",
            category="access",
            title="Root SSH Key",
            content="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC...",
            target_ip="10.10.11.200",
        )
        window.app.loot_ctrl.add_entry(
            entry_type="flag",
            category="post_exploit",
            title="User Flag",
            content="HTB{sm0k3_t3st_fl4g_1337}",
            target_ip="10.10.11.200",
        )
        window.app.save_current_project_state()
        window.app.refresh_filter_pills()
        window.app.refresh_content()
        self.assertGreaterEqual(len(window.cards), 2)

        print("Smoke: 5. History mode", flush=True)
        window.app.switch_mode("history")
        window.search_panel.search_bar.txt_search.setText("")
        self.assertEqual(window.app.active_mode, "history")

        window.app.history_ctrl.add_entry(
            "curl http://10.10.11.200/secret.txt", target_ip="10.10.11.200"
        )
        window.app.refresh_filter_pills()
        window.app.refresh_content()
        self.assertEqual(len(self.clip_watcher.get_history()), 1)

        print("Smoke: 6. Report mode", flush=True)
        window.app.switch_mode("report")
        self.assertEqual(window.app.active_mode, "report")

        proj_dir = self.project_mgr.get_project_dir(new_box)
        report_file = proj_dir / "report.md"

        builder = ReportBuilder(
            loot_manager=self.loot_mgr,
            clipboard_watcher=self.clip_watcher,
            project_manager=self.project_mgr,
        )
        builder.export(report_file, target_ip="10.10.11.200", project_name=new_box)

        self.assertTrue(report_file.exists())
        content = report_file.read_text(encoding="utf-8")
        self.assertIn(new_box, content)
        self.assertIn("HTB{sm0k3_t3st_fl4g_1337}", content)
        self.assertIn("Root SSH Key", content)

        print("Smoke: 7. Clean Shutdown", flush=True)
        window.hide()
        window.close()
        if hasattr(self.clip_watcher, "stop_listening"):
            self.clip_watcher.stop_listening()
        print("Smoke: COMPLETE", flush=True)


if __name__ == "__main__":
    unittest.main()

import os
import unittest
import tempfile
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
from core.net_detector import NetDetector
from ui.main_window import MainWindow

class TestUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def test_net_detector(self):
        ip = NetDetector.detect_attacker_ip()
        if ip:
            self.assertIsInstance(ip, str)
            self.assertIn(".", ip)

    def test_hud_3_modes_and_projects(self):
        config_manager = ConfigManager()
        snippet_manager = SnippetManager()
        
        temp_dir = tempfile.TemporaryDirectory()
        base_proj_dir = Path(temp_dir.name) / "test_projects"
        project_manager = ProjectManager(base_dir=base_proj_dir)

        temp_loot = Path(temp_dir.name) / "test_ui_loot.json"
        temp_clip = Path(temp_dir.name) / "test_ui_clip.json"

        loot_manager = LootManager(storage_file=temp_loot)
        clipboard_watcher = ClipboardWatcher(storage_file=temp_clip)

        window = MainWindow(
            config_manager, snippet_manager, loot_manager, 
            clipboard_watcher, project_manager
        )
        
        # 1. Mode: Cheatsheet
        self.assertEqual(window.active_mode, "cheatsheet")
        self.assertGreater(len(window.cards), 0)

        # 2. Mode: Loot
        window.switch_mode("loot")
        self.assertEqual(window.active_mode, "loot")

        # 3. Mode: History
        window.switch_mode("history")
        self.assertEqual(window.active_mode, "history")

        # 4. Project Workspace Switch
        project_manager.create_project("BoxOmega", target_ip="10.10.10.123")
        window._switch_to_project("BoxOmega")
        self.assertEqual(window.var_bar.txt_target.text(), "10.10.10.123")
        self.assertEqual(project_manager.get_active_project(), "BoxOmega")

        # Add loot to BoxOmega
        loot_manager.add_entry("credentials", "Omega User", "omega:pass123", "10.10.10.123")
        window._save_current_project_state()

        # Switch back to Default
        window._switch_to_project("Default")
        self.assertEqual(window.var_bar.txt_target.text(), "10.10.10.10")
        self.assertEqual(len(loot_manager.get_entries()), 0)

        # Switch back to BoxOmega -> Loot is restored!
        window._switch_to_project("BoxOmega")
        self.assertEqual(window.var_bar.txt_target.text(), "10.10.10.123")
        self.assertEqual(len(loot_manager.get_entries()), 1)

        window.close()
        temp_dir.cleanup()

if __name__ == "__main__":
    unittest.main()

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

    def test_hud_3_modes(self):
        config_manager = ConfigManager()
        snippet_manager = SnippetManager()
        
        temp_loot = Path(tempfile.gettempdir()) / "test_ui_loot_3m.json"
        temp_clip = Path(tempfile.gettempdir()) / "test_ui_clip_3m.json"
        if temp_loot.exists():
            temp_loot.unlink()
        if temp_clip.exists():
            temp_clip.unlink()

        loot_manager = LootManager(storage_file=temp_loot)
        clipboard_watcher = ClipboardWatcher(storage_file=temp_clip)

        # Pre-seed items
        loot_manager.add_entry("credentials", "MySQL Root", "root:toor123", "10.10.10.99")
        clipboard_watcher.add_entry("curl -i http://10.10.10.99/login", "10.10.10.99")
        clipboard_watcher.add_entry("whoami /priv", "10.10.10.99")

        window = MainWindow(config_manager, snippet_manager, loot_manager, clipboard_watcher)
        
        # 1. Mode: Cheatsheet
        self.assertEqual(window.active_mode, "cheatsheet")
        self.assertGreater(len(window.cards), 0)

        # 2. Mode: Loot
        window.switch_mode("loot")
        self.assertEqual(window.active_mode, "loot")
        self.assertEqual(len(window.cards), 1)

        # 3. Mode: History
        window.switch_mode("history")
        self.assertEqual(window.active_mode, "history")
        self.assertEqual(len(window.cards), 2)

        # Search in History
        window.search_bar.txt_search.setText("whoami")
        self.assertEqual(len(window.cards), 1)

        # Tab cycling
        window.toggle_mode()
        self.assertEqual(window.active_mode, "cheatsheet")

        window.close()

if __name__ == "__main__":
    unittest.main()

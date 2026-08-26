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
        self.temp_dir = tempfile.TemporaryDirectory()
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
        self.temp_dir.cleanup()

    def test_net_detector(self):
        ip = NetDetector.detect_attacker_ip()
        if ip:
            self.assertIsInstance(ip, str)
            self.assertIn(".", ip)

    def test_hud_modes_and_projects(self):
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
        
        # 1. Mode: Cheatsheet
        self.assertEqual(window.active_mode, "cheatsheet")
        self.assertGreater(len(window.cards), 0)

        # 2. Mode: Loot
        window.switch_mode("loot")
        self.assertEqual(window.active_mode, "loot")

        # 3. Mode: History
        window.switch_mode("history")
        self.assertEqual(window.active_mode, "history")

        # 4. Mode: Report
        window.switch_mode("report")
        self.assertEqual(window.active_mode, "report")
        self.assertFalse(window.search_bar.isVisible())
        self.assertFalse(window.var_bar.isVisible())
        self.assertFalse(window.pills_frame.isVisible())

        # Tab cycling stays within cheatsheet/loot/history (does not cycle to report)
        window.switch_mode("cheatsheet")
        window.toggle_mode()
        self.assertEqual(window.active_mode, "loot")
        window.toggle_mode()
        self.assertEqual(window.active_mode, "history")
        window.toggle_mode()
        self.assertEqual(window.active_mode, "cheatsheet")

        # 5. Project Workspace Switch
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

        # 6. Resizability and Edge Detection
        self.assertGreaterEqual(window.width(), 740)
        self.assertGreaterEqual(window.height(), 480)
        
        # Test edge calculation
        from PyQt6.QtCore import QPoint
        edge_bottom_right = window._get_resize_edge(QPoint(window.width() - 2, window.height() - 2))
        self.assertEqual(edge_bottom_right, "bottom_right")
        
        edge_center = window._get_resize_edge(QPoint(window.width() // 2, window.height() // 2))
        self.assertEqual(edge_center, "")

        # 7. Always on Top Toggle
        self.assertTrue(window.chk_always_on_top.isChecked())
        window.chk_always_on_top.setChecked(False)
        self.assertFalse(config_manager.get("always_on_top"))
        window.chk_always_on_top.setChecked(True)
        self.assertTrue(config_manager.get("always_on_top"))

        window.close()

    def test_report_editor_tab_smoke(self):
        """Smoke test verifying ReportEditorTab lifecycle, editing, dirty flag and saving."""
        project_manager = ProjectManager(base_dir=self.projects_dir)
        project_manager.create_project("BoxGamma")
        loot_manager = LootManager(storage_file=self.loot_file)
        clipboard_watcher = ClipboardWatcher(storage_file=self.clip_file)
        report_file_manager = ReportFileManager(project_manager)

        tab = ReportEditorTab(report_file_manager, loot_manager, clipboard_watcher)

        # 1. Load project with no report.md yet
        tab.load_project("BoxGamma")
        self.assertEqual(tab.editor.toPlainText(), "")
        self.assertFalse(tab.is_dirty())

        # 2. Modify editor content -> dirty flag becomes True
        tab.editor.setPlainText("# Box Gamma Writeup\nInitial foothold via port 80.")
        self.assertTrue(tab.is_dirty())
        self.assertIn("Ungespeicherte Änderungen", tab.lbl_status.text())

        # 3. Save -> dirty flag becomes False and file is written
        ok = tab.save()
        self.assertTrue(ok)
        self.assertFalse(tab.is_dirty())
        self.assertIn("Gespeichert", tab.lbl_status.text())
        self.assertTrue(report_file_manager.exists("BoxGamma"))
        self.assertEqual(report_file_manager.load("BoxGamma"), "# Box Gamma Writeup\nInitial foothold via port 80.")

        # 4. Load project with existing content
        tab.load_project("BoxGamma")
        self.assertEqual(tab.editor.toPlainText(), "# Box Gamma Writeup\nInitial foothold via port 80.")
        self.assertFalse(tab.is_dirty())

    def test_loot_grouped_by_category_with_headers(self):
        """Verifies that loot view displays section headers only for non-empty categories in CATEGORIES order."""
        from PyQt6.QtWidgets import QLabel
        from ui.loot_card import LootCard

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

        # Add entries into exactly 3 categories (recon, access, misc)
        loot_manager.add_entry("directory", "Web Root", "http://10.10.10.10/", category="recon")
        loot_manager.add_entry("credentials", "Admin SSH", "root:secret", category="access")
        loot_manager.add_entry("note", "General Hint", "Check port 8080", category="misc")

        window.switch_mode("loot")

        def get_current_headers():
            return [
                window.content_layout.itemAt(i).widget()
                for i in range(window.content_layout.count())
                if isinstance(window.content_layout.itemAt(i).widget(), QLabel)
                and window.content_layout.itemAt(i).widget().property("class") == "LootSectionHeader"
            ]

        def get_current_cards():
            return [
                window.content_layout.itemAt(i).widget()
                for i in range(window.content_layout.count())
                if isinstance(window.content_layout.itemAt(i).widget(), LootCard)
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
        window._select_loot_type("credentials")
        filtered_headers = get_current_headers()
        self.assertEqual(len(filtered_headers), 1)
        self.assertIn("Initial Access", filtered_headers[0].text())

        # 5. Reset filter to 'all' -> all 3 headers return
        window._select_loot_type("all")
        reset_headers = get_current_headers()
        self.assertEqual(len(reset_headers), 3)

        window.close()

if __name__ == "__main__":
    unittest.main()

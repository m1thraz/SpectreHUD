import os
import unittest
import tempfile
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QColor
from core.project_manager import ProjectManager
from core.loot_manager import LootManager
from core.screenshot_manager import ScreenshotManager
from ui.loot_card import LootCard

class TestScreenshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path / "config")
        os.environ["SPECTRE_PROJECTS_DIR"] = str(self.temp_path / "projects")

        self.base_dir = self.temp_path / "projects"
        self.pm = ProjectManager(base_dir=self.base_dir)
        self.pm.create_project("BoxAlpha", target_ip="10.10.10.77")
        self.pm.set_active_project("BoxAlpha")

        self.loot_file = self.temp_path / "config" / "loot.json"
        self.loot_mgr = LootManager(storage_file=self.loot_file)
        self.sm = ScreenshotManager()

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        os.environ.pop("SPECTRE_PROJECTS_DIR", None)
        self.temp_dir.cleanup()

    def test_save_screenshot_and_loot_entry(self):
        # Create a mock 100x100 pixmap
        pixmap = QPixmap(100, 100)
        pixmap.fill(QColor("cyan"))

        from PyQt6.QtWidgets import QWidget
        dummy_win = QWidget()

        # Simulate completion
        self.sm._on_snip_completed(
            pixmap, dummy_win, self.pm, self.loot_mgr, target_ip="10.10.10.77"
        )

        # Verify loot entry
        entries = self.loot_mgr.get_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["type"], "screenshot")
        self.assertIn("loot/screenshot_", entries[0]["content"])
        self.assertIn("![Screenshot", entries[0]["content"])

        # Verify file exists on disk in project loot folder
        proj_dir = self.pm.get_project_dir("BoxAlpha")
        loot_dir = proj_dir / "loot"
        files = list(loot_dir.glob("screenshot_*.png"))
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].exists())

        # Test LootCard image resolution
        card = LootCard(entries[0])
        resolved_img = card._resolve_image_path()
        self.assertIsNotNone(resolved_img)
        self.assertTrue(resolved_img.exists())

        dummy_win.close()

if __name__ == "__main__":
    unittest.main()

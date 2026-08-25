import os
import unittest
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPixmap, QImage, QColor

from core.project_manager import ProjectManager
from core.loot_manager import LootManager
from core.screenshot_manager import ScreenshotManager


class TestScreenshotManager(unittest.TestCase):
    """Unit tests verifying ScreenshotManager file saving and collision handling."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.loot_mgr = LootManager(storage_file=self.temp_path / "loot.json")
        self.screenshot_mgr = ScreenshotManager()

        self.project_mgr.create_project("BoxSnip")
        self.project_mgr.set_active_project("BoxSnip")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_snip_completed_saves_png_and_creates_loot(self):
        """Tests that a completed snip saves a PNG into projects/BoxSnip/loot and registers a loot item."""
        # Create a dummy 100x100 QPixmap
        img = QImage(100, 100, QImage.Format.Format_RGB32)
        img.fill(QColor("red"))
        pixmap = QPixmap.fromImage(img)

        parent_win = QWidget()
        self.screenshot_mgr._on_snip_completed(
            cropped_pixmap=pixmap,
            parent_window=parent_win,
            project_manager=self.project_mgr,
            loot_manager=self.loot_mgr,
            target_ip="10.10.10.55"
        )

        # Check loot directory
        loot_dir = self.project_mgr.get_project_dir("BoxSnip") / "loot"
        pngs = list(loot_dir.glob("screenshot_*.png"))
        self.assertEqual(len(pngs), 1)

        # Check loot entry
        entries = self.loot_mgr.get_all_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["type"], "screenshot")
        self.assertIn("loot/", entries[0]["content"])

    def test_screenshot_collision_resistance(self):
        """Tests that multiple rapid screenshots in the same second do not overwrite each other."""
        img = QImage(50, 50, QImage.Format.Format_RGB32)
        img.fill(QColor("blue"))
        pixmap = QPixmap.fromImage(img)

        parent_win = QWidget()
        # Save two screenshots back-to-back
        self.screenshot_mgr._on_snip_completed(
            cropped_pixmap=pixmap,
            parent_window=parent_win,
            project_manager=self.project_mgr,
            loot_manager=self.loot_mgr,
            target_ip="10.10.10.55"
        )
        self.screenshot_mgr._on_snip_completed(
            cropped_pixmap=pixmap,
            parent_window=parent_win,
            project_manager=self.project_mgr,
            loot_manager=self.loot_mgr,
            target_ip="10.10.10.55"
        )

        loot_dir = self.project_mgr.get_project_dir("BoxSnip") / "loot"
        pngs = list(loot_dir.glob("screenshot_*.png"))
        self.assertEqual(len(pngs), 2, "Expected 2 distinct screenshot files without collision")

        entries = self.loot_mgr.get_all_entries()
        self.assertEqual(len(entries), 2)


if __name__ == "__main__":
    unittest.main()

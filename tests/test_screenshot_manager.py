import os
import unittest
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPixmap, QImage, QColor

from core.project import ProjectManager
from core.loot_manager import LootManager
from core.screenshot_manager import ScreenshotManager
from core.screenshot_transaction_service import ScreenshotTransactionResult
from core.event_bus import EventBus, EventType


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
        self.project_mgr.activate_project("BoxSnip")

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

    def test_capture_virtual_desktop_fallback_or_single_screen(self):
        """Tests that capture_virtual_desktop returns a valid pixmap or handles offscreen."""
        pixmap, bbox = self.screenshot_mgr.capture_virtual_desktop()
        # In offscreen test environment, QScreen may return a pixmap or None
        if pixmap is not None:
            self.assertFalse(pixmap.isNull())
            self.assertIsNotNone(bbox)
            self.assertGreater(bbox.width, 0)
            self.assertGreater(bbox.height, 0)

    def test_screenshot_save_failure_does_not_create_loot_entry(self):
        """Invariant: If saving PNG to disk fails, NO loot entry must be created (no ghost/orphaned loot)."""
        from unittest.mock import patch

        img = QImage(50, 50, QImage.Format.Format_RGB32)
        pixmap = QPixmap.fromImage(img)
        parent_win = QWidget()

        with patch.object(QPixmap, "save", return_value=False):
            with self.assertRaises(Exception):
                self.screenshot_mgr._on_snip_completed(
                    cropped_pixmap=pixmap,
                    parent_window=parent_win,
                    project_manager=self.project_mgr,
                    loot_manager=self.loot_mgr,
                    target_ip="10.10.10.55"
                )

        # Invariant: No loot entries created when disk save fails
        self.assertEqual(len(self.loot_mgr.get_all_entries()), 0)

    def test_screenshot_save_failure_restores_hidden_hud(self):
        """A PNG failure must restore the HUD through the completion finally-path."""
        from unittest.mock import MagicMock, patch
        from PyQt6.QtCore import Qt

        img = QImage(50, 50, QImage.Format.Format_RGB32)
        pixmap = QPixmap.fromImage(img)
        parent_win = MagicMock()
        parent_win.windowState.return_value = Qt.WindowState.WindowNoState

        with patch.object(QPixmap, "save", return_value=False):
            with self.assertRaises(Exception):
                self.screenshot_mgr._on_snip_completed(
                    cropped_pixmap=pixmap,
                    parent_window=parent_win,
                    project_manager=self.project_mgr,
                    loot_manager=self.loot_mgr,
                    target_ip="10.10.10.55",
                )

        parent_win.show.assert_called_once()
        parent_win.raise_.assert_called_once()
        parent_win.activateWindow.assert_called_once()
        parent_win.switch_mode.assert_not_called()

    def test_loot_failure_restores_hidden_hud(self):
        """A loot persistence error must restore the HUD through the same finally-path."""
        from unittest.mock import MagicMock
        from PyQt6.QtCore import Qt

        img = QImage(50, 50, QImage.Format.Format_RGB32)
        pixmap = QPixmap.fromImage(img)
        parent_win = MagicMock()
        parent_win.windowState.return_value = Qt.WindowState.WindowNoState
        failing_loot_manager = MagicMock()
        failing_loot_manager.add_entry.side_effect = RuntimeError("loot write failed")

        with self.assertRaises(RuntimeError):
            self.screenshot_mgr._on_snip_completed(
                cropped_pixmap=pixmap,
                parent_window=parent_win,
                project_manager=self.project_mgr,
                loot_manager=failing_loot_manager,
                target_ip="10.10.10.55",
            )

        parent_win.show.assert_called_once()
        parent_win.raise_.assert_called_once()
        parent_win.activateWindow.assert_called_once()
        parent_win.switch_mode.assert_not_called()

    def test_session_save_failure_signal_path_does_not_switch_to_loot(self):
        """The manager must not treat a rolled-back controller transaction as successful."""
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from PyQt6.QtCore import Qt
        from ui.app_controller import AppController
        from core.event_bus import EventBus

        img = QImage(50, 50, QImage.Format.Format_RGB32)
        pixmap = QPixmap.fromImage(img)
        parent_win = MagicMock()
        parent_win.windowState.return_value = Qt.WindowState.WindowNoState
        controller = SimpleNamespace(
            screenshot_transaction=MagicMock(),
            switch_mode=MagicMock(),
            event_bus=EventBus(),
        )
        controller.screenshot_transaction.commit.return_value = ScreenshotTransactionResult(ok=False)
        self.screenshot_mgr.screenshot_saved.connect(
            lambda entry: AppController._on_screenshot_saved(controller, entry)
        )

        self.screenshot_mgr._on_snip_completed(
            cropped_pixmap=pixmap,
            parent_window=parent_win,
            project_manager=self.project_mgr,
            loot_manager=self.loot_mgr,
            target_ip="10.10.10.55",
        )

        controller.switch_mode.assert_not_called()
        parent_win.switch_mode.assert_not_called()

    def test_screenshot_publishes_exactly_one_domain_event(self):
        """The app boundary publishes one canonical event after the manager signal."""
        img = QImage(50, 50, QImage.Format.Format_RGB32)
        img.fill(QColor("green"))
        pixmap = QPixmap.fromImage(img)
        event_bus = EventBus()
        received = []
        event_bus.subscribe(EventType.SCREENSHOT_SAVED, received.append)
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from ui.app_controller import AppController

        controller = SimpleNamespace(
            screenshot_transaction=MagicMock(),
            switch_mode=MagicMock(),
            event_bus=event_bus,
        )
        controller.screenshot_transaction.commit.return_value = ScreenshotTransactionResult(ok=True)

        self.screenshot_mgr.screenshot_saved.connect(
            lambda entry: AppController._on_screenshot_saved(controller, entry)
        )
        self.screenshot_mgr._on_snip_completed(
            cropped_pixmap=pixmap,
            parent_window=QWidget(),
            project_manager=self.project_mgr,
            loot_manager=self.loot_mgr,
            target_ip="10.10.10.55",
        )

        self.assertEqual(len(received), 1)
        self.assertEqual(set(received[0]), {"entry"})
        self.assertEqual(received[0]["entry"]["type"], "screenshot")
        controller.switch_mode.assert_called_once_with("loot")


if __name__ == "__main__":
    unittest.main()

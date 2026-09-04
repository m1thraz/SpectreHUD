import os
import unittest
import tempfile
from pathlib import Path

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

from core.config import ConfigManager
from core.project import ProjectManager
from core.loot_manager import LootManager
from core.clipboard_history import ClipboardHistory
from core.screenshot_manager import ScreenshotManager
from core.screenshot_transaction_service import ScreenshotTransactionService
from core.project_session_service import ProjectSessionService


class TestWorkflowRobustness(unittest.TestCase):
    """
    Cross-component tests for data integrity, recovery, and normal workflow
    robustness. Component-local validation lives in focused test modules; this
    suite keeps one end-to-end invariant per user-visible failure mode.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.config_dir = self.temp_path / "config"
        self.projects_dir = self.temp_path / "projects"

        os.environ["SPECTRE_CONFIG_DIR"] = str(self.config_dir)
        os.environ["SPECTRE_PROJECTS_DIR"] = str(self.projects_dir)

        self.config_mgr = ConfigManager(config_dir=self.config_dir)
        self.project_mgr = ProjectManager(base_dir=self.projects_dir)
        self.loot_mgr = LootManager()
        self.clip_watcher = ClipboardHistory()
        self.screen_mgr = ScreenshotManager()
        self.session_service = ProjectSessionService(
            self.project_mgr, self.loot_mgr, self.clip_watcher
        )

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        os.environ.pop("SPECTRE_PROJECTS_DIR", None)
        self.temp_dir.cleanup()

    def test_screenshot_manager_does_not_save_project_state(self):
        """
        v15-P0: ScreenshotManager._on_snip_completed() must NOT call
        save_current_project_state() — project state persistence is exclusively
        owned by AppController._on_screenshot_saved().
        """
        from PyQt6.QtGui import QImage, QPixmap
        from PyQt6.QtWidgets import QWidget
        from unittest.mock import MagicMock

        self.project_mgr.create_project("BoxSnipOwnership")
        self.project_mgr.activate_project("BoxSnipOwnership")

        img = QImage(10, 10, QImage.Format.Format_RGB32)
        pix = QPixmap.fromImage(img)
        parent = QWidget()

        # Attach a mock save_current_project_state to the parent window
        parent.save_current_project_state = MagicMock(return_value=True)

        snip_mgr = ScreenshotManager()
        snip_mgr._on_snip_completed(
            cropped_pixmap=pix,
            parent_window=parent,
            project_manager=self.project_mgr,
            loot_manager=self.loot_mgr,
            target_ip="10.10.10.10",
        )

        # Invariant: ScreenshotManager must NOT call save_current_project_state
        parent.save_current_project_state.assert_not_called()

    def test_screenshot_session_save_failure_rolls_back_loot_and_png(self):
        """A failed session commit must not leave screenshot data orphaned."""
        from unittest.mock import MagicMock

        self.project_mgr.create_project("BoxScreenshotRollback")
        self.project_mgr.activate_project("BoxScreenshotRollback")
        original_entry = self.loot_mgr.add_entry("note", "Keep me", "existing loot")
        loot_dir = self.project_mgr.get_project_dir("BoxScreenshotRollback") / "loot"
        loot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = loot_dir / "screenshot_rollback.png"
        screenshot_path.write_bytes(b"png data")
        screenshot_entry = self.loot_mgr.add_entry(
            "screenshot", "Rollback screenshot", "![Screenshot](loot/screenshot_rollback.png)"
        )
        screenshot_entry["file_path"] = str(screenshot_path)

        persist_project_state = MagicMock(return_value=False)
        service = ScreenshotTransactionService(
            self.loot_mgr,
            persist_project_state,
        )

        result = service.commit(screenshot_entry)

        self.assertFalse(result.ok)
        persist_project_state.assert_called_once_with()
        self.assertEqual(
            [entry["id"] for entry in self.loot_mgr.get_all_entries()], [original_entry["id"]]
        )
        self.assertEqual(
            [entry["id"] for entry in self.loot_mgr.storage.load_json("loot")],
            [original_entry["id"]],
        )
        self.assertFalse(screenshot_path.exists())

    def test_screenshot_rollback_removes_png_when_loot_rollback_fails(self):
        """A failed loot rollback must not block independent screenshot-file cleanup."""
        from unittest.mock import MagicMock, patch
        from core.storage import PersistenceError

        self.project_mgr.create_project("BoxScreenshotRollbackFailure")
        loot_dir = self.project_mgr.get_project_dir("BoxScreenshotRollbackFailure") / "loot"
        loot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = loot_dir / "rollback_failure.png"
        screenshot_path.write_bytes(b"png data")
        screenshot_entry = self.loot_mgr.add_entry(
            "screenshot", "Rollback failure screenshot", "![Screenshot](loot/rollback_failure.png)"
        )
        screenshot_entry["file_path"] = str(screenshot_path)

        primary_failure = RuntimeError("project state unavailable")
        service = ScreenshotTransactionService(
            self.loot_mgr,
            MagicMock(side_effect=primary_failure),
        )

        with patch.object(
            self.loot_mgr,
            "replace_entries_and_persist",
            side_effect=PersistenceError("rollback storage unavailable"),
        ) as rollback:
            result = service.commit(screenshot_entry)

        rollback.assert_called_once()
        self.assertFalse(result.ok)
        self.assertIs(result.error, primary_failure)
        self.assertEqual(len(result.cleanup_errors), 1)
        self.assertIsInstance(result.cleanup_errors[0], PersistenceError)
        self.assertFalse(screenshot_path.exists())

    # -------------------------------------------------------------------------
    # 38. Strict project activation
    # -------------------------------------------------------------------------
    def test_activate_project_selects_existing_project(self):
        """Explicit activation selects an existing project without side effects."""
        self.project_mgr.create_project("BoxDeprecated")
        self.assertEqual(self.project_mgr.activate_project("BoxDeprecated"), "BoxDeprecated")

    def test_activate_project_does_not_create_unknown_project(self):
        """Strict activation must not create projects implicitly."""
        from core.project import ProjectNotFoundError

        with self.assertRaises(ProjectNotFoundError):
            self.project_mgr.activate_project("UnknownBox")

        self.assertNotIn("UnknownBox", self.project_mgr.list_projects())
        self.assertFalse((self.projects_dir / "UnknownBox").exists())

    # -------------------------------------------------------------------------
    # 39. v15-P1: list_projects() does not mutate registry
    # -------------------------------------------------------------------------
    @pytest.mark.integration
    def test_list_projects_does_not_mutate_registry(self):
        """
        v15-P1: ProjectRepository.list_projects() must be read-only —
        it must NOT write new entries into self.registry.
        """
        self.project_mgr.create_project("BoxReadOnly1")

        # Create a second project directory WITHOUT registration
        phantom_dir = self.projects_dir / "PhantomProject"
        phantom_dir.mkdir(parents=True, exist_ok=True)

        # Record registry state before list_projects
        registry_before = dict(self.project_mgr.registry)

        # list_projects must discover PhantomProject but NOT register it
        projects = self.project_mgr.list_projects()

        registry_after = dict(self.project_mgr.registry)

        self.assertIn(
            "PhantomProject", projects, "list_projects must discover PhantomProject from disk"
        )
        self.assertEqual(
            registry_before,
            registry_after,
            "list_projects() must not mutate self.registry (read-only invariant violated)",
        )

    # -------------------------------------------------------------------------
    # 40. v15-P1: sync_registry() registers and persists new discoveries
    # -------------------------------------------------------------------------
    def test_sync_registry_registers_and_persists(self):
        """
        v15-P1: ProjectRepository.sync_registry() must register newly discovered
        projects into self.registry AND persist the registry to disk.
        """
        self.project_mgr.create_project("BoxSyncBase")

        # Create an unregistered directory
        new_dir = self.projects_dir / "NewlyDiscovered"
        new_dir.mkdir(parents=True, exist_ok=True)

        # Ensure it's not in registry before sync
        self.assertNotIn("NewlyDiscovered", self.project_mgr.registry)

        # Run sync
        synced = self.project_mgr.sync_registry()

        # Invariant 1: synced list includes newly discovered project
        self.assertIn("NewlyDiscovered", synced)

        # Invariant 2: registry in memory now includes it
        self.assertIn("NewlyDiscovered", self.project_mgr.registry)

        # Invariant 3: registry was persisted to disk
        import json

        registry_file = self.project_mgr.registry_file
        self.assertTrue(registry_file.exists(), "Registry file must exist after sync_registry()")
        disk_registry = json.loads(registry_file.read_text(encoding="utf-8"))
        self.assertIn("NewlyDiscovered", disk_registry)


if __name__ == "__main__":
    unittest.main()

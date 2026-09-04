import os
import unittest
import tempfile
from pathlib import Path


os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

from core.config import ConfigManager
from core.project import ProjectManager, InvalidProjectNameError
from core.loot_manager import LootManager
from core.clipboard_history import ClipboardHistory
from core.screenshot_manager import ScreenshotManager
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

    def test_workspace_change_rejects_unwritable_directory(self):
        """
        Adversarial: Changing workspace directory to an unwritable / invalid path must fail-closed.
        """
        from unittest.mock import patch
        from core.project.validator import validate_workspace_directory, WorkspaceError

        # Empty path
        with self.assertRaises(WorkspaceError):
            validate_workspace_directory("")

        # Unwritable path simulation
        target_p = self.temp_path / "valid_unwritable_probe"
        with patch(
            "pathlib.Path.write_text", side_effect=PermissionError("Mock Permission Denied")
        ):
            with self.assertRaises(WorkspaceError):
                validate_workspace_directory(target_p)

    # -------------------------------------------------------------------------
    # 28. Directory Collision Handling on Existing Folders
    # -------------------------------------------------------------------------
    def test_project_name_collision_on_existing_directories(self):
        """
        Adversarial: Having both 'Hack Box' and 'Hack_Box' on disk must detect collision
        and refuse silent shadowing/overwrite in list_projects.
        """
        dir_a = self.projects_dir / "Hack Box"
        dir_b = self.projects_dir / "Hack_Box"
        dir_a.mkdir(parents=True, exist_ok=True)
        dir_b.mkdir(parents=True, exist_ok=True)

        projects = self.project_mgr.list_projects()
        # Due to collision, the ambiguous alias 'Hack_Box' must not silently shadow both directories
        self.assertNotIn("Hack Box", projects)

    # -------------------------------------------------------------------------
    # 29. Invalid Project Lookup Does Not Mutate Default
    # -------------------------------------------------------------------------
    def test_invalid_project_lookup_does_not_mutate_default(self):
        """
        Invalid project lookup must fail explicitly instead of silently
        returning and potentially mutating the Default project directory.
        """
        with self.assertRaises(InvalidProjectNameError):
            self.project_mgr.get_project_dir("../../../secret")

        with self.assertRaises(InvalidProjectNameError):
            self.project_mgr.repository.get_project_dir("..\\..\\windows_attack")

    # -------------------------------------------------------------------------
    # 30. Screenshot save ownership belongs to AppController
    # -------------------------------------------------------------------------
    def test_screenshot_manager_defers_project_state_persistence(self):
        """
        The ScreenshotManager must not call a parent-window persistence hook or own
        rollback semantics; the AppController persists the completed session after
        receiving the screenshot_saved signal.
        """
        from unittest.mock import MagicMock
        from PyQt6.QtGui import QPixmap, QImage
        from core.screenshot_manager import ScreenshotManager

        snip_mgr = ScreenshotManager()
        self.project_mgr.create_project("BoxRollback")
        self.project_mgr.activate_project("BoxRollback")

        img = QImage(100, 100, QImage.Format.Format_RGB32)
        pix = QPixmap.fromImage(img)

        mock_window = MagicMock()
        mock_window.save_current_project_state.return_value = False

        snip_mgr._on_snip_completed(
            cropped_pixmap=pix,
            parent_window=mock_window,
            project_manager=self.project_mgr,
            loot_manager=self.loot_mgr,
            target_ip="10.10.10.10",
        )

        mock_window.save_current_project_state.assert_not_called()

        # The capture remains available for the AppController to persist.
        loot_dir = self.project_mgr.get_project_dir("BoxRollback") / "loot"
        self.assertEqual(len(list(loot_dir.glob("*.png"))), 1)
        self.assertEqual(len(self.loot_mgr.get_all_entries()), 1)

    # -------------------------------------------------------------------------
    # 31. Session Load Performs Zero Disk Writes
    # -------------------------------------------------------------------------
    def test_session_load_does_not_persist(self):
        """
        Adversarial: ProjectSessionService.load_project_session must strictly populate
        in-memory state without triggering storage write operations.
        """
        from unittest.mock import MagicMock
        from core.project_session_service import ProjectSessionService

        mock_storage = MagicMock()
        self.loot_mgr.storage = mock_storage
        self.clip_watcher.storage = mock_storage

        session_service = ProjectSessionService(
            project_manager=self.project_mgr,
            loot_manager=self.loot_mgr,
            clipboard_history=self.clip_watcher,
        )

        self.project_mgr.create_project("BoxLoadNoWrite")
        mock_storage.save_json.reset_mock()

        session_service.load_project_session("BoxLoadNoWrite")
        # Load operation must NOT call storage.save_json
        mock_storage.save_json.assert_not_called()

    # -------------------------------------------------------------------------
    # 32. Clipboard Metadata Derived From Text
    # -------------------------------------------------------------------------
    def test_clipboard_metadata_is_derived_from_text(self):
        """
        Adversarial: Stored / untrusted metadata in clipboard entries must be derived
        from canonical text rather than blindly accepted.
        """
        from core.validators import validate_clipboard_entry

        malicious = {
            "text": "single line command",
            "char_count": 999999,
            "lines_count": 999999,
            "is_multiline": True,
        }
        res = validate_clipboard_entry(malicious)
        self.assertIsNotNone(res)
        self.assertEqual(res["char_count"], len("single line command"))
        self.assertEqual(res["lines_count"], 1)
        self.assertFalse(res["is_multiline"])

    # -------------------------------------------------------------------------
    # 34. Isolated EventBus per Container Instance
    # -------------------------------------------------------------------------
    def test_event_bus_instances_are_isolated(self):
        """
        Adversarial: Separate ServiceContainer instances must have isolated EventBuses.
        """
        from core.container import ServiceContainer

        c1 = ServiceContainer.create_production(config_dir=self.temp_path / "c1_cfg")
        c2 = ServiceContainer.create_production(config_dir=self.temp_path / "c2_cfg")

        self.assertIsNot(
            c1.event_bus, c2.event_bus, "Container instances must not share singleton EventBus"
        )

        from core.logger import close_log_handlers

        close_log_handlers()

    # -------------------------------------------------------------------------
    # =========================================================================
    # v15 Regression Tests
    # =========================================================================

    # -------------------------------------------------------------------------
    # 37. v15-P0: ScreenshotManager emits signal without saving project state
    # -------------------------------------------------------------------------

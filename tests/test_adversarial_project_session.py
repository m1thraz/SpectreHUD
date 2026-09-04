import os
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch


os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QImage, QPixmap, QColor

from core.config import ConfigManager
from core.project import ProjectManager, InvalidProjectNameError
from core.loot_manager import LootManager
from core.clipboard_history import ClipboardHistory
from core.screenshot_manager import ScreenshotManager
from core.project_session_service import ProjectSessionService
from core.report_file_manager import ReportFileManager, ReportBackupError


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

    # -------------------------------------------------------------------------
    # 1. Project-name validation
    # -------------------------------------------------------------------------
    def test_project_name_validation_keeps_paths_in_workspace(self):
        """
        Invalid project names must not resolve outside the workspace or create
        files and folders in its parent directory.
        """
        invalid_names = [
            "..",
            "../pwned",
            "   ",
            "foo\\bar",
        ]

        from core.project import InvalidProjectNameError

        for bad_name in invalid_names:
            with self.assertRaises(InvalidProjectNameError):
                self.project_mgr.create_project(bad_name, allow_existing=True)

            with self.assertRaises(InvalidProjectNameError):
                self.project_mgr.get_project_dir(bad_name)

        # Invalid input must not create anything beside the workspace.
        parent_entries = [
            p.name for p in self.projects_dir.parent.iterdir() if p.name != "projects"
        ]
        self.assertNotIn("pwned", parent_entries)
        self.assertNotIn("recon", parent_entries)
        self.assertNotIn("exploit", parent_entries)
        self.assertNotIn("notes.md", parent_entries)

    def test_invalid_project_operations_do_not_mutate_default(self):
        """Mutating or loading with an invalid name must never silently target Default."""
        self.project_mgr.save_project_state("Default", {"target_ip": "10.10.10.10"})
        before = self.project_mgr.load_project_state("Default")

        for invalid_name in ("../../evil", "..\\evil", "   "):
            with self.assertRaises(InvalidProjectNameError):
                self.project_mgr.activate_project(invalid_name)
            with self.assertRaises(InvalidProjectNameError):
                self.project_mgr.load_project_state(invalid_name)
            with self.assertRaises(InvalidProjectNameError):
                self.project_mgr.save_project_state(invalid_name, {"target_ip": "9.9.9.9"})

        self.assertEqual(self.project_mgr.load_project_state("Default"), before)

    # -------------------------------------------------------------------------
    # 2. P2: Screenshot Filename Collisions
    # -------------------------------------------------------------------------
    def test_screenshot_names_are_unique(self):
        """
        Adversarial: Rapid back-to-back screenshot captures within the exact same
        second must generate distinct filenames and never overwrite previous evidence.
        """
        self.project_mgr.create_project("BoxTarget")
        self.project_mgr.activate_project("BoxTarget")

        dummy_widget = QWidget()
        img = QImage(50, 50, QImage.Format.Format_RGB32)
        img.fill(QColor("magenta"))
        pixmap = QPixmap.fromImage(img)

        # Fire 3 screenshots in rapid succession
        for _ in range(3):
            self.screen_mgr._on_snip_completed(
                cropped_pixmap=pixmap,
                parent_window=dummy_widget,
                project_manager=self.project_mgr,
                loot_manager=self.loot_mgr,
                target_ip="10.10.10.10",
            )

        loot_dir = self.project_mgr.get_project_dir("BoxTarget") / "loot"
        png_files = list(loot_dir.glob("screenshot_*.png"))

        # Collision Invariant: Exactly 3 unique PNG files must exist
        self.assertEqual(
            len(png_files),
            3,
            f"Screenshot collision occurred: found {len(png_files)} files, expected 3",
        )
        self.assertEqual(len(self.loot_mgr.get_all_entries()), 3)

    # -------------------------------------------------------------------------
    # 3. P2: Fail-Closed Report Backup Guarantee
    # -------------------------------------------------------------------------
    def test_report_regeneration_requires_successful_backup(self):
        """
        Adversarial: If backing up an existing report.md fails (e.g. disk write failure),
        regenerate MUST fail closed by raising ReportBackupError and MUST NOT overwrite
        the user's existing handcrafted report notes.
        """
        rfm = ReportFileManager(self.project_mgr)
        self.project_mgr.create_project("BoxPentest")
        original_report = "# Handcrafted Critical Pentest Writeup\n\n- Sensitive findings here."
        rfm.save(original_report, "BoxPentest")

        # Simulate backup failure
        with patch.object(rfm, "backup", return_value=False):
            with self.assertRaises(ReportBackupError):
                rfm.regenerate(self.loot_mgr, self.clip_watcher, "BoxPentest")

        # Data Safety Invariant: Original file must remain untouched
        self.assertEqual(rfm.load("BoxPentest"), original_report)

    # -------------------------------------------------------------------------
    # 4. P3: Semantic Schema Recovery from Malformed JSON
    # -------------------------------------------------------------------------
    def test_malformed_project_state_is_recovered(self):
        """
        Adversarial: When project_state.json contains syntactically valid but semantically
        poisoned data (str instead of list, int instead of str, nulls, missing keys),
        the session service and managers MUST self-heal into a valid schema without crashing.
        """
        self.project_mgr.create_project("BoxPoisoned")
        proj_dir = self.project_mgr.get_project_dir("BoxPoisoned")
        state_file = proj_dir / "project_state.json"

        # Write poisoned schema
        poisoned_data = {
            "name": "BoxPoisoned",
            "target_ip": 1337,  # int instead of str
            "attacker_ip": None,  # None instead of str
            "port": 8080,  # int instead of str
            "loot": "banana",  # str instead of list[dict]
            "clipboard_history": 42,  # int instead of list[dict]
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(poisoned_data, f)

        # Load session
        loaded_state = self.session_service.load_project_session("BoxPoisoned")

        # Self-Healing Schema Invariants
        self.assertIsInstance(loaded_state["loot"], list)
        self.assertEqual(loaded_state["loot"], [])
        self.assertIsInstance(loaded_state["clipboard_history"], list)
        self.assertEqual(loaded_state["clipboard_history"], [])
        self.assertEqual(loaded_state["target_ip"], "1337")

        # Manager Operation Invariants: Managers must operate without TypeErrors
        self.loot_mgr.add_entry("credentials", "Test Cred", "admin:admin")
        self.assertEqual(len(self.loot_mgr.get_all_entries()), 1)
        self.clip_watcher.add_entry("ls -la")
        self.assertEqual(len(self.clip_watcher.get_all_history()), 1)

    def test_restart_recovers_from_corrupt_registry_and_project_state(self):
        """A new process instance must recover safely from corrupted persisted JSON."""
        self.project_mgr.create_project("BoxRestart")
        project_dir = self.project_mgr.get_project_dir("BoxRestart")
        (project_dir / "project_state.json").write_text("{not valid json", encoding="utf-8")
        self.project_mgr.registry_file.write_text("[not a registry]", encoding="utf-8")

        restarted_manager = ProjectManager(base_dir=self.projects_dir, config_dir=self.config_dir)
        recovered_state = restarted_manager.load_project_state("BoxRestart")

        self.assertIn("BoxRestart", restarted_manager.list_projects())
        self.assertEqual(recovered_state["name"], "BoxRestart")
        self.assertEqual(recovered_state["loot"], [])
        persisted_registry = json.loads(restarted_manager.registry_file.read_text(encoding="utf-8"))
        self.assertIn("BoxRestart", persisted_registry)

    def test_workspace_loss_while_running_fails_closed_without_crashing(self):
        """Saving after the configured workspace disappears must report failure safely."""
        self.project_mgr.create_project("BoxWorkspaceLoss")
        self.project_mgr.activate_project("BoxWorkspaceLoss")

        workspace = self.project_mgr.base_dir
        for child in workspace.iterdir():
            if child.is_dir():
                import shutil

                shutil.rmtree(child)
            else:
                child.unlink()
        workspace.rmdir()
        workspace.write_text("workspace is unavailable", encoding="utf-8")

        self.assertFalse(
            self.project_mgr.save_project_state("BoxWorkspaceLoss", {"target_ip": "10.10.10.10"})
        )

    def test_project_switch_rolls_back_when_report_load_fails(self):
        """A broken report must not leave the application switched to a half-loaded project."""
        from unittest.mock import MagicMock, patch
        from core.event_bus import EventBus, EventType
        from ui.coordinators.workspace_coordinator import WorkspaceCoordinator

        self.project_mgr.create_project("BoxReportOld")
        self.project_mgr.create_project("BoxReportBroken")
        self.project_mgr.activate_project("BoxReportOld")
        report_ctrl = MagicMock()
        report_ctrl.confirm_discard_if_dirty.return_value = True
        report_ctrl.load_project.side_effect = RuntimeError("corrupted report.md")
        project_ctrl = MagicMock()
        event_bus = EventBus()
        events = []
        event_bus.subscribe(EventType.PROJECT_CHANGED, events.append)
        coordinator = WorkspaceCoordinator(
            project_manager=self.project_mgr,
            session_service=MagicMock(save_project_session=MagicMock(return_value=True)),
            project_ctrl=project_ctrl,
            report_ctrl=report_ctrl,
            event_bus=event_bus,
        )

        with patch("ui.coordinators.workspace_coordinator.QMessageBox.critical"):
            switched = coordinator.switch_to_project(
                "BoxReportBroken", QWidget(), variables_provider=lambda: {}
            )

        self.assertFalse(switched)
        self.assertEqual(self.project_mgr.get_active_project(), "BoxReportOld")
        project_ctrl.update_project_combo.assert_called_once()
        self.assertEqual(events, [])

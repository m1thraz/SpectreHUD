"""
Tests for headless WorkspaceApplicationService.

Validates atomic project switching, typed failure reasons, pre-switch persistence,
and guaranteed rollback on unlock cancellation/failure, report load failure,
or session load failure.
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core.event_bus import EventBus, EventType, ProjectChangedPayload
from core.project import (
    PersistFailureReason,
    PersistResult,
    ProjectManager,
    ProjectSessionService,
    ProjectStateLoadError,
    WorkspaceApplicationService,
    WorkspaceSwitchFailureReason,
)


class TestWorkspaceApplicationService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.event_bus = EventBus()
        self.project_mgr = ProjectManager(
            base_dir=self.temp_path / "projects",
            event_bus=self.event_bus,
        )
        self.project_mgr.create_project("Box1", target_ip="10.10.10.1")
        self.project_mgr.create_project("Box2", target_ip="10.10.10.2")
        self.project_mgr.activate_project("Box1")

        self.session_service = MagicMock(spec=ProjectSessionService)
        self.session_service.save_project_session.return_value = PersistResult.ok()
        self.session_service.load_project_session.return_value = (
            self.project_mgr.load_project_state("Box1")
        )

        self.report_loader = MagicMock()

        self.service = WorkspaceApplicationService(
            project_manager=self.project_mgr,
            session_service=self.session_service,
            report_loader=self.report_loader,
            event_bus=self.event_bus,
        )

    def tearDown(self):
        self.event_bus.clear()
        self.temp_dir.cleanup()

    def test_switch_to_same_project_returns_failure(self):
        result = self.service.switch_to_project("Box1")
        self.assertFalse(result)
        self.assertFalse(result.success)
        self.assertEqual(result.failure_reason, WorkspaceSwitchFailureReason.SAME_PROJECT)
        self.assertEqual(result.active_project, "Box1")
        self.assertFalse(result.rollback_performed)

    def test_switch_to_non_existent_project_returns_target_not_found(self):
        result = self.service.switch_to_project("GhostBox")
        self.assertFalse(result)
        self.assertEqual(result.failure_reason, WorkspaceSwitchFailureReason.TARGET_NOT_FOUND)
        self.assertEqual(self.project_mgr.active_project, "Box1")
        self.assertFalse(result.rollback_performed)

    def test_successful_switch_loads_report_and_session(self):
        events = []
        self.event_bus.subscribe(EventType.PROJECT_CHANGED, lambda p: events.append(p))

        result = self.service.switch_to_project(
            "Box2",
            variables={"target_ip": "10.10.10.2"},
        )

        self.assertTrue(result)
        self.assertTrue(result.success)
        self.assertEqual(result.previous_project, "Box1")
        self.assertEqual(result.active_project, "Box2")
        self.assertIsNone(result.failure_reason)
        self.assertFalse(result.rollback_performed)
        self.assertEqual(self.project_mgr.active_project, "Box2")

        self.report_loader.assert_called_with("Box2")
        self.session_service.load_project_session.assert_called_with("Box2")

        # The final event should announce phase="loaded" for Box2
        self.assertIn(
            ProjectChangedPayload(project_name="Box2", phase="loaded"),
            events,
        )

    def test_pre_switch_save_failure_aborts_without_activating_target(self):
        self.session_service.save_project_session.return_value = PersistResult.failed(
            PersistFailureReason.DISK_FULL
        )

        result = self.service.switch_to_project(
            "Box2",
            variables={"target_ip": "10.10.10.1"},
            force_discard=False,
        )

        self.assertFalse(result)
        self.assertEqual(result.failure_reason, WorkspaceSwitchFailureReason.PRE_SWITCH_SAVE_FAILED)
        self.assertEqual(self.project_mgr.active_project, "Box1")
        self.assertFalse(result.rollback_performed)
        self.report_loader.assert_not_called()

    def test_pre_switch_save_failure_with_force_discard_continues(self):
        self.session_service.save_project_session.return_value = PersistResult.failed(
            PersistFailureReason.DISK_FULL
        )

        result = self.service.switch_to_project(
            "Box2",
            variables={"target_ip": "10.10.10.1"},
            force_discard=True,
        )

        self.assertTrue(result)
        self.assertEqual(self.project_mgr.active_project, "Box2")

    def test_unlock_cancellation_rolls_back_to_previous_project_and_key(self):
        """Simulates cancelling the unlock dialog and verifies complete rollback."""
        events = []
        self.event_bus.subscribe(EventType.PROJECT_CHANGED, lambda p: events.append(p))

        # Box1 has an active session key
        self.project_mgr.lock_service.set_session_key("Box1", b"secret-box1-key")

        with patch.object(self.project_mgr, "is_pentest_mode", return_value=True):
            with patch.object(self.project_mgr, "is_project_unlocked", return_value=False):
                unlock_mock = MagicMock(return_value="cancelled")

                result = self.service.switch_to_project("Box2", unlock_callback=unlock_mock)

        self.assertFalse(result)
        self.assertEqual(result.failure_reason, WorkspaceSwitchFailureReason.UNLOCK_CANCELLED)
        self.assertTrue(result.rollback_performed)
        self.assertEqual(result.active_project, "Box1")

        # Crucial: ProjectManager active project must be restored to Box1, NOT remain on Box2!
        self.assertEqual(self.project_mgr.active_project, "Box1")
        # Session key for Box1 must be restored in lock_service
        self.assertEqual(
            self.project_mgr.lock_service.get_session_key("Box1"),
            b"secret-box1-key",
        )

        # Event bus must reflect that Box1 was restored as activated, and Box2 was never marked loaded
        self.assertEqual(events[-1], ProjectChangedPayload(project_name="Box1", phase="activated"))
        self.assertFalse(any(e.project_name == "Box2" and e.phase == "loaded" for e in events))
        self.report_loader.assert_not_called()

    def test_unlock_failure_rolls_back_to_previous_project(self):
        with patch.object(self.project_mgr, "is_pentest_mode", return_value=True):
            with patch.object(self.project_mgr, "is_project_unlocked", return_value=False):
                unlock_mock = MagicMock(return_value=False)

                result = self.service.switch_to_project("Box2", unlock_callback=unlock_mock)

        self.assertFalse(result)
        self.assertEqual(result.failure_reason, WorkspaceSwitchFailureReason.UNLOCK_FAILED)
        self.assertTrue(result.rollback_performed)
        self.assertEqual(self.project_mgr.active_project, "Box1")

    def test_report_load_failure_rolls_back_to_previous_project(self):
        self.report_loader.side_effect = RuntimeError("Report file is corrupted")

        result = self.service.switch_to_project("Box2")

        self.assertFalse(result)
        self.assertEqual(result.failure_reason, WorkspaceSwitchFailureReason.REPORT_LOAD_FAILED)
        self.assertTrue(result.rollback_performed)
        self.assertEqual(self.project_mgr.active_project, "Box1")
        self.assertIn("corrupted", result.error_message)

    def test_session_load_failure_rolls_back_to_previous_project(self):
        self.session_service.load_project_session.side_effect = [
            ProjectStateLoadError("Invalid schema", PersistFailureReason.SCHEMA_MISMATCH),
            self.project_mgr.load_project_state("Box1"),  # for rollback
        ]

        result = self.service.switch_to_project("Box2")

        self.assertFalse(result)
        self.assertEqual(result.failure_reason, WorkspaceSwitchFailureReason.SESSION_LOAD_FAILED)
        self.assertTrue(result.rollback_performed)
        self.assertEqual(self.project_mgr.active_project, "Box1")


if __name__ == "__main__":
    unittest.main()

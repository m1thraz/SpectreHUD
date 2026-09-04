"""
Unit tests for WorkspaceCoordinator.
Validates project switching, session persistence, Pentest-Mode unlocking,
rollback handling on load failure, and workspace directory transactions.
"""

import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget, QMessageBox, QPushButton

app = QApplication.instance()
if app is None:
    app = QApplication([])

from core.config import ConfigManager
from core.project import ProjectManager
from core.project.validator import WorkspaceError
from core.project_session_service import ProjectSessionService
from core.project_lock_service import ProjectSecurityMetaError
from core.event_bus import EventBus, EventType
from ui.coordinators.workspace_coordinator import WorkspaceCoordinator


class TestWorkspaceCoordinator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path)

        self.event_bus = EventBus()
        self.config = ConfigManager(config_dir=self.temp_path)
        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.project_mgr.create_project("Box1", target_ip="10.10.10.1")
        self.project_mgr.create_project("Box2", target_ip="10.10.10.2")
        self.project_mgr.active_project = "Box1"

        self.session_service = MagicMock(spec=ProjectSessionService)
        self.session_service.load_project_session.return_value = {"target_ip": "10.10.10.1"}
        self.session_service.save_project_session.return_value = True

        self.project_ctrl = MagicMock()
        self.report_ctrl = MagicMock()
        self.report_ctrl.confirm_discard_if_dirty.return_value = True

        self.coord = WorkspaceCoordinator(
            project_manager=self.project_mgr,
            session_service=self.session_service,
            project_ctrl=self.project_ctrl,
            report_ctrl=self.report_ctrl,
            event_bus=self.event_bus,
        )
        self.window = QWidget()

    def tearDown(self):
        self.event_bus.clear()
        self.window.deleteLater()
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        self.temp_dir.cleanup()

    def test_load_active_project_session_regular(self):
        """load_active_project_session loads session when no unlock is needed."""
        state = self.coord.load_active_project_session(self.window)
        self.assertEqual(state, {"target_ip": "10.10.10.1"})
        self.session_service.load_project_session.assert_called_with("Box1")

    def test_unlock_project_if_needed_flows(self):
        """_unlock_project_if_needed tests already unlocked, cancel, retry, success, and error."""
        # 1. Project does not need unlock
        self.assertTrue(self.coord._unlock_project_if_needed("Box1", self.window))

        # 2. Window is None but needs unlock -> returns False
        with patch.object(self.project_mgr, "is_pentest_mode", return_value=True):
            with patch.object(self.project_mgr, "is_project_unlocked", return_value=False):
                self.assertFalse(self.coord._unlock_project_if_needed("Box1", None))

        # 3. Security meta error -> critical messagebox
        with patch.object(self.project_mgr, "is_pentest_mode", side_effect=ProjectSecurityMetaError("corrupted")):
            with patch("ui.coordinators.workspace_coordinator.QMessageBox.critical") as mock_crit:
                res = self.coord._unlock_project_if_needed("Box1", self.window)
                self.assertFalse(res)
                mock_crit.assert_called_once()

        # 4. Dialog cancelled
        with patch.object(self.project_mgr, "is_pentest_mode", return_value=True):
            with patch.object(self.project_mgr, "is_project_unlocked", return_value=False):
                with patch("ui.coordinators.workspace_coordinator.ProjectUnlockDialog") as MockDlg:
                    mock_dlg = MagicMock()
                    mock_dlg.exec.return_value = 0
                    MockDlg.return_value = mock_dlg
                    res = self.coord._unlock_project_if_needed("Box1", self.window)
                    self.assertFalse(res)

        # 5. Wrong password then correct password
        with patch.object(self.project_mgr, "is_pentest_mode", return_value=True):
            with patch.object(self.project_mgr, "is_project_unlocked", return_value=False):
                with patch("ui.coordinators.workspace_coordinator.ProjectUnlockDialog") as MockDlg:
                    mock_dlg = MagicMock()
                    mock_dlg.exec.return_value = 1
                    mock_dlg.get_password.return_value = "secret"
                    MockDlg.return_value = mock_dlg

                    attempts = [False, True]

                    def fake_unlock(name, pwd):
                        return attempts.pop(0)

                    with patch.object(self.project_mgr, "unlock_project", side_effect=fake_unlock):
                        with patch("ui.coordinators.workspace_coordinator.QMessageBox.warning") as mock_warn:
                            res = self.coord._unlock_project_if_needed("Box1", self.window)
                            self.assertTrue(res)
                            mock_warn.assert_called_once()

    def test_switch_to_project_same_project_no_op(self):
        """switch_to_project returns False if switching to currently active project."""
        self.assertFalse(
            self.coord.switch_to_project("Box1", self.window, lambda: {})
        )

    def test_switch_to_project_dirty_report_rejected(self):
        """switch_to_project returns False if user declines discarding dirty report."""
        self.report_ctrl.confirm_discard_if_dirty.return_value = False
        self.assertFalse(
            self.coord.switch_to_project("Box2", self.window, lambda: {})
        )

    def test_switch_to_project_save_failure_dialog(self):
        """switch_to_project prompts user when saving previous project state fails."""
        self.session_service.save_project_session.return_value = False

        # User cancels switch
        with patch("ui.coordinators.workspace_coordinator.QMessageBox.exec", return_value=QMessageBox.StandardButton.Cancel):
            res = self.coord.switch_to_project("Box2", self.window, lambda: {})
            self.assertFalse(res)
            self.project_ctrl.update_project_combo.assert_called_once()

        # User confirms switch (Yes)
        with patch("ui.coordinators.workspace_coordinator.QMessageBox.exec", return_value=QMessageBox.StandardButton.Yes):
            res = self.coord.switch_to_project("Box2", self.window, lambda: {})
            self.assertTrue(res)
            self.assertEqual(self.project_mgr.active_project, "Box2")

    def test_switch_to_project_activation_error(self):
        """switch_to_project shows error dialog if project activation fails."""
        with patch.object(self.project_mgr, "activate_project", side_effect=Exception("not found")):
            with patch("ui.coordinators.workspace_coordinator.QMessageBox.critical") as mock_crit:
                res = self.coord.switch_to_project("NonExistent", self.window, lambda: {})
                self.assertFalse(res)
                mock_crit.assert_called_once()

    def test_switch_to_project_report_load_failure_rollback(self):
        """switch_to_project rolls back to previous project if report loading fails."""
        self.report_ctrl.load_project.side_effect = Exception("corrupt report")
        with patch("ui.coordinators.workspace_coordinator.QMessageBox.critical") as mock_crit:
            res = self.coord.switch_to_project("Box2", self.window, lambda: {})
            self.assertFalse(res)
            mock_crit.assert_called_once()
            # Verified previous project was restored
            self.assertEqual(self.project_mgr.active_project, "Box1")
            self.project_ctrl.update_project_combo.assert_called()

    def test_switch_to_project_success_flow(self):
        """switch_to_project successfully switches, executes callback, and emits signals."""
        events = []
        self.event_bus.subscribe(EventType.PROJECT_CHANGED, lambda d: events.append(d))

        signal_projects = []
        self.coord.project_changed.connect(lambda p: signal_projects.append(p))

        callbacks = []
        res = self.coord.switch_to_project(
            "Box2",
            self.window,
            lambda: {"target_ip": "10.10.10.1"},
            on_success_callback=lambda p: callbacks.append(p),
        )
        self.assertTrue(res)
        self.assertEqual(self.project_mgr.active_project, "Box2")
        self.assertEqual(callbacks, ["Box2"])
        self.assertEqual(signal_projects, ["Box2"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["project_name"], "Box2")

    def test_apply_workspace_setting_invalid_path(self):
        """apply_workspace_setting shows warning on invalid workspace path."""
        with patch("ui.coordinators.workspace_coordinator.validate_workspace_directory", side_effect=WorkspaceError("invalid")):
            with patch("ui.coordinators.workspace_coordinator.QMessageBox.warning") as mock_warn:
                res = self.coord.apply_workspace_setting(
                    "/invalid/path", self.config, self.window, lambda: None, lambda: None, lambda: None
                )
                self.assertFalse(res)
                mock_warn.assert_called_once()

    def test_apply_workspace_setting_same_workspace(self):
        """apply_workspace_setting returns True if workspace directory is unchanged."""
        current_dir = str(self.project_mgr.base_dir)
        res = self.coord.apply_workspace_setting(
            current_dir, self.config, self.window, lambda: None, lambda: None, lambda: None
        )
        self.assertTrue(res)

    def test_apply_workspace_setting_success_and_empty_workspace(self):
        """apply_workspace_setting switches workspace and creates Default if empty."""
        new_dir = self.temp_path / "new_workspace"
        new_dir.mkdir()

        session_loads = []
        filter_refreshes = []
        content_refreshes = []

        res = self.coord.apply_workspace_setting(
            str(new_dir),
            self.config,
            self.window,
            load_session=lambda: session_loads.append(True),
            refresh_filters=lambda: filter_refreshes.append(True),
            refresh_content=lambda: content_refreshes.append(True),
        )
        self.assertTrue(res)
        self.assertEqual(self.project_mgr.base_dir, new_dir.resolve())
        self.assertTrue(len(session_loads) > 0)
        self.assertTrue(len(filter_refreshes) > 0)
        self.assertTrue(len(content_refreshes) > 0)
        self.assertEqual(self.config.get("workspace_dir"), str(new_dir.resolve()))
        # Default project should have been created in the empty workspace
        self.assertTrue((new_dir / "Default").is_dir())

    def test_apply_workspace_setting_rollback_on_failure(self):
        """apply_workspace_setting rolls back to original workspace on error."""
        original_base = self.project_mgr.base_dir
        new_dir = self.temp_path / "failing_workspace"
        new_dir.mkdir()

        with patch.object(self.config, "set", side_effect=Exception("config save fail")):
            with patch("ui.coordinators.workspace_coordinator.QMessageBox.warning") as mock_warn:
                res = self.coord.apply_workspace_setting(
                    str(new_dir),
                    self.config,
                    self.window,
                    load_session=lambda: None,
                    refresh_filters=lambda: None,
                    refresh_content=lambda: None,
                )
                self.assertFalse(res)
                mock_warn.assert_called_once()
                self.assertEqual(self.project_mgr.base_dir, original_base)

    def test_show_project_menu_and_open_dialog_delegation(self):
        """show_project_menu and open_new_project_dialog delegate to project_ctrl."""
        btn = QPushButton()
        self.coord.show_project_menu(btn, self.window, lambda p: None, lambda: None)
        self.project_ctrl.show_project_menu.assert_called_once()

        self.coord.open_new_project_dialog(self.window, "10.10.10.1", "10.10.14.2", "4444", lambda p: None)
        self.project_ctrl.open_new_project_dialog.assert_called_once()

    def test_switch_to_project_missing_folder_prompt(self):
        """switch_to_project displays folder missing warning when active project directory removed."""
        self.session_service.save_project_session.return_value = False
        with patch.object(self.project_mgr, "project_exists", return_value=False):
            with patch("ui.coordinators.workspace_coordinator.QMessageBox.exec", return_value=QMessageBox.StandardButton.Cancel):
                res = self.coord.switch_to_project("Box2", self.window, lambda: {})
                self.assertFalse(res)

    def test_switch_to_project_target_unlock_failed(self):
        """switch_to_project resets combo and aborts if target project unlock fails."""
        with patch.object(self.coord, "_unlock_project_if_needed", return_value=False):
            res = self.coord.switch_to_project("Box2", self.window, lambda: {})
            self.assertFalse(res)
            self.project_ctrl.update_project_combo.assert_called()

    def test_apply_workspace_setting_restore_failure_critical(self):
        """apply_workspace_setting shows critical error when both switch and restore fail."""
        new_dir = self.temp_path / "double_fail_workspace"
        new_dir.mkdir()

        with patch.object(self.config, "set", side_effect=Exception("switch error")):
            with patch.object(self.project_mgr, "activate_project", side_effect=Exception("restore error")):
                with patch("ui.coordinators.workspace_coordinator.QMessageBox.critical") as mock_crit:
                    res = self.coord.apply_workspace_setting(
                        str(new_dir),
                        self.config,
                        self.window,
                        load_session=lambda: None,
                        refresh_filters=lambda: None,
                        refresh_content=lambda: None,
                    )
                    self.assertFalse(res)
                    mock_crit.assert_called_once()


if __name__ == "__main__":
    unittest.main()

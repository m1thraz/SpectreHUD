import os
import json
import unittest
import tempfile
from pathlib import Path

import pytest

# Ensure Qt runs headlessly in test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from unittest.mock import patch

from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project import ProjectManager
from core.screenshot_manager import ScreenshotManager
from core.report_file_manager import ReportFileManager
from core.storage import PersistenceError
from ui.main_window import MainWindow

pytestmark = pytest.mark.integration


class TestWorkflowInvariants(unittest.TestCase):
    """
    Workflow Invariant & Behavior Tests:
    Guarantees that core user workflows (multi-project switching, data isolation,
    report modification, backup & restore, dirty state guards) cannot break silently.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base_path = Path(self.temp_dir.name)

        self.config_dir = self.base_path / "config"
        self.projects_dir = self.base_path / "projects"

        self.config_mgr = ConfigManager(config_dir=self.config_dir)
        self.snippet_mgr = SnippetManager()
        self.project_mgr = ProjectManager(base_dir=self.projects_dir)
        self.loot_mgr = LootManager(storage_file=self.config_dir / "loot.json")
        self.clip_watcher = ClipboardWatcher(storage_file=self.config_dir / "clipboard.json")
        self.screen_mgr = ScreenshotManager()

        self.window = MainWindow(
            config_manager=self.config_mgr,
            snippet_manager=self.snippet_mgr,
            loot_manager=self.loot_mgr,
            clipboard_watcher=self.clip_watcher,
            project_manager=self.project_mgr,
            screenshot_manager=self.screen_mgr,
        )

    def tearDown(self):
        if hasattr(self, "window") and self.window:
            from unittest.mock import patch

            with patch("PyQt6.QtWidgets.QMessageBox.exec", return_value=0):
                self.window.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Invariant 1: Multi-Project Workspace & State Isolation
    # -------------------------------------------------------------------------
    def test_screenshot_to_loot_and_report_pipeline(self):
        """
        Invariant:
        - When a screenshot is added, its image file is located inside projects/<box>/loot/
        - Loot entry format is Markdown image reference: ![Title](loot/screenshot_*.png)
        - Exported/regenerated report embeds the screenshot path correctly.
        """
        self.project_mgr.create_project("BoxScreenTest")
        self.window.app.switch_to_project("BoxScreenTest")
        proj_dir = self.project_mgr.get_project_dir("BoxScreenTest")

        # Simulate screenshot creation
        loot_dir = proj_dir / "loot"
        loot_dir.mkdir(parents=True, exist_ok=True)
        img_file = loot_dir / "screenshot_20260825_120000.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\nFakePngData")

        entry = self.loot_mgr.add_entry(
            entry_type="screenshot",
            category="recon",
            title="Nmap Port Scan Screenshot",
            content="![Nmap Port Scan Screenshot](loot/screenshot_20260825_120000.png)",
            target_ip="10.10.10.77",
        )
        self.assertEqual(entry["type"], "screenshot")

        # Generate report
        rfm = ReportFileManager(self.project_mgr)
        report_text = rfm.regenerate(self.loot_mgr, self.clip_watcher, "BoxScreenTest")

        # Invariant: Image embedding must be preserved in markdown report
        self.assertIn(
            "![Nmap Port Scan Screenshot](loot/screenshot_20260825_120000.png)", report_text
        )
        self.assertTrue((proj_dir / "loot" / "screenshot_20260825_120000.png").exists())

    # -------------------------------------------------------------------------
    # Invariant 6: Single Source of Truth - No Global JSON Leakage
    # -------------------------------------------------------------------------
    def test_single_source_of_truth_no_global_leakage(self):
        """
        Invariant:
        - project_state.json in the project directory is the SOLE source of truth.
        - No global 'loot_sessions.json' or 'clipboard_history.json' files are created in the root config directory.
        """
        self.project_mgr.create_project("BoxSingleTruth", target_ip="10.10.10.77")
        self.window.app.switch_to_project("BoxSingleTruth")

        self.loot_mgr.add_entry(
            entry_type="note", title="Secret Note", content="confidential", category="recon"
        )
        self.clip_watcher.add_entry("curl http://10.10.10.77/admin", target_ip="10.10.10.77")
        self.window.app.save_current_project_state()

        # Check project state file
        proj_dir = self.project_mgr.get_project_dir("BoxSingleTruth")
        state_file = proj_dir / "project_state.json"
        self.assertTrue(state_file.exists())

        # Verify no global state files exist in config dir
        config_dir = self.config_mgr.config_dir
        self.assertFalse((config_dir / "loot_sessions.json").exists())
        self.assertFalse((config_dir / "clipboard_history.json").exists())

    # -------------------------------------------------------------------------
    # Invariant 7 (v15-P0): Workspace switch — active project validated in new workspace
    # -------------------------------------------------------------------------
    def test_workspace_switch_validates_active_project(self):
        """
        v15-P0: After switching base_dir to a new workspace that does not contain the
        current active_project, the active project must be reset to an available project
        (not left pointing to a non-existent location).
        """
        self.project_mgr.create_project("BoxOldWS")
        self.project_mgr.activate_project("BoxOldWS")

        # Second workspace with a different project under self.base_path so it survives tearDown
        new_ws = self.base_path / "valid_second_workspace"
        new_ws.mkdir(parents=True, exist_ok=True)
        new_proj_dir = new_ws / "NewWSProject"
        new_proj_dir.mkdir(parents=True, exist_ok=True)
        (new_proj_dir / "loot").mkdir(parents=True, exist_ok=True)
        (new_proj_dir / "reports").mkdir(parents=True, exist_ok=True)

        self.window.app._on_settings_applied({"workspace_dir": str(new_ws)})

        self.assertEqual(self.project_mgr.base_dir, new_ws.resolve())
        self.assertEqual(self.project_mgr.get_active_project(), "NewWSProject")
        self.assertTrue((new_ws / self.project_mgr.get_active_project()).is_dir())
        self.assertEqual(self.config_mgr.get("workspace_dir"), str(new_ws.resolve()))

    # -------------------------------------------------------------------------
    # Invariant 8 (v15-P0): Workspace switch — pre-commit rollback restores old state
    # -------------------------------------------------------------------------
    def test_workspace_switch_rolls_back_on_precommit_failure(self):
        """
        A runtime failure before the workspace config commit must restore the old backend.
        """
        from unittest.mock import patch

        self.project_mgr.create_project("RollbackBox")
        self.project_mgr.activate_project("RollbackBox")
        old_base = self.project_mgr.base_dir
        self.config_mgr.set("workspace_dir", str(old_base))

        new_ws = self.base_path / "new_workspace"
        new_ws.mkdir()
        with patch.object(
            self.window.app,
            "load_active_project_state",
            side_effect=[RuntimeError("session failure"), None],
        ):
            with patch("ui.coordinators.workspace_coordinator.QMessageBox.warning"):
                self.window.app._on_settings_applied({"workspace_dir": str(new_ws)})

        self.assertEqual(self.project_mgr.base_dir, old_base)
        self.assertEqual(self.project_mgr.get_active_project(), "RollbackBox")
        self.assertEqual(self.config_mgr.get("workspace_dir"), str(old_base))

    def test_workspace_config_failure_restores_old_session_and_ui(self):
        """A failed final workspace commit must reload the old session into the UI."""
        self.project_mgr.create_project("BoxOldSession", target_ip="10.10.10.10")
        self.window.app.switch_to_project("BoxOldSession")
        old_loot = self.loot_mgr.add_entry("note", "Old loot", "root.txt", target_ip="10.10.10.10")
        old_history = self.clip_watcher.add_entry("whoami", target_ip="10.10.10.10")
        self.window.app.save_current_project_state()
        old_base = self.project_mgr.base_dir
        self.config_mgr.set("workspace_dir", str(old_base))

        new_workspace = self.base_path / "new_workspace"
        new_config = self.base_path / "new_workspace_config"
        new_manager = ProjectManager(base_dir=new_workspace, config_dir=new_config)
        new_manager.create_project("BoxNewSession", target_ip="10.10.10.20")
        new_manager.save_project_state(
            "BoxNewSession",
            {
                "target_ip": "10.10.10.20",
                "loot": [
                    {"id": "loot_new", "type": "note", "title": "New loot", "content": "user.txt"}
                ],
                "clipboard_history": [{"id": "clip_new", "text": "id", "target_ip": "10.10.10.20"}],
            },
        )

        with patch.object(
            self.config_mgr, "set", side_effect=PersistenceError("config disk unavailable")
        ):
            with patch("ui.coordinators.workspace_coordinator.QMessageBox.warning"):
                self.window.app._on_settings_applied({"workspace_dir": str(new_workspace)})

        self.assertEqual(self.project_mgr.base_dir, old_base)
        self.assertEqual(self.project_mgr.get_active_project(), "BoxOldSession")
        self.assertEqual(
            [entry["id"] for entry in self.loot_mgr.get_all_entries()], [old_loot["id"]]
        )
        self.assertEqual(
            [entry["id"] for entry in self.clip_watcher.get_all_history()], [old_history["id"]]
        )
        self.assertEqual(self.window.var_bar.txt_target.text(), "10.10.10.10")

    def test_workspace_config_failure_does_not_persist_new_workspace_registry(self):
        """A failed workspace commit must not leave discovered projects in the registry."""
        old_base = self.project_mgr.base_dir
        self.config_mgr.set("workspace_dir", str(old_base))
        new_workspace = self.base_path / "registry_side_effect_workspace"
        new_config = self.base_path / "registry_side_effect_config"
        new_manager = ProjectManager(base_dir=new_workspace, config_dir=new_config)
        new_manager.create_project("BoxRegistrySideEffect")

        with patch.object(
            self.config_mgr, "set", side_effect=PersistenceError("config disk unavailable")
        ):
            with patch("ui.coordinators.workspace_coordinator.QMessageBox.warning"):
                self.window.app._on_settings_applied({"workspace_dir": str(new_workspace)})

        self.assertEqual(self.project_mgr.base_dir, old_base)
        self.assertNotIn("BoxRegistrySideEffect", self.project_mgr.registry)
        with self.project_mgr.registry_file.open(encoding="utf-8") as registry_file:
            self.assertNotIn("BoxRegistrySideEffect", json.load(registry_file))


if __name__ == "__main__":
    unittest.main()

import os
import unittest
import tempfile
from pathlib import Path
from typing import Dict, Any

# Ensure Qt runs headlessly in test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QMessageBox
from unittest.mock import patch

from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
from core.screenshot_manager import ScreenshotManager
from core.report_file_manager import ReportFileManager
from ui.main_window import MainWindow
from ui.report_editor_tab import ReportEditorTab


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
            screenshot_manager=self.screen_mgr
        )

    def tearDown(self):
        if hasattr(self, 'window') and self.window:
            self.window.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Invariant 1: Multi-Project Workspace & State Isolation
    # -------------------------------------------------------------------------
    def test_multi_project_data_and_state_isolation(self):
        """
        Invariant: Data created in Project A (Loot, Clipboard, Variables) must
        NEVER leak into Project B or Project C, and must persist across project switches.
        """
        # 1. Setup Project Alpha
        self.project_mgr.create_project("BoxAlpha", target_ip="10.10.10.101", attacker_ip="10.10.14.1", port="4444")
        self.window._switch_to_project("BoxAlpha")
        
        self.loot_mgr.add_entry(
            entry_type="credentials",
            category="access",
            title="Alpha Admin",
            content="admin:AlphaSecret123!",
            target_ip="10.10.10.101"
        )
        self.clip_watcher.add_entry("nmap -sC -sV 10.10.10.101", target_ip="10.10.10.101")
        self.window._save_current_project_state()

        # 2. Setup Project Beta
        self.project_mgr.create_project("BoxBeta", target_ip="10.10.10.202", attacker_ip="10.10.14.2", port="8080")
        self.window._switch_to_project("BoxBeta")
        
        # Verify BoxBeta starts clean and isolated
        self.assertEqual(len(self.loot_mgr.get_all_entries()), 0, "BoxBeta must not inherit BoxAlpha loot")
        self.assertEqual(len(self.clip_watcher.get_all_history()), 0, "BoxBeta must not inherit BoxAlpha clipboard")
        self.assertEqual(self.window.var_bar.txt_target.text(), "10.10.10.202")
        self.assertEqual(self.window.var_bar.txt_port.text(), "8080")

        self.loot_mgr.add_entry(
            entry_type="flag",
            category="post_exploit",
            title="Beta Root Flag",
            content="HTB{b3t4_fl4g_9999}",
            target_ip="10.10.10.202"
        )
        self.clip_watcher.add_entry("gobuster dir -u http://10.10.10.202", target_ip="10.10.10.202")
        self.window._save_current_project_state()

        # 3. Switch back to BoxAlpha -> Invariant: Complete Restoration of Alpha
        self.window._switch_to_project("BoxAlpha")
        alpha_loot = self.loot_mgr.get_all_entries()
        alpha_clip = self.clip_watcher.get_all_history()
        
        self.assertEqual(len(alpha_loot), 1)
        self.assertEqual(alpha_loot[0]["title"], "Alpha Admin")
        self.assertNotIn("Beta Root Flag", [e["title"] for e in alpha_loot])
        
        self.assertEqual(len(alpha_clip), 1)
        self.assertIn("10.10.10.101", alpha_clip[0]["text"])
        self.assertEqual(self.window.var_bar.txt_target.text(), "10.10.10.101")
        self.assertEqual(self.window.var_bar.txt_port.text(), "4444")

        # 4. Switch back to BoxBeta -> Invariant: Complete Restoration of Beta
        self.window._switch_to_project("BoxBeta")
        beta_loot = self.loot_mgr.get_all_entries()
        beta_clip = self.clip_watcher.get_all_history()
        
        self.assertEqual(len(beta_loot), 1)
        self.assertEqual(beta_loot[0]["title"], "Beta Root Flag")
        self.assertNotIn("Alpha Admin", [e["title"] for e in beta_loot])
        self.assertEqual(self.window.var_bar.txt_target.text(), "10.10.10.202")
        self.assertEqual(self.window.var_bar.txt_port.text(), "8080")

    # -------------------------------------------------------------------------
    # Invariant 2: Multi-Project Report File Isolation
    # -------------------------------------------------------------------------
    def test_multi_project_report_file_isolation(self):
        """
        Invariant: Editing report.md in BoxAlpha must not overwrite or bleed into BoxBeta.
        """
        rfm = ReportFileManager(self.project_mgr)

        self.project_mgr.create_project("BoxAlpha")
        self.project_mgr.create_project("BoxBeta")

        alpha_text = "# BoxAlpha Report\n\nManual findings for Alpha."
        beta_text = "# BoxBeta Report\n\nManual findings for Beta."

        rfm.save(alpha_text, "BoxAlpha")
        rfm.save(beta_text, "BoxBeta")

        # Verify disk isolation
        self.assertEqual(rfm.load("BoxAlpha"), alpha_text)
        self.assertEqual(rfm.load("BoxBeta"), beta_text)

        # Verify UI editor tab synchronization on switch
        self.window._switch_to_project("BoxAlpha")
        self.assertEqual(self.window.report_editor_tab.editor.toPlainText(), alpha_text)

        self.window._switch_to_project("BoxBeta")
        self.assertEqual(self.window.report_editor_tab.editor.toPlainText(), beta_text)

    # -------------------------------------------------------------------------
    # Invariant 3: Report Regeneration, Automatic Backup & Restoration
    # -------------------------------------------------------------------------
    def test_report_regeneration_backup_and_restore_lifecycle(self):
        """
        Invariant:
        - When user customizes report.md and regenerates from loot, a .bak backup is ALWAYS created.
        - Previous manual notes are NEVER lost.
        - Backup can be restored to exact prior state.
        """
        rfm = ReportFileManager(self.project_mgr)
        self.project_mgr.create_project("BoxBackupTest")
        self.project_mgr.activate_project("BoxBackupTest")

        # Step 1: User writes manual writeup notes
        manual_notes = "# Custom Writeup Notes\n\n- Manual exploit chain step 1\n- Critical pivot notes"
        rfm.save(manual_notes, "BoxBackupTest")
        self.assertTrue(rfm.exists("BoxBackupTest"))
        self.assertFalse(rfm.get_backup_path("BoxBackupTest").exists())

        # Step 2: Add some loot and trigger regeneration
        self.loot_mgr.add_entry(
            entry_type="credentials",
            category="recon",
            title="FTP Anonymous",
            content="anonymous:guest",
            target_ip="10.10.10.50"
        )

        regenerated_content = rfm.regenerate(self.loot_mgr, self.clip_watcher, "BoxBackupTest")

        # Invariant Assertions:
        # 1. Backup was created
        backup_path = rfm.get_backup_path("BoxBackupTest")
        self.assertTrue(backup_path.exists(), "report.md.bak must exist after regeneration")
        
        # 2. Backup contains 100% of the manual notes
        backup_content = backup_path.read_text(encoding="utf-8")
        self.assertEqual(backup_content, manual_notes, "Backup must preserve original manual content")

        # 3. New report contains fresh loot
        self.assertIn("FTP Anonymous", regenerated_content)
        self.assertIn("anonymous:guest", regenerated_content)

        # Step 3: User restores from backup
        restore_success = rfm.restore_backup("BoxBackupTest")
        self.assertTrue(restore_success)
        restored_content = rfm.load("BoxBackupTest")
        self.assertEqual(restored_content, manual_notes, "Restored report must match original manual notes exactly")

    # -------------------------------------------------------------------------
    # Invariant 4: Report Dirty State Protection Guard
    # -------------------------------------------------------------------------
    def test_report_editor_dirty_state_guard(self):
        """
        Invariant:
        - If report editor has unsaved changes, confirm_discard_if_dirty() blocks project switch
          if user cancels (QMessageBox.No), and allows switch if user accepts (QMessageBox.Yes).
        """
        self.project_mgr.create_project("BoxDirty1")
        self.project_mgr.create_project("BoxDirty2")
        self.window._switch_to_project("BoxDirty1")

        editor_tab = self.window.report_editor_tab
        self.assertFalse(editor_tab.is_dirty())

        # User types changes in editor
        editor_tab.editor.setPlainText("Unsaved critical pentest notes...")
        self.assertTrue(editor_tab.is_dirty(), "Editor must be dirty after manual text edits")

        # Simulate user cancelling discard when switching project
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.No):
            self.window._switch_to_project("BoxDirty2")
            # Invariant: Project switch was aborted to protect unsaved work
            self.assertEqual(self.project_mgr.get_active_project(), "BoxDirty1")
            self.assertEqual(editor_tab.editor.toPlainText(), "Unsaved critical pentest notes...")

        # Simulate user saving report
        editor_tab.save()
        self.assertFalse(editor_tab.is_dirty(), "Editor must not be dirty after save")

        # Now switch should succeed without prompt
        self.window._switch_to_project("BoxDirty2")
        self.assertEqual(self.project_mgr.get_active_project(), "BoxDirty2")

    # -------------------------------------------------------------------------
    # Invariant 5: Screenshot to Loot & Report Pipeline Invariant
    # -------------------------------------------------------------------------
    def test_screenshot_to_loot_and_report_pipeline(self):
        """
        Invariant:
        - When a screenshot is added, its image file is located inside projects/<box>/loot/
        - Loot entry format is Markdown image reference: ![Title](loot/screenshot_*.png)
        - Exported/regenerated report embeds the screenshot path correctly.
        """
        self.project_mgr.create_project("BoxScreenTest")
        self.window._switch_to_project("BoxScreenTest")
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
            target_ip="10.10.10.77"
        )
        self.assertEqual(entry["type"], "screenshot")

        # Generate report
        rfm = ReportFileManager(self.project_mgr)
        report_text = rfm.regenerate(self.loot_mgr, self.clip_watcher, "BoxScreenTest")

        # Invariant: Image embedding must be preserved in markdown report
        self.assertIn("![Nmap Port Scan Screenshot](loot/screenshot_20260825_120000.png)", report_text)
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
        self.window._switch_to_project("BoxSingleTruth")

        self.loot_mgr.add_entry(entry_type="note", title="Secret Note", content="confidential", category="recon")
        self.clip_watcher.add_entry("curl http://10.10.10.77/admin", target_ip="10.10.10.77")
        self.window._save_current_project_state()

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

        # Second workspace with a different project
        import tempfile
        with tempfile.TemporaryDirectory() as new_ws_tmp:
            new_ws = Path(new_ws_tmp) / "projects"
            new_ws.mkdir(parents=True, exist_ok=True)
            (new_ws / "NewWSProject").mkdir()

            self.window.app._on_settings_applied({"workspace_dir": str(new_ws)})

            self.assertEqual(self.project_mgr.base_dir, new_ws.resolve())
            self.assertEqual(self.project_mgr.get_active_project(), "NewWSProject")
            self.assertTrue((new_ws / self.project_mgr.get_active_project()).is_dir())

    # -------------------------------------------------------------------------
    # Invariant 8 (v15-P0): Workspace switch — rollback on failure restores old state
    # -------------------------------------------------------------------------
    def test_workspace_switch_rolls_back_on_invalid_path(self):
        """
        v15-P0: If the new workspace directory is invalid (does not exist, fails validation),
        base_dir must be rolled back to the previous value.
        """
        from core.project.validator import WorkspaceError

        from unittest.mock import patch

        self.project_mgr.create_project("RollbackBox")
        self.project_mgr.activate_project("RollbackBox")
        old_base = self.project_mgr.base_dir

        new_ws = self.base_path / "new_workspace"
        new_ws.mkdir()
        with patch.object(self.project_mgr, "sync_registry", side_effect=RuntimeError("registry failure")):
            with patch("ui.app_controller.QMessageBox.warning"):
                self.window.app._on_settings_applied({"workspace_dir": str(new_ws)})

        self.assertEqual(self.project_mgr.base_dir, old_base)
        self.assertEqual(self.project_mgr.get_active_project(), "RollbackBox")


if __name__ == "__main__":
    unittest.main()

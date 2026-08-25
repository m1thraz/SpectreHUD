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
from core.project_manager import ProjectManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.screenshot_manager import ScreenshotManager
from core.project_session_service import ProjectSessionService
from core.report_file_manager import ReportFileManager, ReportBackupError
from core.snippet_manager import SnippetManager
from ui.main_window import MainWindow


class TestAdversarialRegressions(unittest.TestCase):
    """
    Adversarial regression test suite locking in security, data integrity,
    and resilience invariants discovered during architectural hardening.
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
        self.clip_watcher = ClipboardWatcher()
        self.screen_mgr = ScreenshotManager()
        self.session_service = ProjectSessionService(
            self.project_mgr, self.loot_mgr, self.clip_watcher
        )

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        os.environ.pop("SPECTRE_PROJECTS_DIR", None)
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. P1: Workspace Escape & Path Traversal
    # -------------------------------------------------------------------------
    def test_project_name_cannot_escape_workspace(self):
        """
        Adversarial: Malicious or traversal project names ('..', '.', '../escape',
        '..\\escape', '../../../../etc', '   ') must NEVER resolve outside the workspace
        and MUST NOT create any files or folders in parent directories.
        """
        malicious_names = [
            "..",
            ".",
            "...",
            "../pwned",
            "..\\pwned_win",
            "../../../../etc/passwd",
            "   ",
            "---",
            "foo/bar",
            "foo\\bar",
            "\x00hidden"
        ]

        resolved_base = self.projects_dir.resolve()

        for bad_name in malicious_names:
            proj_dir = self.project_mgr.create_project(bad_name)
            resolved_proj = proj_dir.resolve()

            # Boundary Invariant: Must be strictly inside projects_dir
            self.assertTrue(
                resolved_proj.is_relative_to(resolved_base),
                f"Adversarial path traversal escape detected for input {bad_name!r}: {resolved_proj}"
            )

        # File System Invariant: Parent directory of workspace must remain completely untouched
        parent_entries = [p.name for p in self.projects_dir.parent.iterdir() if p.name != "projects"]
        self.assertNotIn("pwned", parent_entries)
        self.assertNotIn("recon", parent_entries)
        self.assertNotIn("exploit", parent_entries)
        self.assertNotIn("notes.md", parent_entries)

    # -------------------------------------------------------------------------
    # 2. P2: Screenshot Filename Collisions
    # -------------------------------------------------------------------------
    def test_screenshot_names_are_unique(self):
        """
        Adversarial: Rapid back-to-back screenshot captures within the exact same
        second must generate distinct filenames and never overwrite previous evidence.
        """
        self.project_mgr.create_project("BoxTarget")
        self.project_mgr.set_active_project("BoxTarget")

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
                target_ip="10.10.10.10"
            )

        loot_dir = self.project_mgr.get_project_dir("BoxTarget") / "loot"
        png_files = list(loot_dir.glob("screenshot_*.png"))

        # Collision Invariant: Exactly 3 unique PNG files must exist
        self.assertEqual(len(png_files), 3, f"Screenshot collision occurred: found {len(png_files)} files, expected 3")
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
            "target_ip": 1337,           # int instead of str
            "attacker_ip": None,         # None instead of str
            "port": 8080,                # int instead of str
            "loot": "banana",            # str instead of list[dict]
            "clipboard_history": 42      # int instead of list[dict]
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

    # -------------------------------------------------------------------------
    # 5. P4: Single Source of Truth & No Global State Leakage
    # -------------------------------------------------------------------------
    def test_single_source_of_truth_no_global_leakage(self):
        """
        Adversarial: Active project operations must never write or leak session loot
        or clipboard history into the global configuration directory.
        """
        self.project_mgr.create_project("BoxSecretWork")
        self.session_service.load_project_session("BoxSecretWork")

        self.loot_mgr.add_entry("flag", "Final Root Flag", "THM{s3cr3t_fl4g}")
        self.clip_watcher.add_entry("cat /root/root.txt")
        self.session_service.save_project_session({"target_ip": "10.10.10.99"}, "BoxSecretWork")

        # Invariant: Data is safely in project directory
        proj_dir = self.project_mgr.get_project_dir("BoxSecretWork")
        self.assertTrue((proj_dir / "project_state.json").exists())

        # Invariant: Global root directory has NO leaked files
        self.assertFalse((self.config_dir / "loot_sessions.json").exists())
        self.assertFalse((self.config_dir / "clipboard_history.json").exists())


if __name__ == "__main__":
    unittest.main()

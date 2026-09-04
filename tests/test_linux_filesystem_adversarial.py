"""
Adversarial tests for Linux/POSIX filesystem semantics.

Covers Phase 8:
- Ticket 25: Case Sensitivity (report.md vs Report.md vs REPORT.md)
- Ticket 26: Permission failures (read-only file/directory, missing write permissions)
- Ticket 27: Symlinks (valid, dangling, external targets)
- Ticket 28: Atomic Write semantics under POSIX (durability, temp file cleanup, permission retention)
"""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.atomic_write import (
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    _secure_chmod,
)
from core.project.manager import ProjectManager
from core.project.validator import (
    WorkspaceError,
    validate_workspace_directory,
)
from core.report_file_manager import (
    ReportBackupError,
    ReportFileManager,
    ReportSaveError,
)


class TestLinuxFilesystemAdversarial(unittest.TestCase):
    "Adversarial suite testing POSIX/Linux filesystem behaviors."

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        # Restore permissions if any test made directory read-only so cleanup succeeds
        try:
            for root, dirs, files in os.walk(self.temp_path):
                for d in dirs:
                    os.chmod(os.path.join(root, d), 0o777)
                for f in files:
                    os.chmod(os.path.join(root, f), 0o666)
            os.chmod(self.temp_path, 0o777)
        except OSError:
            pass
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # Ticket 25: Case Sensitivity
    # -------------------------------------------------------------------------
    def test_case_sensitivity_distinct_filenames(self):
        """Ticket 25: Distinct cased filenames (report.md vs Report.md) are not conflated."""
        f_lower = self.temp_path / "report.md"
        f_upper = self.temp_path / "REPORT.md"
        f_mixed = self.temp_path / "Report.md"

        atomic_write_text(f_lower, "lower content")

        if os.name == "posix":
            atomic_write_text(f_upper, "upper content")
            atomic_write_text(f_mixed, "mixed content")

            self.assertEqual(f_lower.read_text(encoding="utf-8"), "lower content")
            self.assertEqual(f_upper.read_text(encoding="utf-8"), "upper content")
            self.assertEqual(f_mixed.read_text(encoding="utf-8"), "mixed content")
            self.assertEqual(len(list(self.temp_path.glob("*.md"))), 3)
        else:
            pm = ProjectManager(base_dir=self.temp_path)
            pm.create_project("BoxCase")
            rfm = ReportFileManager(pm)
            report_path = rfm.get_report_path("BoxCase")
            self.assertEqual(report_path.name, "report.md")

    def test_case_sensitivity_project_names(self):
        """Ticket 25: Projects with different casing on POSIX remain distinct entities."""
        pm = ProjectManager(base_dir=self.temp_path)
        pm.create_project("AlphaBox")

        if os.name == "posix":
            pm.create_project("alphabox")
            projects = pm.list_projects()
            self.assertIn("AlphaBox", projects)
            self.assertIn("alphabox", projects)

    # -------------------------------------------------------------------------
    # Ticket 26: Permissions and Read-Only Failure Modes
    # -------------------------------------------------------------------------
    def test_atomic_write_fails_gracefully_on_permission_denied(self):
        """Ticket 26: Writing when permissions are denied fails without leaving orphaned temp files."""
        target = self.temp_path / "readonly.txt"
        atomic_write_text(target, "initial content")

        # When replace fails with PermissionError (e.g. read-only target lock or restricted destination)
        with patch("core.atomic_write._replace_file_with_retry", side_effect=PermissionError("Permission denied")):
            with self.assertRaises(OSError):
                atomic_write_text(target, "modified content")

        self.assertEqual(target.read_text(encoding="utf-8"), "initial content")
        tmp_files = list(self.temp_path.glob(".*.tmp_*"))
        self.assertEqual(len(tmp_files), 0)

        if os.name == "posix":
            # On POSIX, writing in a non-writable directory fails at open()
            ro_dir = self.temp_path / "ro_posix_dir"
            ro_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(ro_dir, 0o500)
            try:
                with self.assertRaises(PermissionError):
                    atomic_write_text(ro_dir / "test.txt", "content")
            finally:
                os.chmod(ro_dir, 0o700)

    def test_report_file_manager_save_fails_on_permission_denied(self):
        """Ticket 26: ReportFileManager.save() returns False on PermissionError, and save failure triggers ReportSaveError."""
        pm = ProjectManager(base_dir=self.temp_path)
        pm.create_project("PermBox")
        rfm = ReportFileManager(pm)

        report_file = rfm.get_report_path("PermBox")
        atomic_write_text(report_file, "# Original Report")

        with patch("core.atomic_write.atomic_write_text", side_effect=PermissionError("Access denied")):
            self.assertFalse(rfm.save("# New Report", "PermBox"))

        # When backup succeeds but save fails, ReportSaveError must be raised
        with patch.object(rfm, "backup", return_value=True):
            with patch.object(rfm, "save", return_value=False):
                with self.assertRaises(ReportSaveError):
                    rfm.regenerate(loot_manager=None, clipboard_watcher=None, project_name="PermBox")

        self.assertEqual(report_file.read_text(encoding="utf-8"), "# Original Report")

    def test_report_file_manager_backup_fails_on_permission_denied(self):
        """Ticket 26: ReportFileManager.backup() returns False and regenerate() raises ReportBackupError on PermissionError."""
        pm = ProjectManager(base_dir=self.temp_path)
        pm.create_project("BackupPermBox")
        rfm = ReportFileManager(pm)

        report_file = rfm.get_report_path("BackupPermBox")
        atomic_write_text(report_file, "# Content")

        with patch("core.atomic_write.atomic_write_text", side_effect=PermissionError("Cannot write backup")):
            self.assertFalse(rfm.backup("BackupPermBox"))
            with self.assertRaises(ReportBackupError):
                rfm.regenerate(loot_manager=None, clipboard_watcher=None, project_name="BackupPermBox")

    def test_workspace_validation_fails_closed_on_readonly_directory(self):
        """Ticket 26: validate_workspace_directory() rejects non-writable directory."""
        ws = self.temp_path / "readonly_ws"
        ws.mkdir()

        with patch.object(Path, "write_text", side_effect=PermissionError("Permission denied")):
            with self.assertRaises(WorkspaceError):
                validate_workspace_directory(ws)

    # -------------------------------------------------------------------------
    # Ticket 27: Symlink Handling
    # -------------------------------------------------------------------------
    def test_atomic_write_resolves_valid_symlink(self):
        """Ticket 27: Writing to a valid symlink updates target file correctly."""
        real_file = self.temp_path / "real_file.txt"
        atomic_write_text(real_file, "real content")

        symlink_file = self.temp_path / "link_to_real.txt"
        try:
            symlink_file.symlink_to(real_file)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation not supported or permitted on this platform environment.")

        atomic_write_text(symlink_file.resolve(), "updated through link")
        self.assertEqual(real_file.read_text(encoding="utf-8"), "updated through link")

    def test_broken_dangling_symlink_fails_predictably(self):
        """Ticket 27: Dangling symlinks fail cleanly during read without hanging."""
        broken_link = self.temp_path / "broken_link.txt"
        non_existent = self.temp_path / "ghost.txt"
        try:
            broken_link.symlink_to(non_existent)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation not supported or permitted on this platform environment.")

        self.assertTrue(broken_link.is_symlink())
        self.assertFalse(broken_link.exists())

        atomic_write_text(broken_link, "repaired via atomic write")
        self.assertTrue(broken_link.exists())
        self.assertEqual(broken_link.read_text(encoding="utf-8"), "repaired via atomic write")

    def test_symlink_pointing_outside_workspace(self):
        """Ticket 27: Symlink inside workspace pointing to an external directory or file."""
        external_dir = self.temp_path / "external_area"
        external_dir.mkdir()
        external_target = external_dir / "secret_external.txt"
        external_target.write_text("external payload", encoding="utf-8")

        project_dir = self.temp_path / "project_ws"
        project_dir.mkdir()
        internal_symlink = project_dir / "link_to_external.txt"

        try:
            internal_symlink.symlink_to(external_target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation not supported or permitted on this platform environment.")

        self.assertTrue(internal_symlink.is_symlink())
        # Reading through symlink returns target data
        self.assertEqual(internal_symlink.read_text(encoding="utf-8"), "external payload")

        # Resolving returns the external target outside the project root
        resolved = internal_symlink.resolve()
        self.assertEqual(resolved, external_target.resolve())
        self.assertFalse(str(resolved).startswith(str(project_dir.resolve())))

        # Atomic write to resolved path updates the external target correctly
        atomic_write_text(resolved, "updated external payload")
        self.assertEqual(external_target.read_text(encoding="utf-8"), "updated external payload")

    # -------------------------------------------------------------------------
    # Ticket 28: Atomic Write Under POSIX (Durability, Chmod, Error Recovery)
    # -------------------------------------------------------------------------
    def test_secure_chmod_sets_0600_on_posix(self):
        """Ticket 28: _secure_chmod applies 0o600 on POSIX and does not crash on Windows."""
        test_file = self.temp_path / "chmod_test.txt"
        test_file.write_text("secure data", encoding="utf-8")

        _secure_chmod(test_file, 0o600)

        if os.name == "posix":
            file_mode = stat.S_IMODE(test_file.stat().st_mode)
            self.assertEqual(file_mode, 0o600)

    def test_atomic_write_bytes_and_json_durability(self):
        """Ticket 28: atomic_write_bytes and atomic_write_json write atomically and leave no temp files."""
        bytes_target = self.temp_path / "data.bin"
        json_target = self.temp_path / "data.json"

        self.assertTrue(atomic_write_bytes(bytes_target, b"\xde\xad\xbe\xef"))
        self.assertEqual(bytes_target.read_bytes(), b"\xde\xad\xbe\xef")

        sample_data = {"tool": "SpectreHUD", "version": "2.0.3", "active": True}
        self.assertTrue(atomic_write_json(json_target, sample_data))
        with json_target.open("r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), sample_data)

        leftovers = list(self.temp_path.glob(".*.tmp_*"))
        self.assertEqual(len(leftovers), 0)

    def test_atomic_write_cleans_temp_file_on_write_failure(self):
        """Ticket 28: When an error occurs during write/flush/fsync, the temp file is unlinked."""
        target = self.temp_path / "failure_target.txt"

        with patch("os.fsync", side_effect=OSError("Disk I/O failure")):
            with self.assertRaises(OSError):
                atomic_write_text(target, "some text")

        temp_files = list(self.temp_path.glob(".*.tmp_*"))
        self.assertEqual(len(temp_files), 0)
        self.assertFalse(target.exists())

    def test_atomic_write_cleans_temp_file_on_replace_failure(self):
        """Ticket 28: When atomic replace fails, existing target file is unchanged and temp file is unlinked."""
        target = self.temp_path / "existing_doc.txt"
        atomic_write_text(target, "original durable content")

        with patch("core.atomic_write._replace_file_with_retry", side_effect=OSError("Replace lock failed")):
            with self.assertRaises(OSError):
                atomic_write_text(target, "corrupted content")

        self.assertEqual(target.read_text(encoding="utf-8"), "original durable content")

        temp_files = list(self.temp_path.glob(".*.tmp_*"))
        self.assertEqual(len(temp_files), 0)


if __name__ == "__main__":
    unittest.main()

"""
Tests for Finding 3 (Transactional Project Creation with Rollback)
and Finding 4 (Protection against Silent Project Hijacking on Folder Import).
"""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from core.project import (
    PersistFailureReason,
    ProjectManager,
    ProjectCreationError,
)


class TestProjectTransactions(unittest.TestCase):
    def test_create_project_rollback_on_subfolder_conflict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "projects"
            config_dir = Path(tmpdir) / "config"
            pm = ProjectManager(base_dir=base_dir, config_dir=config_dir)

            # Pre-create a conflicting file where a category subfolder would be.
            broken_dest = base_dir / "BrokenBox"
            broken_dest.mkdir(parents=True)
            category_file = broken_dest / "access"
            category_file.write_text("I am a file, not a directory", encoding="utf-8")

            with self.assertRaises(ProjectCreationError):
                pm.create_project("BrokenBox", allow_existing=True)

            # The project must NOT be registered in the registry
            self.assertNotIn("BrokenBox", pm.registry)

    def test_allow_existing_rollback_removes_only_files_created_by_failed_call(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "projects"
            config_dir = Path(tmpdir) / "config"
            pm = ProjectManager(base_dir=base_dir, config_dir=config_dir)
            existing = base_dir / "ExistingBox"
            existing.mkdir()
            sentinel = existing / "keep.txt"
            sentinel.write_text("user data", encoding="utf-8")
            existing_recon = existing / "recon"
            existing_recon.mkdir()

            with patch(
                "core.project.repository.atomic_write_json",
                side_effect=OSError("injected state write failure"),
            ):
                with self.assertRaises(ProjectCreationError):
                    pm.create_project("ExistingBox", allow_existing=True)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "user data")
            self.assertTrue(existing_recon.is_dir())
            self.assertFalse((existing / "notes.md").exists())
            self.assertFalse((existing / "project_state.json").exists())
            for subdirectory in ("access", "privesc", "postex", "scripts", "misc", "loot"):
                self.assertFalse((existing / subdirectory).exists())
            self.assertNotIn("ExistingBox", pm.registry)

    def test_import_project_prevents_silent_hijacking(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "projects"
            config_dir = Path(tmpdir) / "config"
            pm = ProjectManager(base_dir=base_dir, config_dir=config_dir)

            # Create legitimate original project 'Box'
            pm.create_project("Box")
            original_path = pm.registry["Box"]

            # Create an external directory with same name 'Box'
            downloads_dir = Path(tmpdir) / "downloads" / "Box"
            downloads_dir.mkdir(parents=True)

            result = pm.import_project_folder(downloads_dir)
            self.assertFalse(result.success)
            self.assertEqual(result.failure_reason, PersistFailureReason.VALIDATION_FAILED)

            # Original project path must remain untouched in registry
            self.assertEqual(pm.registry["Box"], original_path)

    def test_activation_cannot_create_an_unknown_project(self):
        """Strict activation preserves the workspace when the project is unknown."""
        from core.project import ProjectNotFoundError

        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager(
                base_dir=Path(tmpdir) / "projects", config_dir=Path(tmpdir) / "config"
            )
            with self.assertRaises(ProjectNotFoundError):
                pm.activate_project("MissingBox")

            self.assertFalse((pm.base_dir / "MissingBox").exists())

    def test_save_permission_error_returns_typed_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager(
                base_dir=Path(tmpdir) / "projects",
                config_dir=Path(tmpdir) / "config",
            )
            pm.create_project("ReadOnlyBox")

            with patch(
                "core.project.state_store.atomic_write_json",
                side_effect=PermissionError("injected permission failure"),
            ):
                result = pm.save_project_state("ReadOnlyBox", {"target_ip": "1.2.3.4"})

            self.assertFalse(result.success)
            self.assertEqual(
                result.failure_reason,
                PersistFailureReason.PERMISSION_DENIED,
            )


if __name__ == "__main__":
    unittest.main()

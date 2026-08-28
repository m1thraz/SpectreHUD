"""
Tests for Finding 3 (Transactional Project Creation with Rollback)
and Finding 4 (Protection against Silent Project Hijacking on Folder Import).
"""

import unittest
import tempfile
from pathlib import Path

from core.project_manager import ProjectManager, ProjectExistsError, ProjectCreationError


class TestProjectTransactions(unittest.TestCase):

    def test_create_project_rollback_on_subfolder_conflict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "projects"
            config_dir = Path(tmpdir) / "config"
            pm = ProjectManager(base_dir=base_dir, config_dir=config_dir)

            # Pre-create a folder with a conflicting file where 'exploit' subfolder would be
            broken_dest = base_dir / "BrokenBox"
            broken_dest.mkdir(parents=True)
            exploit_file = broken_dest / "exploit"
            exploit_file.write_text("I am a file, not a directory", encoding="utf-8")

            with self.assertRaises(ProjectCreationError):
                pm.create_project("BrokenBox", allow_existing=True)

            # The project must NOT be registered in the registry
            self.assertNotIn("BrokenBox", pm.registry)

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

            # Attempting to import external Box must raise ProjectExistsError
            with self.assertRaises(ProjectExistsError):
                pm.import_project_folder(downloads_dir)

            # Original project path must remain untouched in registry
            self.assertEqual(pm.registry["Box"], original_path)

    def test_deprecated_activation_cannot_create_an_unknown_project(self):
        """v15-P0: old activation API warns but preserves strict activation semantics."""
        from core.project import ProjectNotFoundError
        import warnings

        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager(
                base_dir=Path(tmpdir) / "projects",
                config_dir=Path(tmpdir) / "config"
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                with self.assertRaises(ProjectNotFoundError):
                    pm.set_active_project("MissingBox")

            self.assertFalse((pm.base_dir / "MissingBox").exists())


if __name__ == '__main__':
    unittest.main()

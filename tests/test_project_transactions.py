"""
Tests for Finding 3 (Transactional Project Creation with Rollback)
and Finding 4 (Protection against Silent Project Hijacking on Folder Import).
"""

import unittest
import tempfile
from pathlib import Path

from core.project import ProjectManager, ProjectExistsError, ProjectCreationError


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

    def test_activation_cannot_create_an_unknown_project(self):
        """Strict activation preserves the workspace when the project is unknown."""
        from core.project import ProjectNotFoundError

        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager(
                base_dir=Path(tmpdir) / "projects",
                config_dir=Path(tmpdir) / "config"
            )
            with self.assertRaises(ProjectNotFoundError):
                pm.activate_project("MissingBox")

            self.assertFalse((pm.base_dir / "MissingBox").exists())


if __name__ == '__main__':
    unittest.main()

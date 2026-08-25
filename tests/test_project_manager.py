import os
import unittest
import tempfile
from pathlib import Path
from core.project_manager import ProjectManager

class TestProjectManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        os.environ["SPECTRE_PROJECTS_DIR"] = str(self.base_dir)
        self.pm = ProjectManager(base_dir=self.base_dir)

    def tearDown(self):
        os.environ.pop("SPECTRE_PROJECTS_DIR", None)
        self.temp_dir.cleanup()

    def test_default_project_creation(self):
        projects = self.pm.list_projects()
        self.assertIn("Default", projects)

        default_dir = self.pm.get_project_dir("Default")
        self.assertTrue((default_dir / "recon").exists())
        self.assertTrue((default_dir / "exploit").exists())
        self.assertTrue((default_dir / "loot").exists())
        self.assertTrue((default_dir / "notes.md").exists())
        self.assertTrue((default_dir / "project_state.json").exists())

    def test_create_custom_project(self):
        proj_dir = self.pm.create_project("PickleRick", target_ip="10.10.10.80", attacker_ip="10.10.14.99")
        self.assertTrue(proj_dir.exists())
        self.assertIn("PickleRick", self.pm.list_projects())

        state = self.pm.load_project_state("PickleRick")
        self.assertEqual(state["name"], "PickleRick")
        self.assertEqual(state["target_ip"], "10.10.10.80")
        self.assertEqual(state["attacker_ip"], "10.10.14.99")

        notes = (proj_dir / "notes.md").read_text(encoding="utf-8")
        self.assertIn("PickleRick", notes)
        self.assertIn("10.10.10.80", notes)

    def test_save_and_load_state(self):
        self.pm.create_project("Blue", target_ip="10.10.10.40")
        state = self.pm.load_project_state("Blue")
        state["loot"].append({"type": "credentials", "title": "Admin Pass", "content": "admin:P@ss"})
        state["clipboard_history"].append({"text": "nmap -p 445 10.10.10.40"})

        self.pm.save_project_state("Blue", state)

        # Reload
        reloaded = self.pm.load_project_state("Blue")
        self.assertEqual(len(reloaded["loot"]), 1)
        self.assertEqual(reloaded["loot"][0]["title"], "Admin Pass")
        self.assertEqual(len(reloaded["clipboard_history"]), 1)

    def test_active_project_switch(self):
        self.pm.create_project("Lame", target_ip="10.10.10.3")
        self.pm.set_active_project("Lame")
        self.assertEqual(self.pm.get_active_project(), "Lame")

        self.pm.set_active_project("Default")
        self.assertEqual(self.pm.get_active_project(), "Default")

    def test_path_traversal_prevention_double_dot(self):
        """Invariant: Project name '..' must NEVER escape base projects directory."""
        proj_dir = self.pm.create_project("..")
        self.assertTrue(proj_dir.resolve().is_relative_to(self.base_dir.resolve()))
        self.assertEqual(proj_dir.name, "Default")

        # Verify nothing was created outside base_dir
        parent_items = list(self.base_dir.parent.iterdir())
        self.assertNotIn("recon", [p.name for p in parent_items if p.is_dir()])
        self.assertNotIn("exploit", [p.name for p in parent_items if p.is_dir()])

    def test_path_traversal_prevention_nested_traversal(self):
        """Invariant: Traversal payloads ('../foo', '....', '..\\..\\') must remain sandboxed."""
        dangerous_names = [
            "..",
            ".",
            "...",
            "../secret",
            "..\\evil",
            "../../../../etc",
            "   ",
            "---",
            "valid_box-123"
        ]

        for name in dangerous_names:
            proj_dir = self.pm.get_project_dir(name)
            self.assertTrue(
                proj_dir.resolve().is_relative_to(self.base_dir.resolve()),
                f"Project directory for {name!r} escaped workspace: {proj_dir}"
            )


if __name__ == "__main__":
    unittest.main()


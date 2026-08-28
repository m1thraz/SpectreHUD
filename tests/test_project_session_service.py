import unittest
import tempfile
from pathlib import Path

from core.project_manager import ProjectManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project_session_service import ProjectSessionService


class TestProjectSessionService(unittest.TestCase):
    """Unit tests verifying ProjectSessionService domain isolation and persistence orchestration."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.projects_dir = self.base_dir / "projects"
        self.config_dir = self.base_dir / "config"

        self.project_manager = ProjectManager(base_dir=self.projects_dir)
        self.loot_manager = LootManager(storage_file=self.config_dir / "loot.json")
        self.clipboard_watcher = ClipboardWatcher(storage_file=self.config_dir / "clip.json")

        self.session_service = ProjectSessionService(
            project_manager=self.project_manager,
            loot_manager=self.loot_manager,
            clipboard_watcher=self.clipboard_watcher
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_load_session(self):
        """Tests that saving session state populates file and loading restores loot and clipboard."""
        self.project_manager.create_project("Box1")
        self.project_manager.activate_project("Box1")

        self.loot_manager.add_entry(
            entry_type="credentials",
            category="access",
            title="SSH Root",
            content="root:password123",
            target_ip="10.10.10.10"
        )
        self.clipboard_watcher.add_entry("ssh root@10.10.10.10", target_ip="10.10.10.10")

        variables = {
            "target_ip": "10.10.10.10",
            "attacker_ip": "10.10.14.5",
            "port": "2222",
            "username": "admin",
            "password": "SecretPassword123"
        }

        # Save session
        self.session_service.save_project_session(variables=variables, project_name="Box1")

        # Clear active memory
        self.loot_manager.set_entries([])
        self.clipboard_watcher.set_history([])

        # Load session
        loaded_state = self.session_service.load_project_session("Box1")

        self.assertEqual(loaded_state.get("target_ip"), "10.10.10.10")
        self.assertEqual(loaded_state.get("port"), "2222")
        self.assertEqual(loaded_state.get("username"), "admin")
        self.assertEqual(loaded_state.get("password"), "SecretPassword123")
        self.assertEqual(len(self.loot_manager.get_all_entries()), 1)
        self.assertEqual(self.loot_manager.get_all_entries()[0]["title"], "SSH Root")
        self.assertEqual(len(self.clipboard_watcher.get_all_history()), 1)
        self.assertIn("ssh root@10.10.10.10", self.clipboard_watcher.get_all_history()[0]["text"])

    def test_session_isolation_across_projects(self):
        """Tests that loading an empty/new project cleans up loot and clipboard in memory."""
        self.project_manager.create_project("Box1")
        self.project_manager.create_project("Box2")

        # Set Box1 state
        self.loot_manager.add_entry(entry_type="flag", category="post_exploit", title="Flag1", content="HTB{flag1}")
        self.session_service.save_project_session(variables={"target_ip": "1.1.1.1"}, project_name="Box1")

        # Switch and load Box2
        self.session_service.load_project_session("Box2")
        self.assertEqual(len(self.loot_manager.get_all_entries()), 0)
        self.assertEqual(len(self.clipboard_watcher.get_all_history()), 0)

        # Switch back to Box1
        self.session_service.load_project_session("Box1")
        self.assertEqual(len(self.loot_manager.get_all_entries()), 1)
        self.assertEqual(self.loot_manager.get_all_entries()[0]["title"], "Flag1")


if __name__ == "__main__":
    unittest.main()

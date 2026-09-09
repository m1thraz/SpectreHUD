import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from core.project import (
    PersistFailureReason,
    ProjectManager,
    ProjectSchemaMismatchError,
)
from core.loot.manager import LootManager
from core.clipboard_history import ClipboardHistory
from core.quick_note_manager import QuickNoteManager
from core.project import ProjectStateCorruptedError
from core.project.session_service import ProjectSessionService, ProjectSessionValidationError


class TestProjectSessionService(unittest.TestCase):
    """Unit tests verifying ProjectSessionService domain isolation and persistence orchestration."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.projects_dir = self.base_dir / "projects"
        self.config_dir = self.base_dir / "config"

        self.project_manager = ProjectManager(base_dir=self.projects_dir)
        self.loot_manager = LootManager(storage_file=self.config_dir / "loot.json")
        self.clipboard_watcher = ClipboardHistory(storage_file=self.config_dir / "clip.json")
        self.quick_note_manager = QuickNoteManager(storage_file=self.config_dir / "notes.json")

        self.session_service = ProjectSessionService(
            project_manager=self.project_manager,
            loot_manager=self.loot_manager,
            clipboard_history=self.clipboard_watcher,
            quick_note_manager=self.quick_note_manager,
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
            target_ip="10.10.10.10",
        )
        self.clipboard_watcher.add_entry("ssh root@10.10.10.10", target_ip="10.10.10.10")
        self.quick_note_manager.add_entry("Investigate SMB share", category="recon", target_ip="10.10.10.10")

        variables = {
            "target_ip": "10.10.10.10",
            "attacker_ip": "10.10.14.5",
            "port": "2222",
            "username": "admin",
            "password": "SecretPassword123",
        }

        # Save session
        self.session_service.save_project_session(variables=variables, project_name="Box1")

        # Clear active memory
        self.loot_manager.replace_entries([])
        self.clipboard_watcher.replace_history([])
        self.quick_note_manager.replace_entries([])

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
        self.assertEqual(len(self.quick_note_manager.get_all_entries()), 1)
        self.assertEqual(self.quick_note_manager.get_all_entries()[0]["text"], "Investigate SMB share")

    def test_session_isolation_across_projects(self):
        """Tests that loading an empty/new project cleans up loot and clipboard in memory."""
        self.project_manager.create_project("Box1")
        self.project_manager.create_project("Box2")

        # Set Box1 state
        self.loot_manager.add_entry(
            entry_type="flag", category="post_exploit", title="Flag1", content="HTB{flag1}"
        )
        self.quick_note_manager.add_entry("Box1 note", category="misc")
        self.session_service.save_project_session(
            variables={"target_ip": "1.1.1.1"}, project_name="Box1"
        )

        # Switch and load Box2
        self.session_service.load_project_session("Box2")
        self.assertEqual(len(self.loot_manager.get_all_entries()), 0)
        self.assertEqual(len(self.clipboard_watcher.get_all_history()), 0)
        self.assertEqual(len(self.quick_note_manager.get_all_entries()), 0)

        # Switch back to Box1
        self.session_service.load_project_session("Box1")
        self.assertEqual(len(self.loot_manager.get_all_entries()), 1)
        self.assertEqual(self.loot_manager.get_all_entries()[0]["title"], "Flag1")
        self.assertEqual(len(self.quick_note_manager.get_all_entries()), 1)
        self.assertEqual(self.quick_note_manager.get_all_entries()[0]["text"], "Box1 note")

    def test_successful_session_save_round_trips_live_loot_without_loss(self):
        """A successful save must preserve every user-created live loot entry verbatim."""
        self.project_manager.create_project("RoundTrip")
        self.loot_manager.add_entry("note", "First", "alpha", target_ip="10.10.10.10")
        self.loot_manager.add_entry("flag", "Second", "HTB{beta}", target_ip="10.10.10.10")
        live_loot = self.loot_manager.get_all_entries()

        result = self.session_service.save_project_session(
            variables={"target_ip": "10.10.10.10"}, project_name="RoundTrip"
        )
        self.assertTrue(result.success)

        reloaded_state = self.project_manager.load_project_state("RoundTrip")
        self.assertEqual(reloaded_state["loot"], live_loot)

    def test_corrupt_state_load_preserves_the_live_session(self):
        project_dir = self.project_manager.create_project("CorruptBox")
        self.loot_manager.add_entry("note", "Live", "keep me", category="recon")
        live_loot = self.loot_manager.get_all_entries()
        (project_dir / "project_state.json").write_text("{not json", encoding="utf-8")

        with self.assertRaises(ProjectStateCorruptedError):
            self.session_service.load_project_session("CorruptBox")

        self.assertEqual(self.loot_manager.get_all_entries(), live_loot)

    def test_component_validation_failure_preserves_entire_live_session(self):
        self.project_manager.create_project("AtomicLoad")
        self.loot_manager.add_entry("note", "Live loot", "keep", category="recon")
        self.clipboard_watcher.add_entry("live clipboard")
        self.quick_note_manager.add_entry("live note", category="misc")
        previous_loot = self.loot_manager.get_all_entries()
        previous_history = self.clipboard_watcher.get_all_history()
        previous_notes = self.quick_note_manager.get_all_entries()

        with patch(
            "core.project.session_service.validate_quick_notes_list",
            side_effect=ValueError("injected quick-note validation failure"),
        ):
            with self.assertRaises(ProjectSessionValidationError) as error:
                self.session_service.load_project_session("AtomicLoad")

        self.assertIs(error.exception.failure_reason, PersistFailureReason.VALIDATION_FAILED)
        self.assertEqual(self.loot_manager.get_all_entries(), previous_loot)
        self.assertEqual(self.clipboard_watcher.get_all_history(), previous_history)
        self.assertEqual(self.quick_note_manager.get_all_entries(), previous_notes)

    def test_missing_project_state_schema_is_migrated_with_backup(self):
        project_dir = self.project_manager.create_project("FutureSchema")
        state_file = project_dir / "project_state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state.pop("schema_version")
        legacy_bytes = json.dumps(state).encode("utf-8")
        state_file.write_bytes(legacy_bytes)

        loaded = self.session_service.load_project_session("FutureSchema")

        self.assertEqual(loaded["schema_version"], 1)
        self.assertEqual(json.loads(state_file.read_text(encoding="utf-8"))["schema_version"], 1)
        backup = project_dir / "project_state.json.pre-schema-v1.bak"
        self.assertEqual(backup.read_bytes(), legacy_bytes)

    def test_unknown_project_state_schema_is_explicit_and_preserves_runtime(self):
        project_dir = self.project_manager.create_project("FutureSchema")
        self.loot_manager.add_entry("note", "Live", "keep", category="recon")
        previous_loot = self.loot_manager.get_all_entries()
        state_file = project_dir / "project_state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["schema_version"] = 999
        state_file.write_text(json.dumps(state), encoding="utf-8")

        with self.assertRaises(ProjectSchemaMismatchError) as error:
            self.session_service.load_project_session("FutureSchema")

        self.assertIs(error.exception.failure_reason, PersistFailureReason.SCHEMA_MISMATCH)
        self.assertEqual(self.loot_manager.get_all_entries(), previous_loot)

    def test_runtime_apply_failure_rolls_back_all_components(self):
        self.project_manager.create_project("ApplyRollback")
        self.loot_manager.add_entry("note", "Live loot", "keep", category="recon")
        self.clipboard_watcher.add_entry("live clipboard")
        self.quick_note_manager.add_entry("live note", category="misc")
        previous_loot = self.loot_manager.get_all_entries()
        previous_history = self.clipboard_watcher.get_all_history()
        previous_notes = self.quick_note_manager.get_all_entries()

        original_replace = self.quick_note_manager.replace_entries
        calls = 0

        def fail_first_replace(entries):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("injected apply failure")
            return original_replace(entries)

        with patch.object(
            self.quick_note_manager,
            "replace_entries",
            side_effect=fail_first_replace,
        ):
            with self.assertRaises(ProjectSessionValidationError):
                self.session_service.load_project_session("ApplyRollback")

        self.assertEqual(self.loot_manager.get_all_entries(), previous_loot)
        self.assertEqual(self.clipboard_watcher.get_all_history(), previous_history)
        self.assertEqual(self.quick_note_manager.get_all_entries(), previous_notes)

    def test_invalid_state_encoding_and_oversized_state_are_rejected(self):
        project_dir = self.project_manager.create_project("InvalidStateBox")
        state_file = project_dir / "project_state.json"

        state_file.write_bytes(b"\xff\xfe\x00")
        with self.assertRaises(ProjectStateCorruptedError):
            self.project_manager.load_project_state("InvalidStateBox")

        state_file.write_text("{}", encoding="utf-8")
        with patch("core.project.state_store.is_file_size_valid", return_value=False):
            with self.assertRaises(ProjectStateCorruptedError):
                self.project_manager.load_project_state("InvalidStateBox")


if __name__ == "__main__":
    unittest.main()

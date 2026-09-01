import os
import json
import unittest
import tempfile
from pathlib import Path
from core.loot_manager import LootLimitError, LootManager, LootValidationError
from core.validators import MAX_CONTENT_LENGTH, MAX_LOOT_ENTRIES
from core.storage import PersistenceError
from unittest.mock import patch


class TestLootManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path)

        self.storage_file = self.temp_path / "test_loot.json"
        self.loot_mgr = LootManager(storage_file=self.storage_file)

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_add_and_update_with_severity(self):
        """Tests adding and updating entries with severity levels."""
        entry = self.loot_mgr.add_entry(
            entry_type="credentials",
            title="Domain Admin Creds",
            content="admin:Pass123",
            severity="critical",
        )
        self.assertEqual(entry["severity"], "critical")

        # Update severity
        updated = self.loot_mgr.update_entry(entry["id"], severity="high")
        self.assertEqual(updated["severity"], "high")

        # Fallback on invalid severity
        updated_fallback = self.loot_mgr.update_entry(entry["id"], severity="invalid_level")
        self.assertEqual(updated_fallback["severity"], "info")

    def test_add_and_get_entry(self):
        entry = self.loot_mgr.add_entry(
            entry_type="credentials",
            title="FTP Admin Login",
            content="admin:P@ssword123",
            target_ip="10.10.10.25",
            category="access",
        )
        self.assertIsNotNone(entry["id"])
        self.assertEqual(entry["category"], "access")
        self.assertEqual(len(self.loot_mgr.entries), 1)

        # Retrieve entries
        entries = self.loot_mgr.get_entries(target_ip="10.10.10.25")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "FTP Admin Login")
        self.assertEqual(entries[0]["content"], "admin:P@ssword123")
        self.assertEqual(entries[0]["category"], "access")

    def test_add_rejects_entry_beyond_persisted_limit(self):
        """The 1001st live entry must not create state that a session save truncates."""
        self.loot_mgr.entries = [
            {"id": f"loot_{index}", "type": "note", "title": "Existing", "content": "safe"}
            for index in range(MAX_LOOT_ENTRIES)
        ]

        with self.assertRaises(LootLimitError):
            self.loot_mgr.add_entry("note", "One too many", "must be rejected")

        self.assertEqual(len(self.loot_mgr.get_all_entries()), MAX_LOOT_ENTRIES)

    def test_add_rejects_content_that_persistence_would_truncate(self):
        oversized = "x" * (MAX_CONTENT_LENGTH + 1)

        with self.assertRaises(LootValidationError):
            self.loot_mgr.add_entry("note", "Too large", oversized)

        self.assertEqual(self.loot_mgr.get_all_entries(), [])

    def test_category_fallback_on_add(self):
        """Invalid or omitted category falls back to 'misc'."""
        e1 = self.loot_mgr.add_entry("note", "Note 1", "Content", category="non_existent_category")
        self.assertEqual(e1["category"], "misc")

        e2 = self.loot_mgr.add_entry("note", "Note 2", "Content")
        self.assertEqual(e2["category"], "misc")

    def test_update_entry(self):
        """update_entry successfully updates fields and recategorizes."""
        entry = self.loot_mgr.add_entry(
            "note", "Old Title", "Old Content", target_ip="10.10.10.1", category="recon"
        )
        entry_id = entry["id"]

        # Update title, content and recategorize to privesc
        updated = self.loot_mgr.update_entry(
            entry_id,
            title="New Title",
            content="New Content",
            category="privesc",
            type="credentials",
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["title"], "New Title")
        self.assertEqual(updated["content"], "New Content")
        self.assertEqual(updated["category"], "privesc")
        self.assertEqual(updated["type"], "credentials")

        # Verify disk persistence
        with open(self.storage_file, "r", encoding="utf-8") as f:
            disk_entries = json.load(f)
        self.assertEqual(disk_entries[0]["title"], "New Title")
        self.assertEqual(disk_entries[0]["category"], "privesc")

        # Invalid category update falls back to misc
        self.loot_mgr.update_entry(entry_id, category="invalid_cat")
        self.assertEqual(self.loot_mgr.entries[0]["category"], "misc")

        # Non-existent ID returns None
        result = self.loot_mgr.update_entry("loot_nonexistent", title="Fail")
        self.assertIsNone(result)

    def test_legacy_migration_and_immediate_persistence(self):
        """Legacy JSON entries without 'category' are migrated on load and immediately written to disk."""
        legacy_file = self.temp_path / "legacy_loot.json"
        raw_legacy_data = [
            {
                "id": "loot_old1",
                "type": "credentials",
                "title": "Legacy Admin",
                "content": "admin:oldpass",
                "target_ip": "10.10.10.10",
                "timestamp": "2026-08-20 12:00:00",
                # Note: No 'category' field
            },
            {
                "id": "loot_old2",
                "type": "flag",
                "category": "unknown_legacy_phase",
                "title": "Legacy Flag",
                "content": "THM{old}",
                "target_ip": "10.10.10.10",
                "timestamp": "2026-08-20 12:05:00",
            },
        ]
        with open(legacy_file, "w", encoding="utf-8") as f:
            json.dump(raw_legacy_data, f)

        # Initialize manager with legacy file -> triggers load & migration
        mgr = LootManager(storage_file=legacy_file)
        self.assertEqual(len(mgr.entries), 2)
        self.assertEqual(mgr.entries[0]["category"], "misc")
        self.assertEqual(mgr.entries[1]["category"], "misc")

        # Check that file on disk was IMMEDIATELY updated without needing manual save
        with open(legacy_file, "r", encoding="utf-8") as f:
            migrated_disk_data = json.load(f)
        self.assertEqual(migrated_disk_data[0]["category"], "misc")
        self.assertEqual(migrated_disk_data[1]["category"], "misc")

    def test_replace_entries_and_persist_migrates_and_immediately_saves(self):
        """The explicitly persistent replacement API migrates entries and saves them."""
        legacy_list = [
            {
                "id": "l_switch_1",
                "type": "credentials",
                "title": "Project Switch Cred",
                "content": "pass123",
            },
            {
                "id": "l_switch_2",
                "type": "dir",
                "category": "bad_cat",
                "title": "Dir",
                "content": "/uploads",
            },
        ]
        self.loot_mgr.replace_entries_and_persist(legacy_list)
        self.assertEqual(len(self.loot_mgr.entries), 2)
        self.assertEqual(self.loot_mgr.entries[0]["category"], "misc")
        self.assertEqual(self.loot_mgr.entries[1]["category"], "misc")
        self.assertEqual(self.loot_mgr.entries[1]["type"], "directory")

        # Verify disk has migrated entries immediately
        with open(self.storage_file, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        self.assertEqual(disk_data[0]["category"], "misc")
        self.assertEqual(disk_data[1]["category"], "misc")
        self.assertEqual(disk_data[1]["type"], "directory")

    def test_replace_entries_persist_failure_does_not_mutate_memory(self):
        """A failed replacement write preserves both the prior RAM and disk state."""
        previous = self.loot_mgr.add_entry("note", "Previous", "must survive")
        replacement = [
            {"id": "loot_new", "type": "note", "title": "New", "content": "must not commit"}
        ]

        with patch.object(self.loot_mgr.storage, "save_json", return_value=False):
            with self.assertRaises(PersistenceError):
                self.loot_mgr.replace_entries_and_persist(replacement)

        self.assertEqual(
            [entry["id"] for entry in self.loot_mgr.get_all_entries()], [previous["id"]]
        )
        self.assertEqual(
            [entry["id"] for entry in self.loot_mgr.storage.load_json("loot")],
            [previous["id"]],
        )

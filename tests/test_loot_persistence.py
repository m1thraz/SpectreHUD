import os
import json
import unittest
import tempfile
from pathlib import Path
from core.loot_manager import LootManager
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

    def test_replace_entries_and_persist_replaces_stored_entries(self):
        self.loot_mgr.replace_entries_and_persist([])
        self.assertEqual(self.loot_mgr.get_all_entries(), [])

    def test_search_and_filter(self):
        self.loot_mgr.add_entry(
            "credentials", "SSH Root", "root:toor", "10.10.10.50", category="access"
        )
        self.loot_mgr.add_entry(
            "hash", "Shadow Root Hash", "$6$rounds=5000$...", "10.10.10.50", category="privesc"
        )
        self.loot_mgr.add_entry(
            "flag", "User Flag", "THM{user_flag_123}", "10.10.10.99", category="access"
        )

        # Filter by type
        creds = self.loot_mgr.get_entries(entry_type="credentials")
        self.assertEqual(len(creds), 1)
        self.assertEqual(creds[0]["title"], "SSH Root")

        # Filter by Category
        privesc_items = self.loot_mgr.get_entries(category="privesc")
        self.assertEqual(len(privesc_items), 1)
        self.assertEqual(privesc_items[0]["title"], "Shadow Root Hash")

        # Filter by Target IP
        target_50 = self.loot_mgr.get_entries(target_ip="10.10.10.50")
        self.assertEqual(len(target_50), 2)

        # Search by keyword
        shadow = self.loot_mgr.get_entries(search_query="shadow")
        self.assertEqual(len(shadow), 1)
        self.assertEqual(shadow[0]["type"], "hash")

    def test_delete_and_clear(self):
        e1 = self.loot_mgr.add_entry("note", "Port 80 Note", "Apache 2.4.41", "10.10.10.10")
        e2 = self.loot_mgr.add_entry("flag", "Root Flag", "THM{root_456}", "10.10.10.10")
        self.assertEqual(len(self.loot_mgr.entries), 2)

        # Delete one
        self.loot_mgr.delete_entry(e1["id"])
        self.assertEqual(len(self.loot_mgr.entries), 1)

        # Clear session
        self.loot_mgr.clear_session()
        self.assertEqual(len(self.loot_mgr.entries), 0)

    def test_reorder_within_category_persists_after_reload(self):
        fourth = self.loot_mgr.add_entry("note", "Fourth", "4", category="recon")
        third = self.loot_mgr.add_entry("note", "Third", "3", category="recon")
        second = self.loot_mgr.add_entry("note", "Second", "2", category="recon")
        first = self.loot_mgr.add_entry("note", "First", "1", category="recon")

        self.loot_mgr.reorder_entry(fourth["id"], "recon", 1)

        reloaded = LootManager(storage_file=self.storage_file)
        ordered = sorted(
            reloaded.get_entries(category="recon"),
            key=lambda entry: entry["position"],
        )
        self.assertEqual(
            [entry["id"] for entry in ordered],
            [first["id"], fourth["id"], second["id"], third["id"]],
        )
        self.assertEqual([entry["position"] for entry in ordered], [0, 1, 2, 3])

    def test_failed_reorder_preserves_previous_memory_order(self):
        second = self.loot_mgr.add_entry("note", "Second", "2", category="recon")
        first = self.loot_mgr.add_entry("note", "First", "1", category="recon")
        original = self.loot_mgr.get_all_entries()

        with patch.object(self.loot_mgr.storage, "save_json", return_value=False):
            with self.assertRaises(PersistenceError):
                self.loot_mgr.reorder_entry(second["id"], "recon", 0)

        self.assertEqual(self.loot_mgr.get_all_entries(), original)
        self.assertEqual(
            [entry["id"] for entry in sorted(original, key=lambda entry: entry["position"])],
            [first["id"], second["id"]],
        )

    def test_legacy_entries_receive_stable_positions_on_load(self):
        legacy_entries = [
            {"id": "first", "type": "note", "category": "recon", "title": "First", "content": "1"},
            {
                "id": "second",
                "type": "note",
                "category": "recon",
                "title": "Second",
                "content": "2",
            },
            {"id": "other", "type": "note", "category": "access", "title": "Other", "content": "3"},
        ]
        self.storage_file.write_text(json.dumps(legacy_entries), encoding="utf-8")

        migrated = LootManager(storage_file=self.storage_file)

        self.assertEqual(
            [(entry["id"], entry["position"]) for entry in migrated.get_all_entries()],
            [("first", 0), ("second", 1), ("other", 0)],
        )
        persisted = json.loads(self.storage_file.read_text(encoding="utf-8"))
        self.assertTrue(all("position" in entry for entry in persisted))

    def test_export_loot_delegation(self):
        """Deprecated export_loot delegates to ReportBuilder."""
        self.loot_mgr.add_entry(
            "credentials", "Web Admin", "admin:Secret!", "10.10.10.30", category="access"
        )
        self.loot_mgr.add_entry(
            "hash", "MySQL Hash", "$mysql$user*...", "10.10.10.30", category="privesc"
        )
        self.loot_mgr.add_entry(
            "directory", "Hidden Endpoint", "/api/v1/admin", "10.10.10.30", category="recon"
        )
        self.loot_mgr.add_entry(
            "flag", "Root Flag", "THM{test_flag}", "10.10.10.30", category="privesc"
        )
        self.loot_mgr.add_entry(
            "screenshot",
            "Gained Root Shell",
            "loot/screenshot_root.png",
            "10.10.10.30",
            category="access",
        )

        export_path = self.temp_path / "loot_export.md"
        result = self.loot_mgr.export_loot(export_path, target_ip="10.10.10.30")

        self.assertTrue(export_path.exists())
        content = export_path.read_text(encoding="utf-8")
        self.assertIn("admin:Secret!", content)
        self.assertIn("$mysql$user*...", content)
        self.assertIn("`/api/v1/admin`", content)
        self.assertIn("THM{test_flag}", content)
        self.assertIn("![Gained Root Shell](loot/screenshot_root.png)", content)
        self.assertIn("10.10.10.30", content)


if __name__ == "__main__":
    unittest.main()

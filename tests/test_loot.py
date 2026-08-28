import os
import json
import unittest
import tempfile
from pathlib import Path
from core.loot_manager import LootManager

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
            severity="critical"
        )
        self.assertEqual(entry["severity"], "critical")

        # Update severity
        updated = self.loot_mgr.update_entry(entry["id"], severity="high")
        self.assertEqual(updated["severity"], "high")

        # Fallback on invalid severity
        updated_fallback = self.loot_mgr.update_entry(entry["id"], severity="invalid_level")
        self.assertEqual(updated_fallback["severity"], "info")


if __name__ == "__main__":
    unittest.main()

    def test_add_and_get_entry(self):
        entry = self.loot_mgr.add_entry(
            entry_type="credentials",
            title="FTP Admin Login",
            content="admin:P@ssword123",
            target_ip="10.10.10.25",
            category="access"
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

    def test_category_fallback_on_add(self):
        """Invalid or omitted category falls back to 'misc'."""
        e1 = self.loot_mgr.add_entry("note", "Note 1", "Content", category="non_existent_category")
        self.assertEqual(e1["category"], "misc")

        e2 = self.loot_mgr.add_entry("note", "Note 2", "Content")
        self.assertEqual(e2["category"], "misc")

    def test_update_entry(self):
        """update_entry successfully updates fields and recategorizes."""
        entry = self.loot_mgr.add_entry("note", "Old Title", "Old Content", target_ip="10.10.10.1", category="recon")
        entry_id = entry["id"]

        # Update title, content and recategorize to privesc
        updated = self.loot_mgr.update_entry(
            entry_id,
            title="New Title",
            content="New Content",
            category="privesc",
            type="credentials"
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
                "timestamp": "2026-08-20 12:00:00"
                # Note: No 'category' field
            },
            {
                "id": "loot_old2",
                "type": "flag",
                "category": "unknown_legacy_phase",
                "title": "Legacy Flag",
                "content": "THM{old}",
                "target_ip": "10.10.10.10",
                "timestamp": "2026-08-20 12:05:00"
            }
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

    def test_set_entries_migration_and_immediate_persistence(self):
        """Calling set_entries (e.g. on project switch) migrates legacy entries and immediately saves to disk."""
        legacy_list = [
            {"id": "l_switch_1", "type": "credentials", "title": "Project Switch Cred", "content": "pass123"},
            {"id": "l_switch_2", "type": "dir", "category": "bad_cat", "title": "Dir", "content": "/uploads"}
        ]
        self.loot_mgr.set_entries(legacy_list)
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

    def test_search_and_filter(self):
        self.loot_mgr.add_entry("credentials", "SSH Root", "root:toor", "10.10.10.50", category="access")
        self.loot_mgr.add_entry("hash", "Shadow Root Hash", "$6$rounds=5000$...", "10.10.10.50", category="privesc")
        self.loot_mgr.add_entry("flag", "User Flag", "THM{user_flag_123}", "10.10.10.99", category="access")

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

    def test_export_loot_delegation(self):
        """Deprecated export_loot delegates to ReportBuilder."""
        self.loot_mgr.add_entry("credentials", "Web Admin", "admin:Secret!", "10.10.10.30", category="access")
        self.loot_mgr.add_entry("hash", "MySQL Hash", "$mysql$user*...", "10.10.10.30", category="privesc")
        self.loot_mgr.add_entry("directory", "Hidden Endpoint", "/api/v1/admin", "10.10.10.30", category="recon")
        self.loot_mgr.add_entry("flag", "Root Flag", "THM{test_flag}", "10.10.10.30", category="privesc")
        self.loot_mgr.add_entry("screenshot", "Gained Root Shell", "loot/screenshot_root.png", "10.10.10.30", category="access")

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

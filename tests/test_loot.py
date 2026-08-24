import unittest
import tempfile
from pathlib import Path
from core.loot_manager import LootManager

class TestLootManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_file = Path(self.temp_dir.name) / "test_loot.json"
        self.loot_mgr = LootManager(storage_file=self.storage_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_and_get_entry(self):
        entry = self.loot_mgr.add_entry(
            entry_type="credentials",
            title="FTP Admin Login",
            content="admin:P@ssword123",
            target_ip="10.10.10.25"
        )
        self.assertIsNotNone(entry["id"])
        self.assertEqual(len(self.loot_mgr.entries), 1)

        # Retrieve entries
        entries = self.loot_mgr.get_entries(target_ip="10.10.10.25")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "FTP Admin Login")
        self.assertEqual(entries[0]["content"], "admin:P@ssword123")

    def test_search_and_filter(self):
        self.loot_mgr.add_entry("credentials", "SSH Root", "root:toor", "10.10.10.50")
        self.loot_mgr.add_entry("hash", "Shadow Root Hash", "$6$rounds=5000$...", "10.10.10.50")
        self.loot_mgr.add_entry("flag", "User Flag", "THM{user_flag_123}", "10.10.10.99")

        # Filter by type
        creds = self.loot_mgr.get_entries(entry_type="credentials")
        self.assertEqual(len(creds), 1)
        self.assertEqual(creds[0]["title"], "SSH Root")

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

    def test_export_loot(self):
        self.loot_mgr.add_entry("credentials", "Web Admin", "admin:Secret!", "10.10.10.30")
        self.loot_mgr.add_entry("flag", "Root Flag", "THM{test_flag}", "10.10.10.30")

        export_path = Path(self.temp_dir.name) / "loot_export.txt"
        result = self.loot_mgr.export_loot(export_path, target_ip="10.10.10.30")
        
        self.assertTrue(export_path.exists())
        content = export_path.read_text(encoding="utf-8")
        self.assertIn("admin:Secret!", content)
        self.assertIn("THM{test_flag}", content)
        self.assertIn("10.10.10.30", content)

if __name__ == "__main__":
    unittest.main()

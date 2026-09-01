import unittest
from core.storage import InMemoryStorageBackend
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.config import ConfigManager


class TestServicesInMemory(unittest.TestCase):
    """
    Verifies that core domain services operate flawlessly in-memory
    without touching the physical disk.
    """

    def test_loot_manager_in_memory(self):
        storage = InMemoryStorageBackend()
        loot_mgr = LootManager(storage=storage)

        # Initially empty
        self.assertEqual(loot_mgr.get_all_entries(), [])

        # Add entries
        e1 = loot_mgr.add_entry(
            entry_type="credentials",
            title="SSH Root",
            content="root:password123",
            target_ip="10.10.10.10",
            category="access",
        )
        self.assertTrue(bool(e1["id"]))
        self.assertEqual(len(loot_mgr.get_all_entries()), 1)

        # Check that storage has the serialized JSON
        stored_raw = storage.load_json("loot")
        self.assertIsNotNone(stored_raw)
        self.assertEqual(len(stored_raw), 1)
        self.assertEqual(stored_raw[0]["title"], "SSH Root")

        # Update entry
        loot_mgr.update_entry(e1["id"], title="Updated SSH Root", content="root:newpass")
        self.assertEqual(loot_mgr.get_all_entries()[0]["title"], "Updated SSH Root")
        self.assertEqual(storage.load_json("loot")[0]["content"], "root:newpass")

        # Delete entry
        loot_mgr.delete_entry(e1["id"])
        self.assertEqual(loot_mgr.get_all_entries(), [])
        self.assertEqual(storage.load_json("loot"), [])

    def test_clipboard_watcher_in_memory(self):
        storage = InMemoryStorageBackend()
        clip_watcher = ClipboardWatcher(storage=storage)

        self.assertEqual(clip_watcher.get_all_history(), [])

        # Add items
        item = clip_watcher.add_entry("nmap -sC -sV 10.10.10.10", target_ip="10.10.10.10")
        self.assertIsNotNone(item)
        self.assertEqual(len(clip_watcher.get_all_history()), 1)

        # Storage persistence check
        stored = storage.load_json("clipboard")
        self.assertIsNotNone(stored)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["text"], "nmap -sC -sV 10.10.10.10")

        # Delete item
        clip_watcher.delete_entry(item["id"])
        self.assertEqual(clip_watcher.get_all_history(), [])
        self.assertEqual(storage.load_json("clipboard"), [])

    def test_config_manager_in_memory(self):
        storage = InMemoryStorageBackend(
            initial_data={
                "config": {"target_ip": "192.168.1.50", "theme": "cyber_dark", "language": "de"}
            }
        )
        config_mgr = ConfigManager(storage=storage)

        self.assertEqual(config_mgr.get("target_ip"), "192.168.1.50")
        self.assertEqual(config_mgr.get("language"), "de")

        # Mutate config
        config_mgr.set("target_ip", "10.10.11.200")
        self.assertEqual(config_mgr.get("target_ip"), "10.10.11.200")

        # Verify reflected in storage
        self.assertEqual(storage.load_json("config")["target_ip"], "10.10.11.200")


if __name__ == "__main__":
    unittest.main()

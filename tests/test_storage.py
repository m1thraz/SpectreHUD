import unittest
import tempfile
from pathlib import Path
from core.storage import InMemoryStorageBackend, FileStorageBackend


class TestStorage(unittest.TestCase):
    """Unit tests verifying InMemoryStorageBackend and FileStorageBackend."""

    def test_in_memory_storage_crud(self):
        storage = InMemoryStorageBackend(initial_data={"init_key": [1, 2, 3]})

        # Initial check
        self.assertTrue(storage.exists("init_key"))
        self.assertEqual(storage.load_json("init_key"), [1, 2, 3])
        self.assertFalse(storage.exists("nonexistent"))
        self.assertIsNone(storage.load_json("nonexistent"))

        # Save new item
        saved = storage.save_json("loot", [{"id": "1", "title": "Root"}])
        self.assertTrue(saved)
        self.assertTrue(storage.exists("loot"))
        self.assertEqual(len(storage.load_json("loot")), 1)

        # Mutation isolation via deep copy
        loaded = storage.load_json("loot")
        loaded.append({"id": "2", "title": "Admin"})
        self.assertEqual(len(storage.load_json("loot")), 1)  # Internal store untouched

        # Delete
        self.assertTrue(storage.delete("loot"))
        self.assertFalse(storage.exists("loot"))
        self.assertFalse(storage.delete("loot"))

        # Clear
        storage.clear()
        self.assertEqual(storage.get_all_keys(), [])

    def test_file_storage_backend_with_base_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            storage = FileStorageBackend(base_dir=base_dir)

            # Save
            self.assertTrue(
                storage.save_json("session", {"active_box": "BoxAlpha", "ip": "10.10.10.1"})
            )
            self.assertTrue((base_dir / "session.json").exists())

            # Load
            data = storage.load_json("session")
            self.assertIsNotNone(data)
            self.assertEqual(data["active_box"], "BoxAlpha")

            # Delete
            self.assertTrue(storage.delete("session"))
            self.assertFalse((base_dir / "session.json").exists())

    def test_file_storage_backend_with_single_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "custom_loot.json"
            storage = FileStorageBackend(single_file_path=file_path)

            self.assertFalse(storage.exists("any_key"))
            self.assertIsNone(storage.load_json("any_key"))

            self.assertTrue(storage.save_json("any_key", ["loot1", "loot2"]))
            self.assertTrue(file_path.exists())

            loaded = storage.load_json("any_key")
            self.assertEqual(loaded, ["loot1", "loot2"])

            storage.clear()
            self.assertFalse(file_path.exists())


if __name__ == "__main__":
    unittest.main()

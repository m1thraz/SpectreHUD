"""
Tests for Finding 2: Transactional Persistence and PersistenceError semantics.
Ensures that storage failures never leave in-memory state mutated while disk I/O failed.
"""

import unittest
import tempfile
from pathlib import Path
from typing import Optional, Any

from core.storage import StorageBackend, PersistenceError
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.project_manager import ProjectManager


class FailingStorageBackend(StorageBackend):
    """Storage backend simulator where save operations always fail."""

    def __init__(self):
        self._store = {}

    def load_json(self, resource_name: str) -> Optional[Any]:
        return self._store.get(resource_name)

    def save_json(self, resource_name: str, data: Any) -> bool:
        return False  # Simulate disk full / permission error

    def exists(self, resource_name: str) -> bool:
        return resource_name in self._store

    def delete(self, resource_name: str) -> bool:
        return False

    def clear(self) -> None:
        self._store.clear()


class TestPersistenceErrors(unittest.TestCase):

    def test_loot_manager_raises_and_rolls_back_on_storage_failure(self):
        backend = FailingStorageBackend()
        manager = LootManager(storage=backend)
        self.assertEqual(len(manager.get_all_entries()), 0)

        with self.assertRaises(PersistenceError):
            manager.add_entry(entry_type="credentials", title="Admin", content="secret")

        # In-memory entries must NOT contain the failed item
        self.assertEqual(len(manager.get_all_entries()), 0)

    def test_clipboard_watcher_raises_and_rolls_back_on_storage_failure(self):
        backend = FailingStorageBackend()
        watcher = ClipboardWatcher(storage=backend)
        self.assertEqual(len(watcher.get_all_history()), 0)

        with self.assertRaises(PersistenceError):
            watcher.add_entry("curl http://target.htb")

        # In-memory history must NOT contain the failed item
        self.assertEqual(len(watcher.get_all_history()), 0)

    def test_config_manager_raises_and_rolls_back_on_storage_failure(self):
        backend = FailingStorageBackend()
        cfg = ConfigManager(storage=backend)
        initial_ip = cfg.get("target_ip")

        with self.assertRaises(PersistenceError):
            cfg.set("target_ip", "1.2.3.4")

        # In-memory config must retain initial value
        self.assertEqual(cfg.get("target_ip"), initial_ip)

    def test_snippet_manager_raises_and_rolls_back_on_disk_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a regular file so trying to mkdir on it as a directory fails
            blocked_file = Path(tmpdir) / "blocked_file"
            blocked_file.write_text("i am a file", encoding="utf-8")
            bad_path = blocked_file / "unwritable.json"

            mgr = SnippetManager(user_snippets_path=bad_path)
            initial_count = len([s for s in mgr.snippets if s.get("is_custom")])

            with self.assertRaises(PersistenceError):
                mgr.add_custom_snippet(title="Failing Snip", template="boom")

            # Must not be in in-memory snippets
            self.assertEqual(len([s for s in mgr.snippets if s.get("is_custom")]), initial_count)

    def test_project_manager_raises_on_registry_save_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager(base_dir=Path(tmpdir) / "projects", config_dir=Path(tmpdir) / "config")
            blocked_file = Path(tmpdir) / "blocked_file"
            blocked_file.write_text("i am a file", encoding="utf-8")
            pm.registry_file = blocked_file / "registry.json"
            
            with self.assertRaises(PersistenceError):
                pm._save_registry()


if __name__ == '__main__':
    unittest.main()

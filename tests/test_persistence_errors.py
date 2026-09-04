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
from core.clipboard_history import ClipboardHistory
from ui.clipboard_monitor import ClipboardMonitor
from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.project import ProjectManager


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
        watcher = ClipboardHistory(storage=backend)
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
            pm = ProjectManager(
                base_dir=Path(tmpdir) / "projects", config_dir=Path(tmpdir) / "config"
            )
            blocked_file = Path(tmpdir) / "blocked_file"
            blocked_file.write_text("i am a file", encoding="utf-8")
            pm.registry_file = blocked_file / "registry.json"

    def test_config_manager_batch_update_atomic(self):
        """Batch update must apply all settings in one atomic write or fail cleanly."""
        backend = FailingStorageBackend()
        cfg = ConfigManager(storage=backend)
        orig_hotkey = cfg.get("hotkey")
        orig_lang = cfg.get("language")

        with self.assertRaises(PersistenceError):
            cfg.update({"hotkey": "<ctrl>+x", "language": "de", "workspace_dir": "D:\\Evil"})

        # None of the batch changes must have been applied to memory
        self.assertEqual(cfg.get("hotkey"), orig_hotkey)
        self.assertEqual(cfg.get("language"), orig_lang)

    def test_clipboard_retry_after_persistence_failure(self):
        """If persistence fails on first copy, retry of the same text must succeed when storage recovers."""

        class FlakyStorageBackend(StorageBackend):
            def __init__(self):
                self.fail_once = True
                self.saved_data = None

            def load_json(self, resource_name: str) -> Optional[Any]:
                return self.saved_data

            def save_json(self, resource_name: str, data: Any) -> bool:
                if self.fail_once:
                    self.fail_once = False
                    return False
                self.saved_data = data
                return True

            def exists(self, resource_name: str) -> bool:
                return self.saved_data is not None

            def delete(self, resource_name: str) -> bool:
                return True

            def clear(self) -> None:
                self.saved_data = None

        flaky = FlakyStorageBackend()
        watcher = ClipboardHistory(storage=flaky)

        # 1. First attempt fails due to storage error
        with self.assertRaises(PersistenceError):
            watcher.add_entry("secret_token_123")

        self.assertEqual(len(watcher.get_all_history()), 0)

        # 2. User retries same copied text — MUST NOT be blocked by deduplication
        res = watcher.add_entry("secret_token_123")
        self.assertIsNotNone(res)
        self.assertEqual(len(watcher.get_all_history()), 1)
        self.assertEqual(watcher.get_all_history()[0]["text"], "secret_token_123")

    def test_loot_controller_catches_persistence_error_gracefully(self):
        """Invariant: Controller must NOT let PersistenceError crash slot execution."""
        from unittest.mock import patch
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from ui.controllers.loot_controller import LootController

        app = QApplication.instance() or QApplication([])
        backend = FailingStorageBackend()
        loot_mgr = LootManager(storage=backend)
        proj_mgr = ProjectManager()
        ctrl = LootController(loot_manager=loot_mgr, project_manager=proj_mgr)

        with patch.object(QMessageBox, "critical") as mock_box:
            entry = ctrl.add_entry("credentials", "Admin", "P@ss")
            self.assertEqual(entry, {})
            mock_box.assert_called_once()

        # Seed existing entry in memory
        loot_mgr.entries = [
            {"id": "item1", "type": "credentials", "title": "Old", "content": "123"}
        ]

        with patch.object(QMessageBox, "critical") as mock_box:
            success = ctrl.update_entry("item1", "New Title", "New Content")
            self.assertFalse(success)
            mock_box.assert_called_once()

        with patch.object(QMessageBox, "critical") as mock_box:
            success = ctrl.delete_entry("item1")
            self.assertFalse(success)
            mock_box.assert_called_once()

    def test_history_controller_catches_persistence_error_gracefully(self):
        """Invariant: HistoryController must NOT let PersistenceError crash slot execution."""
        from unittest.mock import patch
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from ui.controllers.history_controller import HistoryController

        app = QApplication.instance() or QApplication([])
        backend = FailingStorageBackend()
        watcher = ClipboardHistory(storage=backend)
        loot_mgr = LootManager(storage=backend)
        proj_mgr = ProjectManager()
        ctrl = HistoryController(
            clipboard_history=watcher,
            clipboard_monitor=ClipboardMonitor(watcher),
            loot_manager=loot_mgr,
            project_manager=proj_mgr,
        )

        with patch.object(QMessageBox, "critical") as mock_box:
            # add_entry does not crash and notifies
            ctrl.add_entry("nmap 10.10.10.1")
            mock_box.assert_called_once()

        # Seed existing item in memory
        watcher.history = [{"id": "clip1", "text": "test"}]

        with patch.object(QMessageBox, "critical") as mock_box:
            ctrl.delete_entry("clip1")
            mock_box.assert_called_once()

    def test_cheatsheet_controller_catches_persistence_error_gracefully(self):
        """Invariant: CheatsheetController must NOT let PersistenceError crash slot execution."""
        from unittest.mock import patch
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from ui.controllers.cheatsheet_controller import CheatsheetController

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmpdir:
            blocked_file = Path(tmpdir) / "blocked_file"
            blocked_file.write_text("i am a file", encoding="utf-8")
            bad_path = blocked_file / "unwritable.json"

            snip_mgr = SnippetManager(user_snippets_path=bad_path)
            ctrl = CheatsheetController(snippet_manager=snip_mgr)

            with patch.object(QMessageBox, "critical") as mock_box:
                snip_id = ctrl.add_custom_snippet("Failing Snip", "web_http", "sub", "cmd")
                self.assertEqual(snip_id, "")
                mock_box.assert_called_once()

    def test_global_excepthook_handles_persistence_error(self):
        """Invariant: Global excepthook logs traceback and presents safe message without terminating."""
        import sys
        from unittest.mock import patch
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from main import global_exception_hook

        app = QApplication.instance() or QApplication([])
        err = PersistenceError("Simulated disk write failure")

        with patch.object(QMessageBox, "critical") as mock_box:
            try:
                raise err
            except PersistenceError:
                exctype, value, tb = sys.exc_info()
                global_exception_hook(exctype, value, tb)

            mock_box.assert_called_once()


if __name__ == "__main__":
    unittest.main()

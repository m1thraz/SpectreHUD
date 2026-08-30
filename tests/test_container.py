import unittest
import sys
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication

from core.container import ServiceContainer
from ui.main_window import MainWindow

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)


class TestContainer(unittest.TestCase):
    """Unit tests verifying ServiceContainer and Dependency Injection."""

    def tearDown(self):
        from core.logger import close_log_handlers
        close_log_handlers()

    def test_service_container_create_production(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir)
            container = ServiceContainer.create_production(config_dir=config_dir, language="en")

            self.assertIsNotNone(container.config_manager)
            self.assertIsNotNone(container.snippet_manager)
            self.assertIsNotNone(container.project_manager)
            self.assertIsNotNone(container.loot_manager)
            self.assertIsNotNone(container.clipboard_watcher)
            self.assertIsNotNone(container.screenshot_manager)
            self.assertIsNotNone(container.storage)
            self.assertIsNotNone(container.event_bus)

            from core.logger import close_log_handlers
            close_log_handlers()

    def test_service_container_uses_custom_workspace_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir) / "config"
            custom_ws = Path(tmp_dir) / "my_custom_workspace"
            
            # Pre-populate config with custom workspace
            from core.storage import FileStorageBackend
            from core.config import ConfigManager
            st = FileStorageBackend(base_dir=config_dir)
            cfg = ConfigManager(config_dir=config_dir, storage=st)
            cfg.set("workspace_dir", str(custom_ws))

            container = ServiceContainer.create_production(config_dir=config_dir, language="en")
            self.assertEqual(container.project_manager.base_dir.resolve(), custom_ws.resolve())

            from core.logger import close_log_handlers
            close_log_handlers()

    def test_service_container_create_isolated_test_container(self):
        container = ServiceContainer.create_isolated_test_container(
            initial_config={"target_ip": "192.168.1.100", "theme": "cyber_dark"},
            language="en"
        )

        self.assertEqual(container.config_manager.get("target_ip"), "192.168.1.100")
        self.assertIsNotNone(container.event_bus)
        self.assertIsNotNone(container.storage)

        # Test in-memory loot addition
        entry = container.loot_manager.add_entry(
            entry_type="credentials",
            title="InMem Root",
            content="root:toor",
            target_ip="192.168.1.100"
        )
        self.assertTrue(bool(entry["id"]))
        self.assertEqual(len(container.loot_manager.get_all_entries()), 1)

    def test_pure_in_memory_isolation_no_disk_pollution(self):
        """Finding 5: In-memory container must use InMemoryStorageBackend without touching user default paths."""
        from core.storage import InMemoryStorageBackend
        container = ServiceContainer.create_isolated_test_container()
        self.assertIsInstance(container.storage, InMemoryStorageBackend)
        
        # Adding entries in memory should not create user files on disk
        clip = container.clipboard_watcher.add_entry("whoami")
        self.assertIsNotNone(clip)
        self.assertEqual(len(container.clipboard_watcher.get_all_history()), 1)

    def test_main_window_with_in_memory_container(self):
        container = ServiceContainer.create_isolated_test_container(
            initial_config={"target_ip": "10.10.10.200", "theme": "cyber_dark"},
            language="en"
        )
        window = MainWindow(container=container)
        self.assertIsNotNone(window.app)
        self.assertEqual(window.app.config.get("target_ip"), "10.10.10.200")

        # Switch modes
        window.app.switch_mode("loot")
        self.assertEqual(window.app.active_mode, "loot")

        window.app.switch_mode("cheatsheet")
        self.assertEqual(window.app.active_mode, "cheatsheet")

        window.close()


if __name__ == "__main__":
    unittest.main()

"""
Service Container & Dependency Injection Layer for SpectreHUD.

Centralizes lifecycle management, configuration, and dependency composition
for all core domain services, storage backends, and event buses.
"""

from typing import Optional, Dict, Any
from pathlib import Path

from core.storage import StorageBackend, InMemoryStorageBackend, FileStorageBackend
from core.event_bus import EventBus, get_event_bus
from core.config import ConfigManager, get_default_config_dir
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
from core.screenshot_manager import ScreenshotManager
from core.logger import get_logger

logger = get_logger("container")


class ServiceContainer:
    """
    Central dependency injection container holding instances of all core services.
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        snippet_manager: SnippetManager,
        project_manager: ProjectManager,
        loot_manager: LootManager,
        clipboard_watcher: ClipboardWatcher,
        screenshot_manager: ScreenshotManager,
        storage: StorageBackend,
        event_bus: EventBus
    ):
        self.config_manager = config_manager
        self.snippet_manager = snippet_manager
        self.project_manager = project_manager
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher
        self.screenshot_manager = screenshot_manager
        self.storage = storage
        self.event_bus = event_bus

    @classmethod
    def create_production(
        cls,
        config_dir: Optional[Path] = None,
        language: Optional[str] = None
    ) -> "ServiceContainer":
        """
        Creates a production service container backed by filesystem persistence
        and default OS directories.
        """
        resolved_config_dir = Path(config_dir) if config_dir else get_default_config_dir()
        storage = FileStorageBackend(base_dir=resolved_config_dir)
        event_bus = get_event_bus()

        config_manager = ConfigManager(config_dir=resolved_config_dir, storage=storage)
        
        # Determine language
        active_lang = language or config_manager.get("language", "en")
        from core.i18n import set_locale
        set_locale(active_lang)

        snippet_manager = SnippetManager(language=active_lang)
        project_manager = ProjectManager(config_dir=resolved_config_dir)
        loot_manager = LootManager()
        clipboard_watcher = ClipboardWatcher()
        screenshot_manager = ScreenshotManager()

        return cls(
            config_manager=config_manager,
            snippet_manager=snippet_manager,
            project_manager=project_manager,
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            screenshot_manager=screenshot_manager,
            storage=storage,
            event_bus=event_bus
        )

    @classmethod
    def create_in_memory(
        cls,
        initial_config: Optional[Dict[str, Any]] = None,
        language: str = "en"
    ) -> "ServiceContainer":
        """
        Creates a pure in-memory service container with zero disk I/O.
        Ideal for unit testing, test fakes, and headless test runners.
        """
        init_data: Dict[str, Any] = {}
        if initial_config:
            init_data["config"] = dict(initial_config)

        storage = InMemoryStorageBackend(initial_data=init_data)
        event_bus = EventBus()

        config_manager = ConfigManager(storage=storage)
        from core.i18n import set_locale
        set_locale(language)

        snippet_manager = SnippetManager(language=language)
        project_manager = ProjectManager(config_dir=config_manager.config_dir)
        loot_manager = LootManager(storage=storage)
        clipboard_watcher = ClipboardWatcher(storage=storage)
        screenshot_manager = ScreenshotManager()

        return cls(
            config_manager=config_manager,
            snippet_manager=snippet_manager,
            project_manager=project_manager,
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            screenshot_manager=screenshot_manager,
            storage=storage,
            event_bus=event_bus
        )

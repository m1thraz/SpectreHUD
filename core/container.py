"""
Service Container & Dependency Injection Layer for SpectreHUD.

Centralizes lifecycle management, configuration, and dependency composition
for all core domain services, storage backends, and event buses.
"""

from typing import Optional, Dict, Any
from pathlib import Path
import tempfile

from core.storage import StorageBackend, InMemoryStorageBackend, FileStorageBackend
from core.event_bus import EventBus
from core.config import ConfigManager, get_default_config_dir
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.quick_note_manager import QuickNoteManager
from core.project import ProjectManager
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
        event_bus: EventBus,
        quick_note_manager: Optional[QuickNoteManager] = None,
    ):
        self.config_manager = config_manager
        self.snippet_manager = snippet_manager
        self.project_manager = project_manager
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher
        self.quick_note_manager = (
            quick_note_manager
            if quick_note_manager is not None
            else QuickNoteManager(event_bus=event_bus)
        )
        self.screenshot_manager = screenshot_manager
        self.storage = storage
        self.event_bus = event_bus

    @classmethod
    def from_services(
        cls,
        *,
        config_manager: ConfigManager,
        snippet_manager: SnippetManager,
        project_manager: ProjectManager,
        loot_manager: LootManager,
        clipboard_watcher: ClipboardWatcher,
        screenshot_manager: Optional[ScreenshotManager] = None,
        quick_note_manager: Optional[QuickNoteManager] = None,
        storage: Optional[StorageBackend] = None,
        event_bus: Optional[EventBus] = None,
    ) -> "ServiceContainer":
        """Compose a container from explicitly supplied service instances.

        This is primarily useful for tests and alternative composition roots
        that need precise service doubles without teaching UI widgets how to
        construct application dependencies.
        """
        actual_event_bus = event_bus or EventBus()
        return cls(
            config_manager=config_manager,
            snippet_manager=snippet_manager,
            project_manager=project_manager,
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            screenshot_manager=screenshot_manager or ScreenshotManager(),
            quick_note_manager=quick_note_manager,
            storage=storage or InMemoryStorageBackend(),
            event_bus=actual_event_bus,
        )

    @classmethod
    def create_production(
        cls, config_dir: Optional[Path] = None, language: Optional[str] = None
    ) -> "ServiceContainer":
        """
        Creates a production service container backed by filesystem persistence
        and default OS directories.
        """
        resolved_config_dir = Path(config_dir) if config_dir else get_default_config_dir()
        from core.logger import configure_file_logging

        configure_file_logging(config_dir=resolved_config_dir)
        storage = FileStorageBackend(base_dir=resolved_config_dir)
        event_bus = EventBus()

        config_manager = ConfigManager(config_dir=resolved_config_dir, storage=storage)

        # Determine language & time format
        active_lang = language or config_manager.get("language", "en")
        time_format = config_manager.get("time_format", "24h")
        from core.i18n import set_locale

        set_locale(active_lang)

        snippet_manager = SnippetManager(language=active_lang)
        workspace_setting = config_manager.get("workspace_dir")
        base_projects_dir = Path(workspace_setting) if workspace_setting else None
        project_manager = ProjectManager(
            base_dir=base_projects_dir, config_dir=resolved_config_dir, event_bus=event_bus
        )

        # Single Source of Truth: Loot, Clipboard & Quick Notes operate in session memory and are persisted exclusively to project_state.json
        session_storage = InMemoryStorageBackend()
        loot_manager = LootManager(
            storage=session_storage, event_bus=event_bus, time_format=time_format
        )
        clipboard_watcher = ClipboardWatcher(
            storage=session_storage, event_bus=event_bus, time_format=time_format
        )
        quick_note_manager = QuickNoteManager(
            storage=session_storage, event_bus=event_bus, time_format=time_format
        )
        screenshot_manager = ScreenshotManager()

        return cls(
            config_manager=config_manager,
            snippet_manager=snippet_manager,
            project_manager=project_manager,
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            quick_note_manager=quick_note_manager,
            screenshot_manager=screenshot_manager,
            storage=storage,
            event_bus=event_bus,
        )

    @classmethod
    def create_isolated_test_container(
        cls,
        initial_config: Optional[Dict[str, Any]] = None,
        language: str = "en",
        base_dir: Optional[Path] = None,
        config_dir: Optional[Path] = None,
        storage: Optional[StorageBackend] = None,
        event_bus: Optional[EventBus] = None,
    ) -> "ServiceContainer":
        """
        Creates a test service container with isolated temporary directories and in-memory storage.

        Note: Uses ``tempfile.mkdtemp()`` for filesystem-dependent managers
        (``ProjectManager``, ``ReportFileManager``). This is **not zero-disk I/O** — it is
        designed for test isolation, not in-process memory-only execution.
        Ideal for unit testing, headless test runners, and CI environments.
        """
        init_data: Dict[str, Any] = {}
        if initial_config:
            init_data["config"] = dict(initial_config)

        actual_storage = storage or InMemoryStorageBackend(initial_data=init_data)
        actual_event_bus = event_bus or EventBus()

        temp_dir = tempfile.mkdtemp(prefix="spectrehud_test_")
        temp_cfg_dir = config_dir or (Path(temp_dir) / "config")
        temp_base_dir = base_dir or (Path(temp_dir) / "projects")

        config_manager = ConfigManager(config_dir=temp_cfg_dir, storage=actual_storage)
        time_format = config_manager.get("time_format", "24h")
        from core.i18n import set_locale

        set_locale(language)

        snippet_manager = SnippetManager(language=language)
        project_manager = ProjectManager(
            base_dir=temp_base_dir, config_dir=temp_cfg_dir, event_bus=actual_event_bus
        )
        loot_manager = LootManager(
            storage=actual_storage, event_bus=actual_event_bus, time_format=time_format
        )
        clipboard_watcher = ClipboardWatcher(
            storage=actual_storage, event_bus=actual_event_bus, time_format=time_format
        )
        quick_note_manager = QuickNoteManager(
            storage=actual_storage, event_bus=actual_event_bus, time_format=time_format
        )
        screenshot_manager = ScreenshotManager()

        return cls(
            config_manager=config_manager,
            snippet_manager=snippet_manager,
            project_manager=project_manager,
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            quick_note_manager=quick_note_manager,
            screenshot_manager=screenshot_manager,
            storage=actual_storage,
            event_bus=actual_event_bus,
        )

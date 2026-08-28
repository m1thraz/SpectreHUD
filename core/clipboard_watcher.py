import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.config import get_default_config_dir
from core.logger import get_logger
from core.storage import StorageBackend, InMemoryStorageBackend, FileStorageBackend, PersistenceError

logger = get_logger("clipboard")

MAX_CLIPBOARD_TEXT_SIZE = 64 * 1024  # 64 KB

class ClipboardWatcher(QObject):
    """
    Monitors system clipboard in background, logs command copies & outputs,
    filters duplicates, and persists history.
    """
    entry_added = pyqtSignal(dict)
    logging_state_changed = pyqtSignal(bool)

    def __init__(
        self,
        storage_file: Optional[Path] = None,
        storage: Optional[StorageBackend] = None,
        event_bus: Optional[Any] = None,
        time_format: str = "24h",
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        if storage is not None:
            self.storage = storage
            self.storage_file = getattr(storage, "single_file_path", None)
        elif storage_file is not None:
            self.storage_file = Path(storage_file)
            self.storage = FileStorageBackend(single_file_path=self.storage_file)
        else:
            self.storage_file = None
            self.storage = InMemoryStorageBackend()
        
        self.event_bus = event_bus
        self.time_format = time_format if time_format in ("24h", "12h") else "24h"
        self.history: List[Dict[str, Any]] = []
        self._last_copied_text: Optional[str] = None
        self._is_paused = True  # Default to PAUSED for user privacy (opt-in)
        self._current_target_provider = None
        
        self.load_history()

    def set_time_format(self, time_format: str) -> None:
        """Sets the active timestamp formatting scheme ('24h' or '12h')."""
        self.time_format = time_format if time_format in ("24h", "12h") else "24h"

    def set_target_provider(self, provider_func) -> None:
        """Sets a callable that returns the active target IP."""
        self._current_target_provider = provider_func

    def start_listening(self) -> None:
        """Connects to QApplication's clipboard dataChanged signal."""
        app = QApplication.instance()
        if app:
            clipboard = app.clipboard()
            clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self) -> None:
        if self._is_paused:
            return

        app = QApplication.instance()
        if not app:
            return

        try:
            text = app.clipboard().text()
            if not text:
                return

            target_ip = ""
            if self._current_target_provider:
                try:
                    target_ip = self._current_target_provider() or ""
                except (TypeError, ValueError, AttributeError) as e:
                    logger.debug(f"Error resolving target_ip in clipboard provider: {e}")

            # Clipboard callbacks must not perform filesystem I/O.  The
            # AppController persists the in-memory session after entry_added.
            self.add_entry(text, target_ip=target_ip, persist=False)
        except (RuntimeError, OSError) as e:
            logger.error(f"Error reading clipboard content: {e}", exc_info=True)

    def add_entry(
        self,
        text: str,
        target_ip: str = "",
        *,
        persist: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Adds a sanitized entry, optionally persisting standalone history storage.

        Clipboard callbacks pass ``persist=False`` so their thread only updates the
        in-memory session.  The UI-side project-session save is triggered by
        ``entry_added``.  Direct, standalone callers retain the legacy persistence
        behaviour by default.
        """
        if not text or not text.strip():
            return None

        # Ignore huge binary or dump pastes
        if len(text) > MAX_CLIPBOARD_TEXT_SIZE:
            logger.debug(f"Ignored clipboard item larger than {MAX_CLIPBOARD_TEXT_SIZE} bytes.")
            return None

        # Deduplicate consecutive identical copies
        clean_text = text.strip()
        if self._last_copied_text == clean_text:
            return None

        lines_count = clean_text.count("\n") + 1
        char_count = len(clean_text)

        # Categorize entry (Command vs Output/Snippet)
        is_multiline = lines_count > 2 or char_count > 120

        from core.validators import format_timestamp
        entry = {
            "id": f"clip_{uuid.uuid4().hex[:8]}",
            "text": clean_text,
            "target_ip": (target_ip or "").strip(),
            "timestamp": format_timestamp(time_format=self.time_format),
            "lines_count": lines_count,
            "char_count": char_count,
            "is_multiline": is_multiline
        }

        new_history = [entry, *self.history]
        if len(new_history) > 500:
            new_history = new_history[:500]

        # Standalone callers may opt into the legacy storage backend.  The live
        # clipboard callback deliberately skips this I/O path.
        if persist and not self.storage.save_json("clipboard", new_history):
            raise PersistenceError("Could not persist clipboard entry to storage.")

        self._last_copied_text = clean_text
        self.history = new_history

        # Qt automatically queues this signal for QObject receivers living in a
        # different thread (the AppController lives on the GUI thread).  Avoid
        # QMetaObject.invokeMethod here: arbitrary Python dicts are not Qt meta
        # object arguments and would otherwise fall back to a direct UI callback.
        self.entry_added.emit(entry)

        if self.event_bus:
            from core.event_bus import EventType
            self.event_bus.publish(EventType.HISTORY_UPDATED, {"history": self.get_all_history()})
        return entry

    def load_history(self) -> None:
        """Loads and semantically validates clipboard history from storage backend."""
        from core.validators import validate_clipboard_list
        raw_data = self.storage.load_json("clipboard")
        if raw_data is not None:
            self.history = validate_clipboard_list(raw_data)
        else:
            self.history = []

    def replace_history(self, history: List[Dict[str, Any]]) -> None:
        """
        Replaces in-memory clipboard history from session loading without triggering disk writes.
        Validates in RAM and emits EventType.HISTORY_UPDATED.
        """
        from core.validators import validate_clipboard_list
        self.history = validate_clipboard_list(history)
        self._last_copied_text = self.history[0]["text"] if self.history else None
        if self.event_bus:
            from core.event_bus import EventType
            self.event_bus.publish(EventType.HISTORY_UPDATED, {"history": self.get_all_history()})

    def set_history(self, history: List[Dict[str, Any]]) -> None:
        """Replaces history with a validated list (e.g. on project switch)."""
        from core.validators import validate_clipboard_list
        validated = validate_clipboard_list(history)
        if not self.storage.save_json("clipboard", validated):
            raise PersistenceError("Could not persist set_history to storage.")
        self.history = validated
        self._last_copied_text = self.history[0]["text"] if self.history else None
        if self.event_bus:
            from core.event_bus import EventType
            self.event_bus.publish(EventType.HISTORY_UPDATED, {"history": self.get_all_history()})

    def get_all_history(self) -> List[Dict[str, Any]]:
        """Returns defensive copies of all history items."""
        return [dict(e) for e in self.history]

    def save_history(self) -> None:
        """Persists history using configured storage backend."""
        if not self.storage.save_json("clipboard", self.history):
            raise PersistenceError("Could not persist clipboard history to storage.")

    def delete_entry(self, entry_id: str) -> bool:
        """Removes an entry by ID."""
        new_history = [e for e in self.history if e.get("id") != entry_id]
        if len(new_history) == len(self.history):
            return False
        if not self.storage.save_json("clipboard", new_history):
            raise PersistenceError(f"Could not persist deletion of clipboard entry {entry_id}.")
        self.history = new_history
        if self.event_bus:
            from core.event_bus import EventType
            self.event_bus.publish(EventType.HISTORY_UPDATED, {"history": self.get_all_history()})
        return True

    def clear_history(self) -> int:
        """Clears all clipboard history."""
        count = len(self.history)
        if not self.storage.save_json("clipboard", []):
            raise PersistenceError("Could not persist cleared clipboard history.")
        self.history = []
        self._last_copied_text = None
        if self.event_bus:
            from core.event_bus import EventType
            self.event_bus.publish(EventType.HISTORY_UPDATED, {"history": self.get_all_history()})
        return count

    def get_history(self, search_query: str = "", target_ip: Optional[str] = None, filter_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Filters history by search query, target IP, or command/output type."""
        results = self.history

        if target_ip and target_ip != "all":
            results = [e for e in results if e.get("target_ip") == target_ip or not e.get("target_ip")]

        if filter_type == "commands":
            results = [e for e in results if not e.get("is_multiline", False)]
        elif filter_type == "outputs":
            results = [e for e in results if e.get("is_multiline", False)]

        if not search_query or not search_query.strip():
            return [dict(e) for e in results]

        q = search_query.strip().lower()
        filtered = []
        for e in results:
            text = e.get("text", "").lower()
            target = e.get("target_ip", "").lower()
            if q in text or q in target:
                filtered.append(e)

        return [dict(e) for e in filtered]

    def toggle_pause(self) -> bool:
        """Toggles logging pause state and emits signal."""
        self._is_paused = not self._is_paused
        self.logging_state_changed.emit(not self._is_paused)
        logger.info(f"Clipboard logging state toggled: {'PAUSED' if self._is_paused else 'ACTIVE'}")
        return self._is_paused

    def set_paused(self, paused: bool) -> None:
        """Explicitly sets logging pause state."""
        if self._is_paused != paused:
            self._is_paused = paused
            self.logging_state_changed.emit(not self._is_paused)
            logger.info(f"Clipboard logging state set: {'PAUSED' if self._is_paused else 'ACTIVE'}")

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def export_report_markdown(self, output_path: Path, target_ip: Optional[str] = None, loot_manager = None) -> str:
        """DEPRECATED: Use core.report_builder.ReportBuilder instead.
        
        Delegates directly to ReportBuilder for unified reporting.
        """
        from core.report_builder import ReportBuilder
        builder = ReportBuilder(loot_manager=loot_manager, clipboard_watcher=self)
        return builder.export(output_path, target_ip=target_ip)

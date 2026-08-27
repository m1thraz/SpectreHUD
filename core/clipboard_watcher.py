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
        self.history: List[Dict[str, Any]] = []
        self._last_copied_text: Optional[str] = None
        self._is_paused = True  # Default to PAUSED for user privacy (opt-in)
        self._current_target_provider = None
        
        self.load_history()

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

            self.add_entry(text, target_ip=target_ip)
        except (RuntimeError, OSError) as e:
            logger.error(f"Error reading clipboard content: {e}", exc_info=True)

    def add_entry(self, text: str, target_ip: str = "") -> Optional[Dict[str, Any]]:
        """Adds a new sanitized entry if not a consecutive duplicate."""
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

        self._last_copied_text = clean_text

        lines_count = clean_text.count("\n") + 1
        char_count = len(clean_text)

        # Categorize entry (Command vs Output/Snippet)
        is_multiline = lines_count > 2 or char_count > 120

        entry = {
            "id": f"clip_{uuid.uuid4().hex[:8]}",
            "text": clean_text,
            "target_ip": target_ip.strip(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "lines_count": lines_count,
            "char_count": char_count,
            "is_multiline": is_multiline
        }

        new_history = [entry, *self.history]
        if len(new_history) > 500:
            new_history = new_history[:500]

        if not self.storage.save_json("clipboard", new_history):
            raise PersistenceError("Could not persist clipboard entry to storage.")
        
        self.history = new_history
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
            return results

        q = search_query.strip().lower()
        filtered = []
        for e in results:
            text = e.get("text", "").lower()
            target = e.get("target_ip", "").lower()
            if q in text or q in target:
                filtered.append(e)

        return filtered

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

"""Pure clipboard-history state, filtering, and persistence."""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.storage import (
    FileStorageBackend,
    InMemoryStorageBackend,
    PersistenceError,
    StorageBackend,
)
from core.validators import format_timestamp, validate_clipboard_list

logger = get_logger("clipboard")

MAX_CLIPBOARD_TEXT_SIZE = 64 * 1024
MAX_HISTORY_ENTRIES = 500


class ClipboardHistory:
    """Owns clipboard history without depending on Qt or a system clipboard."""

    def __init__(
        self,
        storage_file: Optional[Path] = None,
        storage: Optional[StorageBackend] = None,
        event_bus: Optional[Any] = None,
        time_format: str = "24h",
    ) -> None:
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
        self.load_history()

    def set_time_format(self, time_format: str) -> None:
        """Set the timestamp formatting scheme to 24-hour or 12-hour format."""
        self.time_format = time_format if time_format in ("24h", "12h") else "24h"

    def _publish_updated(self, action: str, entry: Optional[Dict[str, Any]] = None) -> None:
        if self.event_bus:
            from core.event_bus import EventType

            self.event_bus.publish(
                EventType.HISTORY_UPDATED,
                {
                    "action": action,
                    "entry": dict(entry) if entry is not None else None,
                    "history": self.get_all_history(),
                },
            )

    def add_entry(
        self, text: str, target_ip: str = "", *, persist: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Add a sanitized history entry if it is valid and not a duplicate."""
        if not text or not text.strip():
            return None
        if len(text) > MAX_CLIPBOARD_TEXT_SIZE:
            logger.debug(
                "Ignored clipboard item larger than %s bytes.", MAX_CLIPBOARD_TEXT_SIZE
            )
            return None

        clean_text = text.strip()
        if self._last_copied_text == clean_text:
            return None

        lines_count = clean_text.count("\n") + 1
        char_count = len(clean_text)
        entry = {
            "id": f"clip_{uuid.uuid4().hex[:8]}",
            "text": clean_text,
            "target_ip": (target_ip or "").strip(),
            "timestamp": format_timestamp(time_format=self.time_format),
            "lines_count": lines_count,
            "char_count": char_count,
            "is_multiline": lines_count > 2 or char_count > 120,
        }
        new_history = [entry, *self.history][:MAX_HISTORY_ENTRIES]

        if persist and not self.storage.save_json("clipboard", new_history):
            raise PersistenceError("Could not persist clipboard entry to storage.")

        self._last_copied_text = clean_text
        self.history = new_history
        self._publish_updated("add", entry)
        return dict(entry)

    def load_history(self) -> None:
        """Load and semantically validate clipboard history from storage."""
        raw_data = self.storage.load_json("clipboard")
        self.history = validate_clipboard_list(raw_data) if raw_data is not None else []
        self._last_copied_text = self.history[0]["text"] if self.history else None

    def replace_history(self, history: List[Dict[str, Any]]) -> None:
        """Replace in-memory history without writing to storage."""
        self.history = validate_clipboard_list(history)
        self._last_copied_text = self.history[0]["text"] if self.history else None
        self._publish_updated("replace")

    def replace_history_and_persist(self, history: List[Dict[str, Any]]) -> None:
        """Replace history and persist the validated result atomically."""
        validated = validate_clipboard_list(history)
        if not self.storage.save_json("clipboard", validated):
            raise PersistenceError("Could not persist replacement clipboard history to storage.")
        self.history = validated
        self._last_copied_text = self.history[0]["text"] if self.history else None
        self._publish_updated("replace")

    def get_all_history(self) -> List[Dict[str, Any]]:
        """Return defensive copies of all history entries."""
        return [dict(entry) for entry in self.history]

    def save_history(self) -> None:
        """Persist the current history."""
        if not self.storage.save_json("clipboard", self.history):
            raise PersistenceError("Could not persist clipboard history to storage.")

    def delete_entry(self, entry_id: str) -> bool:
        """Remove an entry by ID."""
        deleted_entry = next(
            (entry for entry in self.history if entry.get("id") == entry_id), None
        )
        new_history = [entry for entry in self.history if entry.get("id") != entry_id]
        if len(new_history) == len(self.history):
            return False
        if not self.storage.save_json("clipboard", new_history):
            raise PersistenceError(f"Could not persist deletion of clipboard entry {entry_id}.")
        self.history = new_history
        self._publish_updated("delete", deleted_entry)
        return True

    def update_entry(
        self,
        entry_id: str,
        text: str,
        target_ip: Optional[str] = None,
        *,
        persist: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Update text and optionally the target IP of one entry."""
        clean_text = str(text or "").strip()
        if not clean_text:
            return None

        index = next(
            (i for i, entry in enumerate(self.history) if entry.get("id") == entry_id),
            -1,
        )
        if index == -1:
            return None

        current = dict(self.history[index])
        lines_count = clean_text.count("\n") + 1
        char_count = len(clean_text)
        current.update(
            {
                "text": clean_text,
                "lines_count": lines_count,
                "char_count": char_count,
                "is_multiline": lines_count > 2 or char_count > 120,
            }
        )
        if target_ip is not None:
            current["target_ip"] = str(target_ip).strip()

        new_history = list(self.history)
        new_history[index] = current
        if persist and not self.storage.save_json("clipboard", new_history):
            raise PersistenceError(f"Could not persist update of clipboard entry {entry_id}.")

        self.history = new_history
        self._publish_updated("update", current)
        return dict(current)

    def clear_history(self) -> int:
        """Clear all clipboard history and return the removed entry count."""
        count = len(self.history)
        if not self.storage.save_json("clipboard", []):
            raise PersistenceError("Could not persist cleared clipboard history.")
        self.history = []
        self._last_copied_text = None
        self._publish_updated("clear")
        return count

    def get_history(
        self,
        search_query: Optional[str] = "",
        target_ip: Optional[str] = None,
        filter_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filter history by query, target IP, or command/output type."""
        results = self.history
        if target_ip and target_ip != "all":
            results = [
                entry
                for entry in results
                if entry.get("target_ip") == target_ip or not entry.get("target_ip")
            ]
        if filter_type == "commands":
            results = [entry for entry in results if not entry.get("is_multiline", False)]
        elif filter_type == "outputs":
            results = [entry for entry in results if entry.get("is_multiline", False)]

        query = (search_query or "").strip().lower()
        if not query:
            return [dict(entry) for entry in results]
        return [
            dict(entry)
            for entry in results
            if query in entry.get("text", "").lower()
            or query in entry.get("target_ip", "").lower()
        ]

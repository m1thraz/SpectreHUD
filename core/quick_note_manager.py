"""
Quick Note Manager for SpectreHUD.

Provides lightweight, immediate note capture independent of clipboard REC state,
persisted to project storage under 'quick_notes'.
"""

import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal

from core.logger import get_logger
from core.storage import (
    StorageBackend,
    InMemoryStorageBackend,
    FileStorageBackend,
    PersistenceError,
)
from core.loot_manager import VALID_CATEGORY_IDS
from core.validators import (
    format_timestamp,
    validate_quick_notes_list,
    MAX_CLIPBOARD_TEXT_LENGTH,
)

logger = get_logger("quick_notes")


class QuickNoteManager(QObject):
    """
    Manages lightweight quick thought notes in a dedicated inbox.
    Independent of clipboard recording, persisted per project.
    """

    entry_added = pyqtSignal(dict)

    def __init__(
        self,
        storage_file: Optional[Path] = None,
        storage: Optional[StorageBackend] = None,
        event_bus: Optional[Any] = None,
        time_format: str = "24h",
        parent: Optional[QObject] = None,
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
        self.notes: List[Dict[str, Any]] = []

        self.load_entries()

    def set_time_format(self, time_format: str) -> None:
        """Sets the active timestamp formatting scheme ('24h' or '12h')."""
        self.time_format = time_format if time_format in ("24h", "12h") else "24h"

    def _publish_updated(self, action: str, entry: Optional[Dict[str, Any]] = None) -> None:
        """Publishes the canonical event for a quick note mutation."""
        if self.event_bus:
            from core.event_bus import EventType

            self.event_bus.publish(
                EventType.QUICK_NOTES_UPDATED,
                {
                    "action": action,
                    "entry": dict(entry) if entry is not None else None,
                    "notes": self.get_all_entries(),
                },
            )

    def add_entry(
        self,
        text: str,
        category: str = "misc",
        target_ip: Optional[str] = None,
        *,
        persist: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Adds a new quick note entry and optionally persists it."""
        clean_text = str(text or "").strip()
        if not clean_text:
            return None

        if len(clean_text) > MAX_CLIPBOARD_TEXT_LENGTH:
            clean_text = clean_text[:MAX_CLIPBOARD_TEXT_LENGTH]

        cat = str(category or "misc").strip().lower()
        if cat not in VALID_CATEGORY_IDS:
            cat = "misc"

        entry = {
            "id": f"note_{uuid.uuid4().hex[:8]}",
            "text": clean_text,
            "category": cat,
            "target_ip": str(target_ip or "").strip(),
            "timestamp": format_timestamp(time_format=self.time_format),
        }

        new_notes = [entry, *self.notes]
        if len(new_notes) > 500:
            new_notes = new_notes[:500]

        if persist and not self.storage.save_json("quick_notes", new_notes):
            raise PersistenceError("Could not persist quick note entry to storage.")

        self.notes = new_notes
        self.entry_added.emit(entry)
        self._publish_updated("add", entry)
        return entry

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Returns a copy of all current quick notes."""
        return [dict(n) for n in self.notes]

    def get_entries(
        self,
        category: Optional[str] = None,
        target_ip: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns filtered quick notes."""
        results = self.notes
        if category and category != "all":
            results = [n for n in results if n.get("category") == category]
        if target_ip:
            tip = target_ip.strip()
            results = [n for n in results if n.get("target_ip") == tip]
        if search_query and search_query.strip():
            sq = search_query.strip().lower()
            results = [
                n
                for n in results
                if sq in n.get("text", "").lower() or sq in n.get("category", "").lower()
            ]
        return [dict(n) for n in results]

    def delete_entry(self, entry_id: str, *, persist: bool = True) -> bool:
        """Deletes a quick note by id."""
        initial_len = len(self.notes)
        new_notes = [n for n in self.notes if n.get("id") != entry_id]
        if len(new_notes) == initial_len:
            return False

        if persist and not self.storage.save_json("quick_notes", new_notes):
            raise PersistenceError("Could not persist quick note deletion to storage.")

        self.notes = new_notes
        self._publish_updated("delete", {"id": entry_id})
        return True

    def clear_entries(self, *, persist: bool = True) -> None:
        """Clears all quick notes."""
        if persist and not self.storage.save_json("quick_notes", []):
            raise PersistenceError("Could not clear quick notes in storage.")
        self.notes = []
        self._publish_updated("clear")

    def load_entries(self) -> None:
        """Loads and validates quick notes from storage backend."""
        raw_data = self.storage.load_json("quick_notes")
        if raw_data is not None:
            self.notes = validate_quick_notes_list(raw_data)
        else:
            self.notes = []

    def replace_entries(self, entries: List[Dict[str, Any]]) -> None:
        """Replaces in-memory notes during session switching without disk I/O."""
        self.notes = validate_quick_notes_list(entries)
        self._publish_updated("replace")

    def replace_entries_and_persist(self, entries: List[Dict[str, Any]]) -> None:
        """Replaces notes in memory and immediately persists to storage."""
        validated = validate_quick_notes_list(entries)
        if not self.storage.save_json("quick_notes", validated):
            raise PersistenceError("Could not persist quick notes list to storage.")
        self.notes = validated
        self._publish_updated("replace")

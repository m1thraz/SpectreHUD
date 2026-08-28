import json
import uuid
import warnings
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.config import get_default_config_dir
from core.logger import get_logger
from core.storage import StorageBackend, InMemoryStorageBackend, FileStorageBackend, PersistenceError

logger = get_logger("loot")

LOOT_TYPES = [
    {"id": "credentials", "name": "Credentials", "icon": "", "badge_class": "BadgeCreds"},
    {"id": "hash", "name": "Hashes", "icon": "", "badge_class": "BadgeHash"},
    {"id": "screenshot", "name": "Screenshots", "icon": "", "badge_class": "BadgeScreenshot"},
    {"id": "directory", "name": "Directories", "icon": "", "badge_class": "BadgeDir"},
    {"id": "flag", "name": "Flags", "icon": "", "badge_class": "BadgeFlag"},
    {"id": "note", "name": "Notes", "icon": "", "badge_class": "BadgeNote"}
]

CATEGORIES = [
    {"id": "recon", "name": "1. Reconnaissance & Enumeration", "order": 1, "icon": ""},
    {"id": "access", "name": "2. Initial Access & Exploitation", "order": 2, "icon": ""},
    {"id": "privesc", "name": "3. Privilege Escalation", "order": 3, "icon": ""},
    {"id": "postex", "name": "4. Post-Exploitation & Lateral Movement", "order": 4, "icon": ""},
    {"id": "scripts", "name": "5. Custom Scripts & PoCs", "order": 5, "icon": ""},
    {"id": "misc", "name": "6. Miscellaneous", "order": 6, "icon": ""}
]

VALID_CATEGORY_IDS = {c["id"] for c in CATEGORIES}

TYPE_ALIASES = {
    "cred": "credentials",
    "credentials": "credentials",
    "credential": "credentials",
    "dir": "directory",
    "directory": "directory",
    "directories": "directory",
    "notes": "note",
    "note": "note",
    "screenshots": "screenshot",
    "screenshot": "screenshot",
    "flags": "flag",
    "flag": "flag",
    "hashes": "hash",
    "hash": "hash"
}

class LootManager:
    """Manages session loot, credentials, hashes, flags and notes with persistence, categories and export."""

    def __init__(
        self,
        storage_file: Optional[Path] = None,
        storage: Optional[StorageBackend] = None,
        event_bus: Optional[Any] = None,
        time_format: str = "24h"
    ):
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
        self.entries: List[Dict[str, Any]] = []
        self.load_entries()

    def set_time_format(self, time_format: str) -> None:
        """Sets the active timestamp formatting scheme ('24h' or '12h')."""
        self.time_format = time_format if time_format in ("24h", "12h") else "24h"

    def _migrate_entries(self) -> bool:
        """Ensures all entries have a valid category and severity. Returns True if any entry was migrated."""
        from core.validators import VALID_SEVERITIES
        migrated = False
        for entry in self.entries:
            cat = entry.get("category")
            if not cat or cat not in VALID_CATEGORY_IDS:
                entry["category"] = "misc"
                migrated = True
            
            # Normalize severity if missing or invalid
            sev = entry.get("severity")
            norm_sev = str(sev).lower().strip() if sev else "info"
            if norm_sev not in VALID_SEVERITIES:
                norm_sev = "info"
            if norm_sev != sev:
                entry["severity"] = norm_sev
                migrated = True

            # Also normalize type if needed
            entry_type = entry.get("type")
            norm_type = TYPE_ALIASES.get(str(entry_type).lower(), entry_type)
            if norm_type != entry_type:
                entry["type"] = norm_type
                migrated = True
        return migrated

    def load_entries(self) -> None:
        """Loads and semantically validates loot entries from storage backend."""
        from core.validators import validate_loot_list
        raw_data = self.storage.load_json("loot")
        if raw_data is not None:
            self.entries = validate_loot_list(raw_data)
        else:
            self.entries = []

        # Automatic migration of legacy entries lacking category or with invalid category
        if self._migrate_entries():
            logger.info("Migrated legacy loot entries to include category/severity and persisted.")
            self.save_entries()

    def replace_entries(self, entries: List[Dict[str, Any]]) -> None:
        """
        Replaces in-memory loot entries from session loading without triggering disk writes.
        Validates, migrates in RAM, and emits EventType.LOOT_UPDATED.
        """
        from core.validators import validate_loot_list
        self.entries = validate_loot_list(entries)
        self._migrate_entries()
        if self.event_bus:
            from core.event_bus import EventType
            self.event_bus.publish(EventType.LOOT_UPDATED, {"entries": self.get_all_entries()})

    def replace_entries_and_persist(self, entries: List[Dict[str, Any]]) -> None:
        """Replaces entries in memory and immediately persists the validated result."""
        from core.validators import validate_loot_list
        self.entries = validate_loot_list(entries)
        if self._migrate_entries():
            logger.info("Migrated replacement loot entries and persisted them to disk.")
        self.save_entries()
        if self.event_bus:
            from core.event_bus import EventType
            self.event_bus.publish(EventType.LOOT_UPDATED, {"entries": self.get_all_entries()})

    def set_entries(self, entries: List[Dict[str, Any]]) -> None:
        """Deprecated compatibility alias for :meth:`replace_entries_and_persist`."""
        warnings.warn(
            "set_entries() is deprecated; use replace_entries() for in-memory replacement "
            "or replace_entries_and_persist() to write immediately.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.replace_entries_and_persist(entries)

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Returns defensive copies of all entries."""
        return [dict(e) for e in self.entries]

    def save_entries(self) -> None:
        """Persists loot entries using configured storage backend."""
        if not self.storage.save_json("loot", self.entries):
            raise PersistenceError("Could not persist loot entries to storage.")

    def add_entry(
        self, 
        entry_type: str, 
        title: str, 
        content: str, 
        target_ip: str = "", 
        category: str = "misc",
        severity: str = "info",
        **kwargs
    ) -> Dict[str, Any]:
        """Creates and stores a new loot entry with category and severity classification."""
        from core.validators import VALID_SEVERITIES
        normalized_type = TYPE_ALIASES.get(entry_type.lower(), entry_type) if entry_type else "note"
        cat_id = category if category in VALID_CATEGORY_IDS else "misc"
        sev_clean = str(severity).lower().strip() if severity else "info"
        sev_id = sev_clean if sev_clean in VALID_SEVERITIES else "info"
        
        from core.validators import format_timestamp
        time_format = kwargs.get("time_format", self.time_format)
        entry = {
            "id": f"loot_{uuid.uuid4().hex[:8]}",
            "type": normalized_type,
            "category": cat_id,
            "severity": sev_id,
            "title": title.strip() or "Unbenannter Eintrag",
            "content": content.strip(),
            "target_ip": target_ip.strip(),
            "timestamp": format_timestamp(time_format=time_format)
        }
        new_entries = [entry, *self.entries]
        if not self.storage.save_json("loot", new_entries):
            raise PersistenceError("Could not persist new loot entry to storage.")
        self.entries = new_entries
        if self.event_bus:
            from core.event_bus import EventType
            self.event_bus.publish(EventType.LOOT_UPDATED, {"entries": self.get_all_entries()})
        return entry

    def update_entry(self, entry_id: str, **fields) -> Optional[Dict[str, Any]]:
        """Updates fields of an existing entry by ID and persists changes."""
        from core.validators import VALID_SEVERITIES
        new_entries = [dict(e) for e in self.entries]
        updated_entry = None
        for entry in new_entries:
            if entry.get("id") == entry_id:
                if "category" in fields:
                    cat = fields["category"]
                    entry["category"] = cat if cat in VALID_CATEGORY_IDS else "misc"
                if "severity" in fields:
                    raw_sev = str(fields["severity"]).lower().strip() if fields["severity"] else "info"
                    entry["severity"] = raw_sev if raw_sev in VALID_SEVERITIES else "info"
                if "type" in fields:
                    raw_type = fields["type"]
                    entry["type"] = TYPE_ALIASES.get(raw_type.lower(), raw_type) if raw_type else "note"
                if "title" in fields:
                    entry["title"] = fields["title"].strip() or "Unbenannter Eintrag"
                if "content" in fields:
                    entry["content"] = fields["content"].strip()
                if "target_ip" in fields:
                    entry["target_ip"] = fields["target_ip"].strip()
                updated_entry = entry
                break
        
        if updated_entry is not None:
            if not self.storage.save_json("loot", new_entries):
                raise PersistenceError(f"Could not persist update for loot entry {entry_id}.")
            self.entries = new_entries
            if self.event_bus:
                from core.event_bus import EventType
                self.event_bus.publish(EventType.LOOT_UPDATED, {"entries": self.get_all_entries()})
        return updated_entry

    def delete_entry(self, entry_id: str) -> bool:
        """Deletes an entry by ID."""
        new_entries = [e for e in self.entries if e.get("id") != entry_id]
        if len(new_entries) == len(self.entries):
            return False
        if not self.storage.save_json("loot", new_entries):
            raise PersistenceError(f"Could not persist deletion for loot entry {entry_id}.")
        self.entries = new_entries
        if self.event_bus:
            from core.event_bus import EventType
            self.event_bus.publish(EventType.LOOT_UPDATED, {"entries": self.get_all_entries()})
        return True

    def clear_session(self, target_ip: Optional[str] = None) -> int:
        """Clears all entries, or only those matching a specific target IP."""
        if target_ip:
            new_entries = [e for e in self.entries if e.get("target_ip") != target_ip]
            deleted_count = len(self.entries) - len(new_entries)
        else:
            deleted_count = len(self.entries)
            new_entries = []
        if not self.storage.save_json("loot", new_entries):
            raise PersistenceError("Could not persist cleared session loot to storage.")
        self.entries = new_entries
        if self.event_bus:
            from core.event_bus import EventType
            self.event_bus.publish(EventType.LOOT_UPDATED, {"entries": self.get_all_entries()})
        return deleted_count

    def get_entries(
        self, 
        target_ip: Optional[str] = None, 
        entry_type: Optional[str] = None, 
        category: Optional[str] = None,
        search_query: str = ""
    ) -> List[Dict[str, Any]]:
        """Filters loot entries by target IP, type, category and search term."""
        results = self.entries

        if target_ip and target_ip != "all":
            results = [e for e in results if e.get("target_ip") == target_ip or not e.get("target_ip")]

        if entry_type and entry_type != "all":
            norm_type = TYPE_ALIASES.get(entry_type.lower(), entry_type)
            results = [e for e in results if TYPE_ALIASES.get(e.get("type", "").lower(), e.get("type")) == norm_type]

        if category and category != "all":
            results = [e for e in results if e.get("category") == category]

        if not search_query or not search_query.strip():
            return [dict(e) for e in results]

        q = search_query.strip().lower()
        filtered = []
        for e in results:
            title = e.get("title", "").lower()
            content = e.get("content", "").lower()
            target = e.get("target_ip", "").lower()
            cat = e.get("category", "").lower()
            if q in title or q in content or q in target or q in cat:
                filtered.append(e)

        return [dict(e) for e in filtered]

    def get_type_counts(self, target_ip: Optional[str] = None) -> Dict[str, int]:
        """Returns count of entries grouped by loot type."""
        entries = self.get_entries(target_ip=target_ip)
        counts = {"all": len(entries)}
        for t in LOOT_TYPES:
            counts[t["id"]] = sum(1 for e in entries if e.get("type") == t["id"])
        return counts

    def get_category_counts(self, target_ip: Optional[str] = None) -> Dict[str, int]:
        """Returns count of entries grouped by category."""
        entries = self.get_entries(target_ip=target_ip)
        counts = {"all": len(entries)}
        for c in CATEGORIES:
            counts[c["id"]] = sum(1 for e in entries if e.get("category") == c["id"])
        return counts

    def export_loot(self, output_path: Path, target_ip: Optional[str] = None) -> str:
        """DEPRECATED: Use core.report_builder.ReportBuilder instead.
        
        Delegates to ReportBuilder for unified reporting.
        """
        from core.report_builder import ReportBuilder
        builder = ReportBuilder(loot_manager=self)
        return builder.export(output_path, target_ip=target_ip)

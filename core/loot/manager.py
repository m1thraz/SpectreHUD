import uuid
import warnings
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

from core.logger import get_logger
from core.storage import (
    StorageBackend,
    InMemoryStorageBackend,
    FileStorageBackend,
    PersistenceError,
)
from core.validators import (
    MAX_CONTENT_LENGTH,
    MAX_LOOT_ENTRIES,
    MAX_TARGET_IP_LENGTH,
    MAX_TITLE_LENGTH,
)
from core.loot.migrator import LootMigrator

logger = get_logger("loot")

LOOT_TYPES = [
    {"id": "credentials", "name": "Credentials", "icon": "", "badge_class": "BadgeCreds"},
    {"id": "hash", "name": "Hashes", "icon": "", "badge_class": "BadgeHash"},
    {"id": "screenshot", "name": "Screenshots", "icon": "", "badge_class": "BadgeScreenshot"},
    {"id": "directory", "name": "Directories", "icon": "", "badge_class": "BadgeDir"},
    {"id": "flag", "name": "Flags", "icon": "", "badge_class": "BadgeFlag"},
    {"id": "note", "name": "Notes", "icon": "", "badge_class": "BadgeNote"},
]

CATEGORIES = [
    {"id": "recon", "name": "1. Reconnaissance & Enumeration", "order": 1, "icon": ""},
    {"id": "access", "name": "2. Initial Access & Exploitation", "order": 2, "icon": ""},
    {"id": "privesc", "name": "3. Privilege Escalation", "order": 3, "icon": ""},
    {"id": "postex", "name": "4. Post-Exploitation & Lateral Movement", "order": 4, "icon": ""},
    {"id": "scripts", "name": "5. Custom Scripts & PoCs", "order": 5, "icon": ""},
    {"id": "misc", "name": "6. Miscellaneous", "order": 6, "icon": ""},
]

VALID_CATEGORY_IDS: Set[str] = {str(c["id"]) for c in CATEGORIES}


class LootValidationError(ValueError):
    """Raised when user-authored loot cannot be persisted without data loss."""


class LootLimitError(LootValidationError):
    """Raised when the active session reached its maximum number of loot entries."""


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
    "hash": "hash",
}


class LootManager:
    """Manages session loot, credentials, hashes, flags and notes with persistence, categories and export."""

    def __init__(
        self,
        storage_file: Optional[Path] = None,
        storage: Optional[StorageBackend] = None,
        event_bus: Optional[Any] = None,
        time_format: str = "24h",
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

    def _publish_updated(self, action: str, entry: Optional[Dict[str, Any]] = None) -> None:
        """Publishes the single canonical event for a successful loot mutation."""
        if self.event_bus:
            from core.event_bus import EventType

            self.event_bus.publish(
                EventType.LOOT_UPDATED,
                {
                    "action": action,
                    "entry": dict(entry) if entry is not None else None,
                    "entries": self.get_all_entries(),
                },
            )

    @staticmethod
    def _validate_user_text(value: Any, field_name: str, max_length: int) -> str:
        """Reject user input that persistence would otherwise silently truncate."""
        text = str(value or "").strip()
        if len(text) > max_length:
            raise LootValidationError(
                f"{field_name} exceeds the maximum persistable length of {max_length} characters."
            )
        return text

    @staticmethod
    def _migrate_entries(
        entries: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], bool]:
        """Delegate loot schema normalization to the isolated migrator."""
        return LootMigrator.migrate(
            entries,
            valid_category_ids=VALID_CATEGORY_IDS,
            type_aliases=TYPE_ALIASES,
        )

    def load_entries(self) -> None:
        """Loads and semantically validates loot entries from storage backend."""
        from core.validators import validate_loot_list

        raw_data = self.storage.load_json("loot")
        if raw_data is not None:
            position_migration_needed = (
                any(
                    isinstance(item, dict)
                    and (
                        "position" not in item
                        or isinstance(item.get("position"), bool)
                        or not isinstance(item.get("position"), int)
                        or item.get("position", 0) < 0
                    )
                    for item in raw_data
                )
                if isinstance(raw_data, list)
                else False
            )
            self.entries = validate_loot_list(raw_data)
        else:
            self.entries = []
            position_migration_needed = False

        # Automatic migration of legacy entries lacking category or with invalid category
        self.entries, migrated = self._migrate_entries(self.entries)
        if migrated or position_migration_needed:
            logger.info(
                "Migrated legacy loot entries to include category/severity/position and persisted."
            )
            self.save_entries()

    def replace_entries(self, entries: List[Dict[str, Any]]) -> None:
        """
        Replaces in-memory loot entries from session loading without triggering disk writes.
        Validates, migrates in RAM, and emits EventType.LOOT_UPDATED.
        """
        from core.validators import validate_loot_list

        self.entries = validate_loot_list(entries)
        self.entries, _ = self._migrate_entries(self.entries)
        self._publish_updated("replace")

    def replace_entries_and_persist(self, entries: List[Dict[str, Any]]) -> None:
        """Persist a validated replacement before committing it to in-memory state."""
        from core.validators import validate_loot_list

        validated_entries = validate_loot_list(entries)
        validated_entries, migrated = self._migrate_entries(validated_entries)
        if migrated:
            logger.info("Migrated replacement loot entries before persistence.")
        if not self.storage.save_json("loot", validated_entries):
            raise PersistenceError("Could not persist replacement loot entries to storage.")
        self.entries = validated_entries
        self._publish_updated("replace")

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
        **kwargs,
    ) -> Dict[str, Any]:
        """Creates and stores a new loot entry with category and severity classification."""
        if len(self.entries) >= MAX_LOOT_ENTRIES:
            raise LootLimitError(
                f"The active project already contains the maximum of {MAX_LOOT_ENTRIES} loot entries."
            )
        from core.validators import VALID_SEVERITIES

        normalized_type = TYPE_ALIASES.get(entry_type.lower(), entry_type) if entry_type else "note"
        cat_id = category if category in VALID_CATEGORY_IDS else "misc"
        sev_clean = str(severity).lower().strip() if severity else "info"
        sev_id = sev_clean if sev_clean in VALID_SEVERITIES else "info"
        clean_title = self._validate_user_text(title, "Loot title", MAX_TITLE_LENGTH)
        clean_content = self._validate_user_text(content, "Loot content", MAX_CONTENT_LENGTH)
        clean_target_ip = self._validate_user_text(target_ip, "Target IP", MAX_TARGET_IP_LENGTH)

        from core.validators import format_timestamp

        time_format = kwargs.get("time_format", self.time_format)
        entry = {
            "id": f"loot_{uuid.uuid4().hex[:8]}",
            "type": normalized_type,
            "category": cat_id,
            "severity": sev_id,
            "title": clean_title or "Unbenannter Eintrag",
            "content": clean_content,
            "target_ip": clean_target_ip,
            "timestamp": format_timestamp(time_format=time_format),
            "position": 0,
        }
        new_entries = [entry, *self.entries]
        new_entries, _ = self._migrate_entries(new_entries)
        entry = next(candidate for candidate in new_entries if candidate.get("id") == entry["id"])
        if not self.storage.save_json("loot", new_entries):
            raise PersistenceError("Could not persist new loot entry to storage.")
        self.entries = new_entries
        self._publish_updated("add", entry)
        return entry

    def update_entry(self, entry_id: str, **fields) -> Optional[Dict[str, Any]]:
        """Updates fields of an existing entry by ID and persists changes."""
        from core.validators import VALID_SEVERITIES

        new_entries = [dict(e) for e in self.entries]
        updated_entry = None
        for entry in new_entries:
            if entry.get("id") == entry_id:
                previous_category = entry.get("category", "misc")
                if "category" in fields:
                    cat = fields["category"]
                    entry["category"] = cat if cat in VALID_CATEGORY_IDS else "misc"
                    if entry["category"] != previous_category:
                        entry["position"] = sum(
                            1
                            for candidate in new_entries
                            if candidate is not entry
                            and candidate.get("category") == entry["category"]
                        )
                if "severity" in fields:
                    raw_sev = (
                        str(fields["severity"]).lower().strip() if fields["severity"] else "info"
                    )
                    entry["severity"] = raw_sev if raw_sev in VALID_SEVERITIES else "info"
                if "type" in fields:
                    raw_type = fields["type"]
                    entry["type"] = (
                        TYPE_ALIASES.get(raw_type.lower(), raw_type) if raw_type else "note"
                    )
                if "title" in fields:
                    entry["title"] = (
                        self._validate_user_text(fields["title"], "Loot title", MAX_TITLE_LENGTH)
                        or "Unbenannter Eintrag"
                    )
                if "content" in fields:
                    entry["content"] = self._validate_user_text(
                        fields["content"], "Loot content", MAX_CONTENT_LENGTH
                    )
                if "target_ip" in fields:
                    entry["target_ip"] = self._validate_user_text(
                        fields["target_ip"], "Target IP", MAX_TARGET_IP_LENGTH
                    )
                updated_entry = entry
                break

        if updated_entry is not None:
            new_entries, _ = self._migrate_entries(new_entries)
            updated_entry = next(
                entry for entry in new_entries if entry.get("id") == entry_id
            )
            if not self.storage.save_json("loot", new_entries):
                raise PersistenceError(f"Could not persist update for loot entry {entry_id}.")
            self.entries = new_entries
            self._publish_updated("update", updated_entry)
        return updated_entry

    def reorder_entry(
        self, entry_id: str, category: str, target_index: int
    ) -> Optional[Dict[str, Any]]:
        """Moves an entry to a category/index and persists both affected column orders."""
        if category not in VALID_CATEGORY_IDS:
            return None

        new_entries = [dict(entry) for entry in self.entries]
        moving_entry = next((entry for entry in new_entries if entry.get("id") == entry_id), None)
        if moving_entry is None:
            return None

        previous_category = moving_entry.get("category", "misc")
        moving_entry["category"] = category

        target_entries = sorted(
            (
                entry
                for entry in new_entries
                if entry is not moving_entry and entry.get("category") == category
            ),
            key=lambda item: item.get("position", 0),
        )
        insertion_index = max(0, min(int(target_index), len(target_entries)))
        target_entries.insert(insertion_index, moving_entry)
        for position, entry in enumerate(target_entries):
            entry["position"] = position

        if previous_category != category:
            previous_entries = sorted(
                (entry for entry in new_entries if entry.get("category") == previous_category),
                key=lambda item: item.get("position", 0),
            )
            for position, entry in enumerate(previous_entries):
                entry["position"] = position

        if not self.storage.save_json("loot", new_entries):
            raise PersistenceError(f"Could not persist reorder for loot entry {entry_id}.")
        self.entries = new_entries
        self._publish_updated("update", moving_entry)
        return moving_entry

    def delete_entry(self, entry_id: str) -> bool:
        """Deletes an entry by ID."""
        deleted_entry = next((entry for entry in self.entries if entry.get("id") == entry_id), None)
        new_entries = [e for e in self.entries if e.get("id") != entry_id]
        if len(new_entries) == len(self.entries):
            return False
        new_entries, _ = self._migrate_entries(new_entries)
        if not self.storage.save_json("loot", new_entries):
            raise PersistenceError(f"Could not persist deletion for loot entry {entry_id}.")
        self.entries = new_entries
        self._publish_updated("delete", deleted_entry)
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
        self._publish_updated("clear")
        return deleted_count

    def get_entries(
        self,
        target_ip: Optional[str] = None,
        entry_type: Optional[str] = None,
        category: Optional[str] = None,
        search_query: str = "",
    ) -> List[Dict[str, Any]]:
        """Filters loot entries by target IP, type, category and search term."""
        from core.loot.filter import filter_loot_entries

        return filter_loot_entries(
            entries=self.entries,
            target_ip=target_ip,
            entry_type=entry_type,
            category=category,
            search_query=search_query,
        )

    def get_type_counts(self, target_ip: Optional[str] = None) -> Dict[str, int]:
        """Returns count of entries grouped by loot type."""
        from core.loot.filter import count_loot_by_type

        return count_loot_by_type(self.entries, LOOT_TYPES, target_ip=target_ip)

    def get_category_counts(self, target_ip: Optional[str] = None) -> Dict[str, int]:
        """Returns count of entries grouped by category."""
        from core.loot.filter import count_loot_by_category

        return count_loot_by_category(self.entries, CATEGORIES, target_ip=target_ip)

    def export_loot(self, output_path: Path, target_ip: Optional[str] = None) -> str:
        """DEPRECATED: Use core.reporting.builder.ReportBuilder instead.

        Delegates to ReportBuilder for unified reporting.
        """
        warnings.warn(
            "LootManager.export_loot() is deprecated; use core.reporting.builder.ReportBuilder instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from core.reporting.builder import ReportBuilder

        builder = ReportBuilder(loot_manager=self)
        return builder.export(output_path, target_ip=target_ip)

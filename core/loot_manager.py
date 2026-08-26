import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.config import get_default_config_dir
from core.logger import get_logger

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

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = Path(storage_file) if storage_file is not None else None
        if self.storage_file:
            try:
                self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.error(f"Failed to create parent directory for loot storage {self.storage_file}: {e}", exc_info=True)

        self.entries: List[Dict[str, Any]] = []
        if self.storage_file:
            self.load_entries()

    def _migrate_entries(self) -> bool:
        """Ensures all entries have a valid category. Returns True if any entry was migrated."""
        migrated = False
        for entry in self.entries:
            cat = entry.get("category")
            if not cat or cat not in VALID_CATEGORY_IDS:
                entry["category"] = "misc"
                migrated = True
            
            # Also normalize type if needed
            entry_type = entry.get("type")
            norm_type = TYPE_ALIASES.get(str(entry_type).lower(), entry_type)
            if norm_type != entry_type:
                entry["type"] = norm_type
                migrated = True
        return migrated

    def load_entries(self) -> None:
        """Loads and semantically validates loot entries from local JSON file if storage_file is set."""
        if not self.storage_file:
            return
        from core.validators import validate_loot_list
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    self.entries = validate_loot_list(raw_data)
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted loot file at {self.storage_file}: {e}")
                self.entries = []
            except (OSError, UnicodeDecodeError) as e:
                logger.error(f"Error reading loot file {self.storage_file}: {e}")
                self.entries = []
        else:
            self.entries = []

        # Automatic migration of legacy entries lacking category or with invalid category
        if self._migrate_entries():
            logger.info("Migrated legacy loot entries to include category and persisted to disk.")
            self.save_entries()

    def set_entries(self, entries: List[Dict[str, Any]]) -> None:
        """Replaces current entries with a validated list (e.g. on project switch) and migrates immediately."""
        from core.validators import validate_loot_list
        self.entries = validate_loot_list(entries)
        if self._migrate_entries():
            logger.info("Migrated entries set on project switch and persisted to disk.")
        self.save_entries()

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Returns all entries raw."""
        return self.entries

    def save_entries(self) -> None:
        """Persists loot entries to disk atomically if storage_file is configured."""
        if not self.storage_file:
            return
        from core.atomic_write import atomic_write_json
        try:
            atomic_write_json(self.storage_file, self.entries, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"OS error saving loot file to {self.storage_file}: {e}", exc_info=True)
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization error saving loot file to {self.storage_file}: {e}")

    def add_entry(
        self, 
        entry_type: str, 
        title: str, 
        content: str, 
        target_ip: str = "", 
        category: str = "misc",
        **kwargs
    ) -> Dict[str, Any]:
        """Creates and stores a new loot entry with category classification."""
        normalized_type = TYPE_ALIASES.get(entry_type.lower(), entry_type) if entry_type else "note"
        cat_id = category if category in VALID_CATEGORY_IDS else "misc"
        
        entry = {
            "id": f"loot_{uuid.uuid4().hex[:8]}",
            "type": normalized_type,
            "category": cat_id,
            "title": title.strip() or "Unbenannter Eintrag",
            "content": content.strip(),
            "target_ip": target_ip.strip(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.entries.insert(0, entry)  # Most recent first
        self.save_entries()
        return entry

    def update_entry(self, entry_id: str, **fields) -> Optional[Dict[str, Any]]:
        """Updates fields of an existing entry by ID and persists changes."""
        for entry in self.entries:
            if entry.get("id") == entry_id:
                if "category" in fields:
                    cat = fields["category"]
                    entry["category"] = cat if cat in VALID_CATEGORY_IDS else "misc"
                if "type" in fields:
                    raw_type = fields["type"]
                    entry["type"] = TYPE_ALIASES.get(raw_type.lower(), raw_type) if raw_type else "note"
                if "title" in fields:
                    entry["title"] = fields["title"].strip() or "Unbenannter Eintrag"
                if "content" in fields:
                    entry["content"] = fields["content"].strip()
                if "target_ip" in fields:
                    entry["target_ip"] = fields["target_ip"].strip()
                
                self.save_entries()
                return entry
        return None

    def delete_entry(self, entry_id: str) -> bool:
        """Deletes an entry by ID."""
        for i, entry in enumerate(self.entries):
            if entry.get("id") == entry_id:
                self.entries.pop(i)
                self.save_entries()
                return True
        return False

    def clear_session(self, target_ip: Optional[str] = None) -> int:
        """Clears all entries, or only those matching a specific target IP."""
        if target_ip:
            before_count = len(self.entries)
            self.entries = [e for e in self.entries if e.get("target_ip") != target_ip]
            deleted_count = before_count - len(self.entries)
        else:
            deleted_count = len(self.entries)
            self.entries = []
        self.save_entries()
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
            return results

        q = search_query.strip().lower()
        filtered = []
        for e in results:
            title = e.get("title", "").lower()
            content = e.get("content", "").lower()
            target = e.get("target_ip", "").lower()
            cat = e.get("category", "").lower()
            if q in title or q in content or q in target or q in cat:
                filtered.append(e)

        return filtered

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

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.config import get_default_config_dir
from core.logger import get_logger

logger = get_logger("loot")

LOOT_TYPES = [
    {"id": "credentials", "name": "🔑 Credentials / Logins", "icon": "🔑", "badge_class": "BadgeCreds"},
    {"id": "hash", "name": "🔐 Hashes", "icon": "🔐", "badge_class": "BadgeHash"},
    {"id": "screenshot", "name": "📷 Screenshots", "icon": "📷", "badge_class": "BadgeScreenshot"},
    {"id": "directory", "name": "📂 Directories / URLs", "icon": "📂", "badge_class": "BadgeDir"},
    {"id": "flag", "name": "🚩 Flags", "icon": "🚩", "badge_class": "BadgeFlag"},
    {"id": "note", "name": "📝 Notizen & Sonstiges", "icon": "📝", "badge_class": "BadgeNote"}
]

class LootManager:
    """Manages session loot, credentials, hashes, flags and notes with persistence and export."""

    def __init__(self, storage_file: Optional[Path] = None):
        if storage_file is None:
            storage_file = get_default_config_dir() / "loot_sessions.json"
        self.storage_file = Path(storage_file)
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create parent directory for loot storage {self.storage_file}: {e}", exc_info=True)

        self.entries: List[Dict[str, Any]] = []
        self.load_entries()

    def load_entries(self) -> None:
        """Loads loot entries from local JSON file."""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self.entries = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted loot file at {self.storage_file}: {e}")
                self.entries = []
            except Exception as e:
                logger.exception(f"Unexpected error reading loot file {self.storage_file}: {e}")
                self.entries = []
        else:
            self.entries = []

    def set_entries(self, entries: List[Dict[str, Any]]) -> None:
        """Replaces current entries with a new list (e.g. on project switch)."""
        self.entries = entries or []
        self.save_entries()

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Returns all entries raw."""
        return self.entries

    def save_entries(self) -> None:
        """Persists loot entries to disk."""
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"OS error saving loot file to {self.storage_file}: {e}", exc_info=True)
        except Exception as e:
            logger.exception(f"Unexpected error saving loot file to {self.storage_file}: {e}")

    def add_entry(self, entry_type: str, title: str, content: str, target_ip: str = "") -> Dict[str, Any]:
        """Creates and stores a new loot entry."""
        type_aliases = {
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
        normalized_type = type_aliases.get(entry_type.lower(), entry_type) if entry_type else "note"
        entry = {
            "id": f"loot_{uuid.uuid4().hex[:8]}",
            "type": normalized_type,
            "title": title.strip() or "Unbenannter Eintrag",
            "content": content.strip(),
            "target_ip": target_ip.strip(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.entries.insert(0, entry)  # Most recent first
        self.save_entries()
        return entry

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

    def get_entries(self, target_ip: Optional[str] = None, entry_type: Optional[str] = None, search_query: str = "") -> List[Dict[str, Any]]:
        """Filters loot entries by target IP, type and search term."""
        results = self.entries

        if target_ip and target_ip != "all":
            results = [e for e in results if e.get("target_ip") == target_ip or not e.get("target_ip")]

        if entry_type and entry_type != "all":
            type_aliases = {
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
            norm_type = type_aliases.get(entry_type.lower(), entry_type)
            results = [e for e in results if type_aliases.get(e.get("type", "").lower(), e.get("type")) == norm_type]

        if not search_query or not search_query.strip():
            return results

        q = search_query.strip().lower()
        filtered = []
        for e in results:
            title = e.get("title", "").lower()
            content = e.get("content", "").lower()
            target = e.get("target_ip", "").lower()
            if q in title or q in content or q in target:
                filtered.append(e)

        return filtered

    def get_type_counts(self, target_ip: Optional[str] = None) -> Dict[str, int]:
        """Returns count of entries grouped by loot type."""
        entries = self.get_entries(target_ip=target_ip)
        counts = {"all": len(entries)}
        for t in LOOT_TYPES:
            counts[t["id"]] = sum(1 for e in entries if e.get("type") == t["id"])
        return counts

    def export_loot(self, output_path: Path, target_ip: Optional[str] = None) -> str:
        """Exports loot entries to a structured Markdown (.md) file with embedded screenshots."""
        entries = self.get_entries(target_ip=target_ip)
        if not entries:
            return "Keine Loot-Einträge zum Exportieren vorhanden."

        output_path = Path(output_path)
        if output_path.suffix.lower() != ".md":
            output_path = output_path.with_suffix(".md")

        lines = [
            f"# 🎯 CTF Session Loot Export",
            f"**Erstellt am:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`  ",
            f"**Target:** `{target_ip if target_ip and target_ip != 'all' else 'Alle Targets'}`  ",
            f"**Gesamtanzahl Einträge:** {len(entries)}  ",
            "",
            "---",
            ""
        ]

        # Group by type
        for t in LOOT_TYPES:
            type_entries = [e for e in entries if e.get("type") == t["id"]]
            if not type_entries:
                continue

            lines.append(f"## {t['name']} ({len(type_entries)})")
            lines.append("")

            for e in type_entries:
                lines.append(f"### {e.get('title')}")
                meta_info = []
                if e.get("target_ip"):
                    meta_info.append(f"**Target:** `{e.get('target_ip')}`")
                if e.get("timestamp"):
                    meta_info.append(f"**Zeit:** `{e.get('timestamp')}`")
                if meta_info:
                    lines.append(" | ".join(meta_info))
                lines.append("")

                content = e.get("content", "").strip()
                if t["id"] == "screenshot":
                    # Embed markdown image directly
                    if content.startswith("![") and content.endswith(")"):
                        lines.append(content)
                    else:
                        lines.append(f"![{e.get('title')}]({content})")
                elif t["id"] in ["cred", "hash", "flag"]:
                    lines.append("```")
                    lines.append(content)
                    lines.append("```")
                elif t["id"] == "dir":
                    lines.append(f"`{content}`")
                else:
                    lines.append(content)
                
                lines.append("")

            lines.append("---")
            lines.append("")

        md_content = "\n".join(lines)
        try:
            output_path.write_text(md_content, encoding="utf-8")
            return f"Erfolgreich als Markdown exportiert nach {output_path.name}"
        except OSError as e:
            logger.error(f"Failed to export loot to {output_path}: {e}", exc_info=True)
            return f"Fehler beim Exportieren: {e}"

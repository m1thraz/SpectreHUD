import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

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
            storage_file = Path.home() / ".ctf_cheatsheet_widget" / "loot_sessions.json"
        self.storage_file = storage_file
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.entries: List[Dict[str, Any]] = []
        self.load_entries()

    def load_entries(self) -> None:
        """Loads loot entries from local JSON file."""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self.entries = json.load(f)
            except Exception as e:
                print(f"[LootManager] Error reading loot file: {e}")
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
        except Exception as e:
            print(f"[LootManager] Error saving loot file: {e}")

    def add_entry(self, entry_type: str, title: str, content: str, target_ip: str = "") -> Dict[str, Any]:
        """Creates and stores a new loot entry."""
        entry = {
            "id": f"loot_{uuid.uuid4().hex[:8]}",
            "type": entry_type or "note",
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
            results = [e for e in results if e.get("type") == entry_type]

        if not search_query or not search_query.strip():
            return results

        q = search_query.strip().lower()
        terms = q.split()

        filtered = []
        for e in results:
            title = e.get("title", "").lower()
            content = e.get("content", "").lower()
            ip = e.get("target_ip", "").lower()
            etype = e.get("type", "").lower()

            combined = f"{title} {content} {ip} {etype}"
            if all(term in combined for term in terms):
                filtered.append(e)

        return filtered

    def get_type_counts(self, target_ip: Optional[str] = None) -> Dict[str, int]:
        """Returns counts for each loot type."""
        entries = self.get_entries(target_ip=target_ip)
        counts = {"all": len(entries)}
        for t in LOOT_TYPES:
            counts[t["id"]] = sum(1 for e in entries if e.get("type") == t["id"])
        return counts

    def export_loot(self, output_path: Path, target_ip: Optional[str] = None) -> str:
        """Exports entries to a clean structured markdown or text file."""
        entries = self.get_entries(target_ip=target_ip)
        if not entries:
            return "Keine Einträge zum Exportieren vorhanden."

        lines = [
            f"# 🎯 CTF Session Loot Export",
            f"Erstellt am: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Target IP: {target_ip if target_ip else 'Alle Targets'}",
            f"Gesamtanzahl Einträge: {len(entries)}",
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
                if e.get("target_ip"):
                    lines.append(f"**Target:** `{e.get('target_ip')}` | **Zeit:** {e.get('timestamp')}")
                else:
                    lines.append(f"**Zeit:** {e.get('timestamp')}")
                lines.append("")
                lines.append("```")
                lines.append(e.get("content", ""))
                lines.append("```")
                lines.append("")

            lines.append("---")
            lines.append("")

        content = "\n".join(lines)
        output_path.write_text(content, encoding="utf-8")
        return f"Erfolgreich exportiert nach {output_path.name}"

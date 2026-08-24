import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.config import get_default_config_dir

MAX_CLIPBOARD_TEXT_SIZE = 64 * 1024  # 64 KB

class ClipboardWatcher(QObject):
    """
    Monitors system clipboard in background, logs command copies & outputs,
    filters duplicates, and persists history.
    """
    entry_added = pyqtSignal(dict)

    def __init__(self, storage_file: Optional[Path] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        if storage_file is None:
            storage_file = get_default_config_dir() / "clipboard_history.json"
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.history: List[Dict[str, Any]] = []
        self._last_copied_text: Optional[str] = None
        self._is_paused: bool = False
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
                except Exception:
                    pass

            self.add_entry(text, target_ip=target_ip)
        except Exception as e:
            print(f"[ClipboardWatcher] Error reading clipboard: {e}")

    def add_entry(self, text: str, target_ip: str = "") -> Optional[Dict[str, Any]]:
        """Adds a new sanitized entry if not a consecutive duplicate."""
        if not text or not text.strip():
            return None

        # Ignore huge binary or dump pastes
        if len(text) > MAX_CLIPBOARD_TEXT_SIZE:
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

        self.history.insert(0, entry)
        # Keep maximum 500 session history items
        if len(self.history) > 500:
            self.history = self.history[:500]

        self.save_history()
        self.entry_added.emit(entry)
        return entry

    def load_history(self) -> None:
        """Loads history from disk."""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
            except Exception as e:
                print(f"[ClipboardWatcher] Error reading history: {e}")
                self.history = []
        else:
            self.history = []

    def set_history(self, history: List[Dict[str, Any]]) -> None:
        """Replaces history with a new list (e.g. on project switch)."""
        self.history = history or []
        self._last_copied_text = self.history[0]["text"] if self.history else None
        self.save_history()

    def get_all_history(self) -> List[Dict[str, Any]]:
        """Returns all history items raw."""
        return self.history

    def save_history(self) -> None:
        """Saves history to disk."""
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ClipboardWatcher] Error saving history: {e}")

    def delete_entry(self, entry_id: str) -> bool:
        """Removes an entry by ID."""
        for i, entry in enumerate(self.history):
            if entry.get("id") == entry_id:
                self.history.pop(i)
                self.save_history()
                return True
        return False

    def clear_history(self) -> int:
        """Clears all clipboard history."""
        count = len(self.history)
        self.history = []
        self._last_copied_text = None
        self.save_history()
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
        terms = q.split()

        filtered = []
        for e in results:
            text = e.get("text", "").lower()
            ip = e.get("target_ip", "").lower()
            combined = f"{text} {ip}"
            if all(term in combined for term in terms):
                filtered.append(e)

        return filtered

    def toggle_pause(self) -> bool:
        """Toggles clipboard monitoring pause state."""
        self._is_paused = not self._is_paused
        return self._is_paused

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def export_report_markdown(self, output_path: Path, target_ip: Optional[str] = None, loot_manager = None) -> str:
        """Generates a complete, structured CTF Write-up & Command Log Report."""
        history_items = self.get_history(target_ip=target_ip)
        
        lines = [
            f"# 🛡️ CTF Session Report & Write-Up Log",
            f"**Datum & Uhrzeit:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"**Target IP:** `{target_ip if target_ip else 'Alle Targets'}`  ",
            "",
            "---",
            "",
            "## 📋 1. Beute & Gesammelte Credentials (Loot Summary)",
            ""
        ]

        # Add Loot Section if loot_manager provided
        if loot_manager:
            loot_entries = loot_manager.get_entries(target_ip=target_ip)
            if loot_entries:
                for item in loot_entries:
                    lines.append(f"- **[{item.get('type', 'note').upper()}] {item.get('title')}:**")
                    lines.append(f"  ```")
                    lines.append(f"  {item.get('content')}")
                    lines.append(f"  ```")
            else:
                lines.append("*Keine Loot-Einträge erfasst.*")
        else:
            lines.append("*Kein Loot-Manager verknüpft.*")

        lines.extend([
            "",
            "---",
            "",
            "## 📜 2. Chronologischer Befehls- & Ausgabenverlauf (Command History)",
            ""
        ])

        if not history_items:
            lines.append("*Keine Clipboard-Historie vorhanden.*")
        else:
            # Chronological order (oldest first for write-up flow)
            for item in reversed(history_items):
                ts = item.get("timestamp", "")
                ip_badge = f" [Target: `{item.get('target_ip')}`]" if item.get("target_ip") else ""
                lines.append(f"### 🕒 {ts}{ip_badge}")
                lines.append("```bash")
                lines.append(item.get("text", ""))
                lines.append("```")
                lines.append("")

        lines.extend([
            "---",
            "",
            "## 📝 3. Eigene Notizen & Fazit",
            "",
            "- **Root Cause / Initial Access:** ",
            "- **Privilege Escalation:** ",
            "- **Gelerntes / Highlights:** ",
            ""
        ])

        output_path.write_text("\n".join(lines), encoding="utf-8")
        return f"Report erfolgreich generiert: {output_path.name}"

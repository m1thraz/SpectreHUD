import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.config import get_default_config_dir
from core.logger import get_logger

logger = get_logger("clipboard")

MAX_CLIPBOARD_TEXT_SIZE = 64 * 1024  # 64 KB

class ClipboardWatcher(QObject):
    """
    Monitors system clipboard in background, logs command copies & outputs,
    filters duplicates, and persists history.
    """
    entry_added = pyqtSignal(dict)
    logging_state_changed = pyqtSignal(bool)

    def __init__(self, storage_file: Optional[Path] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        if storage_file is None:
            storage_file = get_default_config_dir() / "clipboard_history.json"
        self.storage_file = Path(storage_file)
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create directory for clipboard storage {self.storage_file}: {e}", exc_info=True)
        
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
                except Exception as e:
                    logger.debug(f"Error resolving target_ip in clipboard provider: {e}")

            self.add_entry(text, target_ip=target_ip)
        except Exception as e:
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
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted clipboard history JSON at {self.storage_file}: {e}")
                self.history = []
            except Exception as e:
                logger.exception(f"Unexpected error reading clipboard history from {self.storage_file}: {e}")
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
        except OSError as e:
            logger.error(f"OS error saving clipboard history to {self.storage_file}: {e}", exc_info=True)
        except Exception as e:
            logger.exception(f"Unexpected error saving clipboard history to {self.storage_file}: {e}")

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
        """Generates a structured Markdown CTF writeup/report draft."""
        history_items = self.get_history(target_ip=target_ip)
        
        target_display = target_ip if target_ip and target_ip != "all" else "Generisch / Multi-Target"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            f"# 🛡️ CTF Session Report: {target_display}",
            f"**Datum & Uhrzeit:** `{now_str}`  ",
            f"**Ziel-IP:** `{target_display}`  ",
            "",
            "---",
            "",
            "## 🏆 1. Session Loot & Credentials",
            ""
        ]

        # 1. Integrate Loot if available
        if loot_manager:
            loot_entries = loot_manager.get_entries(target_ip=target_ip)
            if loot_entries:
                for entry in loot_entries:
                    badge = entry.get("type", "note").upper()
                    lines.append(f"### [{badge}] {entry.get('title')}")
                    lines.append(f"- **Zeitstempel:** {entry.get('timestamp')}")
                    if entry.get("target_ip"):
                        lines.append(f"- **Target:** `{entry.get('target_ip')}`")
                    lines.append("")
                    lines.append("```")
                    lines.append(entry.get("content", ""))
                    lines.append("```")
                    lines.append("")
            else:
                lines.append("*Keine Loot-Einträge für diese Session protokolliert.*")
                lines.append("")
        else:
            lines.append("*Loot-Manager nicht verknüpft.*")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## ⚡ 2. Chronologischer Befehlsverlauf (Terminal History)",
            ""
        ])

        # 2. Integrate Commands/Outputs in chronological order (oldest first)
        if not history_items:
            lines.append("*Keine Clipboard-Historie aufgezeichnet.*")
            lines.append("")
        else:
            chronological = list(reversed(history_items))
            for i, item in enumerate(chronological, start=1):
                ts = item.get("timestamp", "").split(" ")[-1]
                target_tag = f" `[{item.get('target_ip')}]`" if item.get("target_ip") else ""
                lines.append(f"#### {i}. `{ts}`{target_tag}")
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

        try:
            output_path.write_text("\n".join(lines), encoding="utf-8")
            return f"Report erfolgreich generiert: {output_path.name}"
        except OSError as e:
            logger.error(f"Failed to export report to {output_path}: {e}", exc_info=True)
            return f"Fehler beim Generieren des Reports: {e}"

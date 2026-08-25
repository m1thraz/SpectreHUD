"""
Semantic validation and schema normalization for JSON data structures.
Protects against malformed data types (e.g. str instead of list, missing dict keys)
when loading user-editable JSON files.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime


def validate_loot_entry(entry: Any) -> Optional[Dict[str, Any]]:
    """Validates and normalizes a single loot item dictionary."""
    if not isinstance(entry, dict):
        return None

    entry_id = str(entry.get("id") or "")
    entry_type = str(entry.get("type") or "note").strip().lower()
    category = str(entry.get("category") or "misc").strip().lower()
    title = str(entry.get("title") or "Unbenannter Eintrag").strip()
    content = str(entry.get("content") or "").strip()
    target_ip = str(entry.get("target_ip") or "").strip()
    timestamp = str(entry.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    return {
        "id": entry_id or f"loot_gen_{hash(title) & 0xFFFFFFFF:08x}",
        "type": entry_type or "note",
        "category": category or "misc",
        "title": title or "Unbenannter Eintrag",
        "content": content,
        "target_ip": target_ip,
        "timestamp": timestamp
    }


def validate_loot_list(data: Any) -> List[Dict[str, Any]]:
    """Validates and normalizes a list of loot entries."""
    if not isinstance(data, list):
        return []
    valid_entries = []
    for item in data:
        validated = validate_loot_entry(item)
        if validated is not None:
            valid_entries.append(validated)
    return valid_entries


def validate_clipboard_entry(entry: Any) -> Optional[Dict[str, Any]]:
    """Validates and normalizes a single clipboard history item dictionary."""
    if not isinstance(entry, dict):
        return None

    text = str(entry.get("text") or "").strip()
    if not text:
        return None

    entry_id = str(entry.get("id") or "")
    target_ip = str(entry.get("target_ip") or "").strip()
    timestamp = str(entry.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    lines_count = entry.get("lines_count")
    if not isinstance(lines_count, int) or lines_count < 1:
        lines_count = text.count("\n") + 1

    char_count = entry.get("char_count")
    if not isinstance(char_count, int) or char_count < 0:
        char_count = len(text)

    is_multiline = bool(entry.get("is_multiline", lines_count > 2 or char_count > 120))

    return {
        "id": entry_id or f"clip_gen_{hash(text) & 0xFFFFFFFF:08x}",
        "text": text,
        "target_ip": target_ip,
        "timestamp": timestamp,
        "lines_count": lines_count,
        "char_count": char_count,
        "is_multiline": is_multiline
    }


def validate_clipboard_list(data: Any) -> List[Dict[str, Any]]:
    """Validates and normalizes a list of clipboard history entries."""
    if not isinstance(data, list):
        return []
    valid_entries = []
    for item in data:
        validated = validate_clipboard_entry(item)
        if validated is not None:
            valid_entries.append(validated)
    return valid_entries


def validate_project_state(data: Any, fallback_name: str = "Default") -> Dict[str, Any]:
    """
    Validates and normalizes the full project_state.json schema.
    Ensures all expected keys and nested structures (loot list, clipboard list) exist.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    default_state = {
        "name": fallback_name,
        "target_ip": "10.10.10.10",
        "attacker_ip": "10.10.14.5",
        "port": "4444",
        "wordlist": "/usr/share/wordlists/dirb/common.txt",
        "created_at": now_str,
        "updated_at": now_str,
        "loot": [],
        "clipboard_history": []
    }

    if not isinstance(data, dict):
        return default_state

    return {
        "name": str(data.get("name") or fallback_name),
        "target_ip": str(data.get("target_ip") or "10.10.10.10"),
        "attacker_ip": str(data.get("attacker_ip") or "10.10.14.5"),
        "port": str(data.get("port") or "4444"),
        "wordlist": str(data.get("wordlist") or "/usr/share/wordlists/dirb/common.txt"),
        "created_at": str(data.get("created_at") or now_str),
        "updated_at": str(data.get("updated_at") or now_str),
        "loot": validate_loot_list(data.get("loot")),
        "clipboard_history": validate_clipboard_list(data.get("clipboard_history"))
    }


def validate_user_snippets(data: Any) -> List[Dict[str, Any]]:
    """Validates and normalizes user custom snippets list."""
    if not isinstance(data, list):
        return []
    valid = []
    for s in data:
        if isinstance(s, dict) and s.get("title") and s.get("template"):
            valid.append({
                "id": str(s.get("id") or f"snip_{hash(s['title']) & 0xFFFFFFFF:08x}"),
                "title": str(s.get("title")),
                "template": str(s.get("template")),
                "category": str(s.get("category") or "Custom"),
                "category_id": str(s.get("category_id") or "custom_snippets"),
                "subcategory": str(s.get("subcategory") or "Allgemein"),
                "description": str(s.get("description") or ""),
                "tags": [str(t) for t in s.get("tags", [])] if isinstance(s.get("tags"), list) else [],
                "is_custom": True
            })
    return valid

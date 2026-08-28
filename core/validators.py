"""
Semantic validation and schema normalization for JSON data structures.
Protects against malformed data types (e.g. str instead of list, missing dict keys)
when loading user-editable JSON files.
"""

import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime


# Raw file size bounds before JSON decoding (defense against parsing Gigabyte JSON bombs)
MAX_PROJECT_STATE_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
MAX_LOOT_FILE_SIZE: int = 10 * 1024 * 1024           # 10 MB
MAX_CLIPBOARD_FILE_SIZE: int = 5 * 1024 * 1024       # 5 MB
MAX_SNIPPETS_FILE_SIZE: int = 5 * 1024 * 1024        # 5 MB
MAX_CONFIG_FILE_SIZE: int = 1 * 1024 * 1024          # 1 MB
MAX_REGISTRY_FILE_SIZE: int = 2 * 1024 * 1024        # 2 MB
MAX_REPORT_FILE_SIZE: int = 10 * 1024 * 1024         # 10 MB
MAX_TEMPLATE_FILE_SIZE: int = 512 * 1024             # 512 KB

# Content & payload size bounds (defense against bloated / malicious project states)
MAX_LOOT_ENTRIES: int = 1000
MAX_CLIPBOARD_ENTRIES: int = 500
MAX_USER_SNIPPETS: int = 500

MAX_TITLE_LENGTH: int = 256
MAX_CONTENT_LENGTH: int = 128 * 1024        # 128 KB
MAX_CLIPBOARD_TEXT_LENGTH: int = 64 * 1024  # 64 KB (matches live recorder)
MAX_TARGET_IP_LENGTH: int = 128
MAX_TIMESTAMP_LENGTH: int = 64
MAX_PROJECT_NAME_LENGTH: int = 128

VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}

# Windows reserved device names (case-insensitive, including stem checks like CON.txt)
WINDOWS_RESERVED_DEVICE_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}


def is_windows_reserved_name(name: str) -> bool:
    """Checks if a name or its stem matches Windows reserved device names."""
    if not name:
        return False
    clean = str(name).strip()
    stem = clean.split(".")[0].strip().upper()
    return stem in WINDOWS_RESERVED_DEVICE_NAMES or clean.upper() in WINDOWS_RESERVED_DEVICE_NAMES


def format_timestamp(dt: Optional[datetime] = None, time_format: str = "24h") -> str:
    """
    Formats a datetime object (or now) according to the configured time_format ('24h' or '12h').
    """
    if dt is None:
        dt = datetime.now()
    if str(time_format).strip().lower() == "12h":
        return dt.strftime("%Y-%m-%d %I:%M:%S %p")
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def is_file_size_valid(file_path: Any, max_bytes: int) -> bool:
    """
    Checks if file exists and does not exceed maximum allowable byte size.
    Returns False if file does not exist or exceeds limit.
    """
    try:
        from pathlib import Path
        p = Path(file_path)
        if not p.exists():
            return False
        return p.stat().st_size <= max_bytes
    except OSError:
        return False


def _stable_hash_id(prefix: str, content: str) -> str:
    """Generates a deterministic, process-independent fallback ID using MD5."""
    digest = hashlib.md5(content.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"{prefix}_{digest}"


def validate_loot_entry(entry: Any) -> Optional[Dict[str, Any]]:
    """Validates, bounds, and normalizes a single loot item dictionary."""
    if not isinstance(entry, dict):
        return None

    entry_id = str(entry.get("id") or "")[:64]
    entry_type = str(entry.get("type") or "note").strip().lower()[:32]
    category = str(entry.get("category") or "misc").strip().lower()[:32]
    raw_sev = str(entry.get("severity") or "info").strip().lower()[:16]
    severity = raw_sev if raw_sev in VALID_SEVERITIES else "info"
    title = str(entry.get("title") or "Unbenannter Eintrag").strip()[:MAX_TITLE_LENGTH]
    content = str(entry.get("content") or "").strip()[:MAX_CONTENT_LENGTH]
    target_ip = str(entry.get("target_ip") or "").strip()[:MAX_TARGET_IP_LENGTH]
    timestamp = str(entry.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))[:MAX_TIMESTAMP_LENGTH]

    return {
        "id": entry_id or _stable_hash_id("loot_gen", f"{title}:{content}"),
        "type": entry_type or "note",
        "category": category or "misc",
        "severity": severity,
        "title": title or "Unbenannter Eintrag",
        "content": content,
        "target_ip": target_ip,
        "timestamp": timestamp
    }


def validate_loot_list(data: Any, max_entries: int = MAX_LOOT_ENTRIES) -> List[Dict[str, Any]]:
    """Validates, normalizes, and caps a list of loot entries."""
    if not isinstance(data, list):
        return []
    valid_entries = []
    for item in data:
        validated = validate_loot_entry(item)
        if validated is not None:
            valid_entries.append(validated)
            if len(valid_entries) >= max_entries:
                break
    return valid_entries


def validate_clipboard_entry(entry: Any) -> Optional[Dict[str, Any]]:
    """Validates, bounds, and normalizes a single clipboard history item dictionary."""
    if not isinstance(entry, dict):
        return None

    raw_text = str(entry.get("text") or "").strip()
    if not raw_text:
        return None

    # Cap text length to 64 KB
    text = raw_text[:MAX_CLIPBOARD_TEXT_LENGTH]

    entry_id = str(entry.get("id") or "")[:64]
    target_ip = str(entry.get("target_ip") or "").strip()[:MAX_TARGET_IP_LENGTH]
    timestamp = str(entry.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))[:MAX_TIMESTAMP_LENGTH]
    
    # Derive canonical metadata strictly from text content
    char_count = len(text)
    lines_count = text.count("\n") + 1
    is_multiline = ("\n" in text) or (char_count > 120)

    return {
        "id": entry_id or _stable_hash_id("clip_gen", text),
        "text": text,
        "target_ip": target_ip,
        "timestamp": timestamp,
        "lines_count": lines_count,
        "char_count": char_count,
        "is_multiline": is_multiline
    }


def validate_clipboard_list(data: Any, max_entries: int = MAX_CLIPBOARD_ENTRIES) -> List[Dict[str, Any]]:
    """Validates, normalizes, and caps a list of clipboard history entries."""
    if not isinstance(data, list):
        return []
    valid_entries = []
    for item in data:
        validated = validate_clipboard_entry(item)
        if validated is not None:
            valid_entries.append(validated)
            if len(valid_entries) >= max_entries:
                break
    return valid_entries


def validate_project_state(data: Any, fallback_name: str = "Default") -> Dict[str, Any]:
    """
    Validates and normalizes the full project_state.json schema.
    Ensures all expected keys and nested structures (loot list, clipboard list) exist,
    strictly bounding all string lengths and list sizes without corrupting credentials.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    default_state = {
        "name": fallback_name[:MAX_PROJECT_NAME_LENGTH],
        "target_ip": "10.10.10.10",
        "attacker_ip": "10.10.14.5",
        "port": "4444",
        "username": "",
        "password": "",
        "wordlist": "/usr/share/wordlists/dirb/common.txt",
        "created_at": now_str,
        "updated_at": now_str,
        "loot": [],
        "clipboard_history": []
    }

    if not isinstance(data, dict):
        return default_state

    return {
        "name": str(data.get("name") or fallback_name)[:MAX_PROJECT_NAME_LENGTH],
        "target_ip": str(data.get("target_ip") or "10.10.10.10")[:MAX_TARGET_IP_LENGTH],
        "attacker_ip": str(data.get("attacker_ip") or "10.10.14.5")[:MAX_TARGET_IP_LENGTH],
        "port": str(data.get("port") or "4444")[:32],
        "username": str(data.get("username") or "")[:1024],
        "password": str(data.get("password") or "")[:1024],
        "wordlist": str(data.get("wordlist") or "/usr/share/wordlists/dirb/common.txt")[:1024],
        "created_at": str(data.get("created_at") or now_str)[:MAX_TIMESTAMP_LENGTH],
        "updated_at": str(data.get("updated_at") or now_str)[:MAX_TIMESTAMP_LENGTH],
        "loot": validate_loot_list(data.get("loot")),
        "clipboard_history": validate_clipboard_list(data.get("clipboard_history"))
    }


def validate_user_snippets(data: Any, max_entries: int = MAX_USER_SNIPPETS) -> List[Dict[str, Any]]:
    """Validates, normalizes, and caps user custom snippets list."""
    if not isinstance(data, list):
        return []
    valid = []
    for s in data:
        if isinstance(s, dict) and s.get("title") and s.get("template"):
            title = str(s.get("title"))[:MAX_TITLE_LENGTH]
            template = str(s.get("template"))[:MAX_CONTENT_LENGTH]
            valid.append({
                "id": str(s.get("id") or _stable_hash_id("snip", title))[:64],
                "title": title,
                "template": template,
                "category": str(s.get("category") or "Custom")[:64],
                "category_id": str(s.get("category_id") or "custom_snippets")[:64],
                "subcategory": str(s.get("subcategory") or "Allgemein")[:64],
                "description": str(s.get("description") or "")[:2048],
                "tags": [str(t)[:64] for t in s.get("tags", [])][:32] if isinstance(s.get("tags"), list) else [],
                "is_custom": True
            })
            if len(valid) >= max_entries:
                break
    return valid

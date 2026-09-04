"""Pure formatting helpers for appending Quick Notes to Markdown reports."""

from typing import Any, Mapping, Optional


def format_report_note(note: Mapping[str, Any]) -> Optional[str]:
    """Return a Markdown block for a Quick Note, or ``None`` for empty notes."""
    text = str(note.get("text") or "").strip()
    if not text:
        return None

    category = str(note.get("category") or "misc").upper()
    timestamp = str(note.get("timestamp") or "")
    target_ip = str(note.get("target_ip") or "").strip()

    header = f"### Note ({category})"
    if target_ip:
        header += f" - [{target_ip}]"
    if timestamp:
        header += f" ({timestamp})"

    return f"{header}\n\n{text}"


def append_report_note(
    current_content: str,
    project_name: str,
    note: Mapping[str, Any],
) -> Optional[str]:
    """Append a formatted Quick Note to existing report content."""
    note_block = format_report_note(note)
    if note_block is None:
        return None

    base_content = str(current_content or "")
    if not base_content.strip():
        base_content = f"# CTF Report - {project_name}\n"

    return f"{base_content.rstrip()}\n\n{note_block}\n"

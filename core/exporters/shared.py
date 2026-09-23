"""Shared export-domain rendering and project-attachment rules."""

from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from core.reporting import MAX_EMBED_IMAGE_FILE_SIZE


def safe_attachment_source(raw_path: str, project_dir: Path) -> Optional[Path]:
    raw_path = raw_path.strip()
    if not raw_path or raw_path.startswith(("#", "data:", "http:", "https:")):
        return None
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return None
    resolved_project = project_dir.resolve()
    try:
        resolved = (project_dir / candidate).resolve(strict=True)
    except OSError:
        return None
    if (
        not resolved.is_relative_to(resolved_project)
        or resolved.is_symlink()
        or not resolved.is_file()
    ):
        return None
    try:
        if resolved.stat().st_size > MAX_EMBED_IMAGE_FILE_SIZE:
            return None
    except OSError:
        return None
    return resolved


def render_loot_markdown(entries: Iterable[Mapping[str, Any]]) -> str:
    blocks: list[str] = []
    for entry in entries:
        entry_id = str(entry.get("id", "")).strip()
        if not entry_id:
            continue
        title = str(entry.get("title", "Untitled loot")).strip() or "Untitled loot"
        entry_type = str(entry.get("type", "note")).strip() or "note"
        timestamp = str(entry.get("timestamp", "")).strip()
        target = str(entry.get("target_ip", "")).strip()
        metadata = [f"- Type: `{entry_type}`"]
        if target:
            metadata.append(f"- Target: `{target}`")
        if timestamp:
            metadata.append(f"- Captured: `{timestamp}`")
        content = str(entry.get("content", "")).rstrip()
        recommendation = str(entry.get("recommendation", "") or "").strip()
        fence = "```"
        while fence in content:
            fence += "`"
        lines = [
            f"<!-- spectrehud-entry:{entry_id} -->",
            f"### {title}",
            *metadata,
            "",
            fence,
            content,
            fence,
        ]
        if recommendation:
            lines.extend(["", "#### Recommendation", "", recommendation])
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


__all__ = ["render_loot_markdown", "safe_attachment_source"]

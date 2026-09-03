"""Crash-recovery draft manager for active box reports.

Atomically maintains a hidden draft snapshot (.report.md.draft) in the active
project directory during editing sessions, allowing seamless recovery after
unexpected terminations (crash, OOM, OS freeze) while cleaning up automatically
on clean save or discard.
"""

from datetime import datetime
import os
from pathlib import Path
import tempfile
from typing import Optional

from core.logger import get_logger

logger = get_logger("draft_manager")

DRAFT_FILENAME = ".report.md.draft"


def get_draft_path(project_dir: Path) -> Path:
    """Returns the path to the draft file within the given project directory."""
    return Path(project_dir) / DRAFT_FILENAME


def save_draft(project_dir: Path, content: str) -> bool:
    """
    Atomically writes the draft content to .report.md.draft in the project dir.
    Returns True if successfully written, False otherwise.
    """
    p_dir = Path(project_dir)
    if not p_dir.exists() or not p_dir.is_dir():
        return False

    draft_path = get_draft_path(p_dir)
    try:
        # Atomic write via tempfile in same directory
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=p_dir,
            delete=False,
            prefix=".draft_tmp_",
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        os.replace(tmp_path, draft_path)
        logger.debug("Draft snapshot updated for %s", p_dir.name)
        return True
    except Exception as exc:
        logger.warning("Failed to write draft snapshot in %s: %s", p_dir, exc)
        return False


def get_draft(project_dir: Path) -> Optional[tuple[str, datetime]]:
    """
    Returns (content, modification_datetime) if a non-empty draft exists, else None.
    """
    draft_path = get_draft_path(project_dir)
    if not draft_path.exists() or not draft_path.is_file():
        return None

    try:
        stat = draft_path.stat()
        if stat.st_size == 0:
            return None
        content = draft_path.read_text(encoding="utf-8")
        mtime = datetime.fromtimestamp(stat.st_mtime)
        return content, mtime
    except Exception as exc:
        logger.warning("Failed to read draft file %s: %s", draft_path, exc)
        return None


def has_recoverable_draft(project_dir: Path, saved_content: str) -> bool:
    """
    Determines whether a draft exists that contains meaningful differences
    from the current saved report on disk.
    """
    result = get_draft(project_dir)
    if result is None:
        return False

    draft_content, _ = result
    # Compare stripped contents so harmless newline/whitespace differences don't trigger prompt
    return draft_content.strip() != (saved_content or "").strip()


def discard_draft(project_dir: Path) -> bool:
    """
    Safely removes the draft file.
    Returns True if a draft was removed, False if no draft existed.
    """
    draft_path = get_draft_path(project_dir)
    try:
        if draft_path.exists():
            draft_path.unlink()
            logger.debug("Draft snapshot discarded for %s", Path(project_dir).name)
            return True
    except Exception as exc:
        logger.warning("Failed to discard draft file %s: %s", draft_path, exc)
    return False

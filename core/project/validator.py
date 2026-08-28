"""
Validation and semantic sanitization for project names and workspace paths.
"""

import re
from pathlib import Path
from typing import Optional, Union

from core.validators import is_windows_reserved_name


class ProjectExistsError(ValueError):
    """Raised when attempting to create a project whose sanitized name already exists."""
    pass


class InvalidProjectNameError(ValueError):
    """Raised when a project name is empty, contains invalid characters, or matches Windows reserved names."""
    pass


class ProjectNotFoundError(KeyError):
    """Raised when attempting to activate a project that does not exist."""
    pass


class ProjectCreationError(RuntimeError):
    """Raised when project workspace creation fails transactionally."""
    pass


class WorkspaceError(RuntimeError):
    """Raised when a workspace directory cannot be created, is inaccessible, or is unwritable."""
    pass


def validate_workspace_directory(path: Union[Path, str]) -> Path:
    """
    Validates that a workspace path is valid, can be created, and is writable.
    Performs an active write probe (.spectrehud_write_test) to fail closed on
    unwritable, read-only, or unavailable paths.
    """
    if not path or not str(path).strip():
        raise WorkspaceError("Workspace directory path cannot be empty.")

    p = Path(path).resolve()
    try:
        p.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        raise WorkspaceError(f"Could not create workspace directory '{p}': {e}") from e

    probe = p / ".spectrehud_write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except (OSError, PermissionError) as e:
        raise WorkspaceError(f"Workspace directory '{p}' is not writable: {e}") from e

    return p


def validate_project_name(name: str) -> str:
    """
    Validates and sanitizes a project name.
    Raises InvalidProjectNameError if the name is empty, contains traversal tokens,
    contains only invalid characters, or matches Windows reserved device names.
    """
    if not name or not str(name).strip():
        raise InvalidProjectNameError("Project name cannot be empty or whitespace only.")

    raw = str(name).strip()

    # Path separators, traversal sequences, or control characters are strictly invalid
    if "/" in raw or "\\" in raw or ".." in raw or re.search(r'[\x00-\x1f\x7f-\x9f]', raw):
        raise InvalidProjectNameError(f"Project name '{name}' contains forbidden characters or sequences.")

    if is_windows_reserved_name(raw):
        raise InvalidProjectNameError(f"Project name '{name}' is a Windows reserved device name.")

    # Replace invalid path characters with underscore (collapsing consecutive invalid chars)
    clean = re.sub(r'[^a-zA-Z0-9_\-\.]+', '_', raw)
    clean = clean.strip("._")

    if not clean or clean in {".", ".."} or not re.match(r'^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$', clean):
        raise InvalidProjectNameError(f"Project name '{name}' contains no valid identifier characters.")

    if is_windows_reserved_name(clean):
        raise InvalidProjectNameError(f"Project name '{name}' resolves to a Windows reserved device name.")

    return clean


def sanitize_project_name(name: str, fallback: str = "Default") -> str:
    """
    Safe sanitization helper for internal lookups.
    Falls back to fallback value if name is invalid.
    """
    try:
        return validate_project_name(name)
    except InvalidProjectNameError:
        return fallback


def validate_workspace_boundary(candidate: Path, base_dir: Path) -> Path:
    """
    Verifies that candidate path resides strictly within base_dir and does not escape via symlink or traversal.
    """
    resolved_cand = candidate.resolve()
    resolved_base = base_dir.resolve()
    if not resolved_cand.is_relative_to(resolved_base) or resolved_cand == resolved_base:
        raise InvalidProjectNameError(
            f"Workspace escape attempt / traversal detected: {candidate} -> {resolved_cand} (outside {resolved_base})"
        )
    return resolved_cand

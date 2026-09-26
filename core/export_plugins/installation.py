"""Platform-aware roots for separately distributed export-plugin bundles."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Iterable, Mapping

from core.platform import plugins_dir


LINUX_SYSTEM_PLUGIN_ROOT = Path("/usr/lib/spectrehud/plugins")


def default_external_export_plugin_roots(
    *,
    system_name: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
    executable: Path | None = None,
    frozen: bool | None = None,
) -> tuple[Path, ...]:
    """Return read-only discovery roots without creating or modifying them."""
    system = (system_name or platform.system()).strip().lower()
    environment = os.environ if environ is None else environ
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    executable_path = Path(sys.executable) if executable is None else Path(executable)
    roots: list[Path] = []
    if system == "windows" and is_frozen:
        roots.append(executable_path.resolve().parent / "plugins")
    elif system == "linux":
        roots.append(LINUX_SYSTEM_PLUGIN_ROOT)
    roots.append(plugins_dir(system_name=system, environ=environment, home=home))
    return _deduplicated(roots)


def _deduplicated(paths: Iterable[Path]) -> tuple[Path, ...]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            result.append(path)
    return tuple(result)


__all__ = ["LINUX_SYSTEM_PLUGIN_ROOT", "default_external_export_plugin_roots"]

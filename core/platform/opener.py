"""Cross-platform opening of existing local files and directories through Qt."""

from os import PathLike
from pathlib import Path
from typing import Union


LocalPath = Union[str, PathLike[str]]


def open_path(path: LocalPath) -> bool:
    """Open an existing local path with the desktop default application."""
    try:
        target = Path(path).expanduser()
        if not target.exists():
            return False
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        url = QUrl.fromLocalFile(str(target.resolve()))
        return bool(QDesktopServices.openUrl(url))
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        return False

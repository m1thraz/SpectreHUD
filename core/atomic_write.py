import os
import json
import uuid
from pathlib import Path
from typing import Any, Union


def _secure_chmod(path: Path, mode: int = 0o600) -> None:
    """Sets restrictive file permissions (0o600) on POSIX systems; safe fallback on Windows."""
    try:
        if os.name == 'posix':
            os.chmod(path, mode)
    except (OSError, NotImplementedError):
        pass


def atomic_write_text(filepath: Union[str, Path], content: str, encoding: str = "utf-8") -> bool:
    """
    Atomically writes text to target filepath via a temporary file in the same directory,
    using flush, fsync, atomic rename (os.replace), and restrictive permissions (0o600).
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_name(f".{path.name}.tmp_{uuid.uuid4().hex[:8]}")
    try:
        with open(temp_path, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        _secure_chmod(temp_path, 0o600)
        os.replace(temp_path, path)
        _secure_chmod(path, 0o600)
        return True
    except OSError as e:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise e


def atomic_write_json(filepath: Union[str, Path], data: Any, indent: int = 2, ensure_ascii: bool = False) -> bool:
    """
    Atomically writes data as formatted JSON to target filepath with restrictive permissions (0o600).
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_name(f".{path.name}.tmp_{uuid.uuid4().hex[:8]}")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
            f.flush()
            os.fsync(f.fileno())
        _secure_chmod(temp_path, 0o600)
        os.replace(temp_path, path)
        _secure_chmod(path, 0o600)
        return True
    except (OSError, TypeError, ValueError) as e:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise e

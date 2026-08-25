import os
import json
import uuid
from pathlib import Path
from typing import Any, Union


def atomic_write_text(filepath: Union[str, Path], content: str, encoding: str = "utf-8") -> bool:
    """
    Atomically writes text to target filepath via a temporary file in the same directory,
    using flush, fsync, and atomic rename (os.replace) to prevent file corruption.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_name(f".{path.name}.tmp_{uuid.uuid4().hex[:8]}")
    try:
        with open(temp_path, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
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
    Atomically writes data as formatted JSON to target filepath.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_name(f".{path.name}.tmp_{uuid.uuid4().hex[:8]}")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
        return True
    except (OSError, TypeError, ValueError) as e:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise e

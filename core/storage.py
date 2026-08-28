"""
Storage Abstraction Layer for SpectreHUD.

Decouples core domain services (LootManager, ClipboardWatcher, ConfigManager, etc.)
from physical disk I/O, allowing pure in-memory execution, mock testing,
and safe atomic file persistence.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, Union
from pathlib import Path
import json
import copy
import threading

from core.atomic_write import atomic_write_json
from core.validators import is_file_size_valid
from core.logger import get_logger

logger = get_logger("storage")

MAX_DEFAULT_STORAGE_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class StorageError(Exception):
    """Base exception for all storage layer errors."""
    pass


class PersistenceError(StorageError, RuntimeError):
    """Raised when data persistence to the underlying storage backend fails."""
    pass


class StorageBackend(ABC):
    """Abstract base interface for data storage backends."""

    @abstractmethod
    def load_json(self, resource_name: str) -> Optional[Any]:
        """Loads and parses JSON data by resource name/key. Returns None if not found."""
        pass

    @abstractmethod
    def save_json(self, resource_name: str, data: Any) -> bool:
        """Persists JSON data by resource name/key. Returns True on success."""
        pass

    @abstractmethod
    def exists(self, resource_name: str) -> bool:
        """Checks if a resource exists in storage."""
        pass

    @abstractmethod
    def delete(self, resource_name: str) -> bool:
        """Deletes a resource from storage."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Wipes all stored resources."""
        pass


class InMemoryStorageBackend(StorageBackend):
    """
    Pure In-Memory storage backend with zero filesystem I/O.
    Thread-safe and ideal for unit testing, isolated sessions, and headless execution.
    """

    def __init__(self, initial_data: Optional[Dict[str, Any]] = None, deep_copy: bool = True):
        self._deep_copy = deep_copy
        self._lock = threading.RLock()
        self._store: Dict[str, Any] = {}
        if initial_data:
            with self._lock:
                for k, v in initial_data.items():
                    self._store[str(k)] = copy.deepcopy(v) if self._deep_copy else v

    def load_json(self, resource_name: str) -> Optional[Any]:
        with self._lock:
            key = str(resource_name)
            if key not in self._store:
                return None
            val = self._store[key]
            return copy.deepcopy(val) if self._deep_copy else val

    def save_json(self, resource_name: str, data: Any) -> bool:
        with self._lock:
            key = str(resource_name)
            self._store[key] = copy.deepcopy(data) if self._deep_copy else data
            return True

    def exists(self, resource_name: str) -> bool:
        with self._lock:
            return str(resource_name) in self._store

    def delete(self, resource_name: str) -> bool:
        with self._lock:
            key = str(resource_name)
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def get_all_keys(self) -> list:
        with self._lock:
            return list(self._store.keys())


class FileStorageBackend(StorageBackend):
    """
    Filesystem-backed JSON storage.
    Supports either a directory containing named JSON files (e.g. base_dir / '{name}.json')
    or a dedicated single file path.
    Enforces atomic write replacements and file size limits.
    """

    def __init__(
        self,
        base_dir: Optional[Union[Path, str]] = None,
        single_file_path: Optional[Union[Path, str]] = None,
        max_file_size: int = MAX_DEFAULT_STORAGE_FILE_SIZE
    ):
        self.max_file_size = max_file_size
        self._lock = threading.RLock()

        if single_file_path is not None:
            self.single_file_path = Path(single_file_path)
            self.base_dir = self.single_file_path.parent
        elif base_dir is not None:
            self.base_dir = Path(base_dir)
            self.single_file_path = None
        else:
            raise ValueError("FileStorageBackend requires either base_dir or single_file_path.")

        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create storage directory {self.base_dir}: {e}", exc_info=True)

    def _resolve_path(self, resource_name: str) -> Path:
        if self.single_file_path is not None:
            return self.single_file_path
        if not resource_name or not str(resource_name).strip():
            raise ValueError("Resource name cannot be empty.")
        raw = str(resource_name).strip()
        if "/" in raw or "\\" in raw or ".." in raw or Path(raw).name != raw:
            raise ValueError(f"Invalid resource name containing path traversal components: {resource_name!r}")
        sanitized_name = raw
        if not sanitized_name.endswith(".json"):
            sanitized_name += ".json"
        return self.base_dir / sanitized_name

    def load_json(self, resource_name: str) -> Optional[Any]:
        target = self._resolve_path(resource_name)
        with self._lock:
            if not target.exists():
                return None

            from core.validators import is_file_size_valid
            if not is_file_size_valid(target, self.max_file_size):
                logger.error(
                    f"Storage file {target} exceeds maximum size limit of {self.max_file_size} bytes. Rejecting oversized file."
                )
                return None

            try:
                with open(target, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, RecursionError) as e:
                logger.error(f"Corrupted JSON in storage file at {target}: {e}")
                return None
            except (OSError, UnicodeDecodeError) as e:
                logger.error(f"Error reading storage file {target}: {e}")
                return None

    def save_json(self, resource_name: str, data: Any) -> bool:
        target = self._resolve_path(resource_name)
        with self._lock:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_json(target, data, indent=2, ensure_ascii=False)
                return True
            except OSError as e:
                logger.error(f"OS error saving storage file to {target}: {e}", exc_info=True)
                return False
            except (TypeError, ValueError) as e:
                logger.error(f"JSON serialization error saving storage file to {target}: {e}")
                return False

    def exists(self, resource_name: str) -> bool:
        target = self._resolve_path(resource_name)
        with self._lock:
            return target.exists()

    def delete(self, resource_name: str) -> bool:
        target = self._resolve_path(resource_name)
        with self._lock:
            if target.exists():
                try:
                    target.unlink()
                    return True
                except OSError as e:
                    logger.error(f"Failed to delete storage file {target}: {e}")
                    return False
            return False

    def clear(self) -> None:
        with self._lock:
            if self.single_file_path:
                self.delete(str(self.single_file_path))
            else:
                for json_file in self.base_dir.glob("*.json"):
                    try:
                        json_file.unlink()
                    except OSError as e:
                        logger.error(f"Failed to delete file {json_file} during clear: {e}")

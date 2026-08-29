"""In-memory session keys for encrypted Pentest-Mode projects."""

from typing import Optional


class ProjectLockedError(Exception):
    """Raised when encrypted state is accessed before its project is unlocked."""


class ProjectSecurityMetaError(Exception):
    """Raised when a project's unencrypted security metadata is invalid."""


class ProjectLockService:
    """Keeps at most the active project's derived key in process memory only."""

    def __init__(self) -> None:
        self._project_name: Optional[str] = None
        self._session_key: Optional[bytes] = None

    def set_session_key(self, project_name: str, key: bytes) -> None:
        if not isinstance(key, bytes):
            raise TypeError("Project session keys must be bytes.")
        self._project_name = project_name
        self._session_key = key

    def get_session_key(self, project_name: str) -> Optional[bytes]:
        return self._session_key if self._project_name == project_name else None

    def is_unlocked(self, project_name: str) -> bool:
        return self.get_session_key(project_name) is not None

    def clear(self) -> None:
        # Python cannot reliably guarantee zeroisation of immutable bytes.  We
        # deliberately drop the sole application reference on switch/shutdown.
        self._project_name = None
        self._session_key = None

    def retain_only(self, project_name: str) -> None:
        if self._project_name != project_name:
            self.clear()

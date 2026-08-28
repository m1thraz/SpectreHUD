"""Application-wide single-instance coordination."""

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QLockFile

from core.config import get_default_config_dir


LOCK_FILENAME = "spectrehud.lock"
STALE_LOCK_TIME_MS = 30_000


class ApplicationLockError(RuntimeError):
    """Raised when SpectreHUD cannot create or access its application lock."""


def acquire_application_lock(config_dir: Optional[Path] = None) -> Optional[QLockFile]:
    """Atomically acquires SpectreHUD's process-wide lock, if available.

    ``QLockFile`` records the owning process and detects locks left behind by a
    crashed process after the configured stale period.  The returned lock must
    stay alive until shutdown and then be released with
    :func:`release_application_lock`.
    """
    lock_dir = Path(config_dir) if config_dir is not None else get_default_config_dir()
    try:
        lock_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ApplicationLockError(
            f"Das Konfigurationsverzeichnis für den Single-Instance-Lock konnte nicht erstellt werden: {lock_dir}"
        ) from exc

    lock = QLockFile(str(lock_dir / LOCK_FILENAME))
    lock.setStaleLockTime(STALE_LOCK_TIME_MS)
    if lock.tryLock(0):
        return lock
    # On Windows, explicitly closing a failed QLockFile attempt prevents its
    # transient file handle from keeping a live owner's lock file undeletable.
    error = lock.error()
    lock.unlock()
    if error != QLockFile.LockError.LockFailedError:
        raise ApplicationLockError(
            f"Der Single-Instance-Lock konnte nicht angelegt werden ({error.name})."
        )
    return None


def release_application_lock(lock: Optional[QLockFile]) -> None:
    """Releases a previously acquired application lock without masking shutdown."""
    if lock is not None and lock.isLocked():
        lock.unlock()

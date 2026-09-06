"""Application-wide single-instance coordination."""

import hashlib
import sys
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QLockFile
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from core.config import get_default_config_dir


LOCK_FILENAME = "spectrehud.lock"
STALE_LOCK_TIME_MS = 30_000


class ApplicationLockError(RuntimeError):
    """Raised when SpectreHUD cannot create or access its application lock."""


def get_ipc_server_name(config_dir: Optional[Path] = None) -> str:
    """Returns a deterministic local server name scoped to the user and config dir."""
    c_dir = Path(config_dir) if config_dir is not None else get_default_config_dir()
    norm_path = str(c_dir.resolve()).lower()
    path_hash = hashlib.sha256(norm_path.encode("utf-8")).hexdigest()[:12]
    return f"spectrehud_ipc_{path_hash}"


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


def start_single_instance_server(
    on_activate: Callable[[], None],
    config_dir: Optional[Path] = None,
) -> Optional[QLocalServer]:
    """Starts the local IPC server listening for activation signals from secondary instances."""
    server_name = get_ipc_server_name(config_dir)
    QLocalServer.removeServer(server_name)

    server = QLocalServer()

    def _handle_connection() -> None:
        client_socket = server.nextPendingConnection()
        if client_socket is not None:
            try:
                on_activate()
            finally:
                client_socket.disconnectFromServer()

    server.newConnection.connect(_handle_connection)
    if server.listen(server_name):
        return server
    return None


def notify_running_instance(
    message: str = "ACTIVATE",
    config_dir: Optional[Path] = None,
    timeout_ms: int = 1500,
) -> bool:
    """Notifies the already running SpectreHUD instance to bring its window to the foreground.

    Returns True if the running instance was contacted and signaled successfully.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            # ASFW_ANY (-1) permits the target process to set the foreground window
            ctypes.windll.user32.AllowSetForegroundWindow(-1)
        except Exception:
            pass

    server_name = get_ipc_server_name(config_dir)
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(timeout_ms):
        return False

    try:
        socket.write(message.encode("utf-8") + b"\n")
        socket.waitForBytesWritten(timeout_ms)
        socket.disconnectFromServer()
        return True
    except Exception:
        return False

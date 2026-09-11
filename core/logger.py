"""
Structured, Hierarchical Logging System for SpectreHUD.

Provides rotating file logging, console streaming, environment-based log levels,
and clean namespace resolution for all core modules and UI components.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from core.platform import logs_dir as platform_logs_dir

DEFAULT_MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB per log file
DEFAULT_LOG_BACKUP_COUNT = 3  # 3 rotated backups (spectrehud.log.1, .2, .3)

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _resolve_default_log_level() -> int:
    """Reads SPECTRE_LOG_LEVEL environment variable or defaults to INFO."""
    env_level = os.environ.get("SPECTRE_LOG_LEVEL", "").strip().upper()
    return _LEVEL_MAP.get(env_level, logging.INFO)


_file_logging_configured = False
_active_log_path: Optional[Path] = None


def get_log_directory() -> Path:
    """Return the configured diagnostics directory or the current platform default."""
    return _active_log_path.parent if _active_log_path is not None else platform_logs_dir()


def get_log_path() -> Path:
    """Return the active or expected rotating log-file path."""
    return _active_log_path or (get_log_directory() / "spectrehud.log")


def is_file_logging_configured() -> bool:
    return _file_logging_configured


@dataclass(frozen=True)
class LogDiagnostics:
    """Public summary of logging state for user diagnostics and error dialogs."""

    path: Path
    is_active: bool


def get_log_diagnostics() -> LogDiagnostics:
    """Return diagnostic information about file logging without leaking internal configuration state."""
    return LogDiagnostics(path=get_log_path(), is_active=_file_logging_configured)


def configure_file_logging(
    log_dir: Optional[Path] = None,
    max_bytes: int = DEFAULT_MAX_LOG_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> Optional[Path]:
    """Explicitly configures rotating file logging during application bootstrap."""
    global _active_log_path, _file_logging_configured
    if _file_logging_configured:
        return _active_log_path

    root_logger = logging.getLogger("spectrehud")
    if root_logger.level == logging.NOTSET:
        root_logger.setLevel(_resolve_default_log_level())
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    try:
        resolved_log_dir = Path(log_dir) if log_dir else platform_logs_dir()
        resolved_log_dir.mkdir(parents=True, exist_ok=True)
        log_file = resolved_log_dir / "spectrehud.log"
        file_handler = RotatingFileHandler(
            str(log_file), maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        _file_logging_configured = True
        _active_log_path = log_file.resolve()
        root_logger.info("File logging active: %s", _active_log_path)
        return _active_log_path
    except (OSError, PermissionError) as e:
        _active_log_path = None
        sys.stderr.write(f"Warning: Could not configure file logging: {e}\n")
        return None


def setup_logger(
    name: str = "spectrehud",
    level: Optional[Union[int, str]] = None,
    max_bytes: int = DEFAULT_MAX_LOG_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> logging.Logger:
    """Configures and returns a structured logger for SpectreHUD with console streaming."""
    logger = logging.getLogger(name)
    resolved_level = (
        _LEVEL_MAP.get(str(level).upper(), logging.INFO)
        if isinstance(level, str)
        else (level if level is not None else _resolve_default_log_level())
    )
    logger.setLevel(resolved_level)

    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(module_name: Optional[str] = None) -> logging.Logger:
    """
    Returns a structured logger hierarchically namespaced under 'spectrehud'.
    Handles __name__ (e.g. 'core.loot.manager' -> 'spectrehud.core.loot.manager')
    and short tags (e.g. 'loot' -> 'spectrehud.loot') without duplication.
    """
    base = setup_logger("spectrehud")
    if not module_name:
        return base

    clean_name = str(module_name).strip()
    if clean_name.startswith("spectrehud."):
        full_name = clean_name
    elif clean_name == "spectrehud":
        return base
    else:
        full_name = f"spectrehud.{clean_name}"

    return logging.getLogger(full_name)


def set_log_level(level: Union[int, str]) -> None:
    """Sets the logging level for all spectrehud loggers."""
    resolved = _LEVEL_MAP.get(str(level).upper(), level) if isinstance(level, str) else level
    root = logging.getLogger("spectrehud")
    root.setLevel(resolved)
    for handler in root.handlers:
        handler.setLevel(resolved)


def flush_logs() -> None:
    """Flushes all handlers for the root spectrehud logger."""
    root = logging.getLogger("spectrehud")
    for handler in root.handlers:
        try:
            handler.flush()
        except Exception:
            pass


def close_log_handlers() -> None:
    """Closes and removes all handlers (file and stream) to release file locks on Windows."""
    global _active_log_path, _file_logging_configured
    root = logging.getLogger("spectrehud")
    for handler in list(root.handlers):
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        root.removeHandler(handler)
    _file_logging_configured = False
    _active_log_path = None

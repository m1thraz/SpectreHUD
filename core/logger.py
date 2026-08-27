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
from logging.handlers import RotatingFileHandler

DEFAULT_MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB per log file
DEFAULT_LOG_BACKUP_COUNT = 3             # 3 rotated backups (spectrehud.log.1, .2, .3)

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}


def _resolve_default_log_level() -> int:
    """Reads SPECTRE_LOG_LEVEL environment variable or defaults to INFO."""
    env_level = os.environ.get("SPECTRE_LOG_LEVEL", "").strip().upper()
    return _LEVEL_MAP.get(env_level, logging.INFO)


def setup_logger(
    name: str = "spectrehud", 
    level: Optional[Union[int, str]] = None,
    max_bytes: int = DEFAULT_MAX_LOG_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT
) -> logging.Logger:
    """Configures and returns a structured, rotating file logger for SpectreHUD."""
    logger = logging.getLogger(name)
    resolved_level = (
        _LEVEL_MAP.get(str(level).upper(), logging.INFO) if isinstance(level, str)
        else (level if level is not None else _resolve_default_log_level())
    )
    
    if logger.handlers:
        logger.setLevel(resolved_level)
        return logger

    logger.setLevel(resolved_level)

    # Formatter
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler in config dir
    try:
        env_dir = os.environ.get("SPECTRE_CONFIG_DIR")
        log_dir = Path(env_dir) if env_dir else Path.home() / ".ctf_cheatsheet_widget"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "spectrehud.log"
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        sys.stderr.write(f"Warning: Could not configure file logging: {e}\n")

    return logger


def get_logger(module_name: Optional[str] = None) -> logging.Logger:
    """
    Returns a structured logger hierarchically namespaced under 'spectrehud'.
    Handles __name__ (e.g. 'core.loot_manager' -> 'spectrehud.core.loot_manager')
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

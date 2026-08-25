import logging
import os
import sys
from pathlib import Path
from typing import Optional

def setup_logger(name: str = "spectrehud", level: int = logging.INFO) -> logging.Logger:
    """Configures and returns a structured logger for SpectreHUD."""
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger

    logger.setLevel(level)

    # Formatter
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optional File Handler in config dir
    try:
        env_dir = os.environ.get("SPECTRE_CONFIG_DIR")
        log_dir = Path(env_dir) if env_dir else Path.home() / ".ctf_cheatsheet_widget"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "spectrehud.log"
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        sys.stderr.write(f"Warning: Could not configure file logging: {e}\n")

    return logger

def get_logger(module_name: Optional[str] = None) -> logging.Logger:
    """Returns a logger namespaced under spectrehud."""
    base = setup_logger("spectrehud")
    if module_name:
        return logging.getLogger(f"spectrehud.{module_name}")
    return base

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from core.logger import get_logger

logger = get_logger("config")

DEFAULT_CONFIG: Dict[str, Any] = {
    "target_ip": "10.10.10.10",
    "attacker_ip": "10.10.14.5",
    "port": "4444",
    "username": "",
    "password": "",
    "wordlist": "/usr/share/wordlists/dirb/common.txt",
    "hotkey": "<ctrl>+<cmd>+<",
    "auto_hide_on_copy": False,
    "always_on_top": True,
    "theme": "cyber_dark",
    "language": "en",
    "workspace_dir": str(Path.home() / "spectre_projects")
}

def get_default_config_dir() -> Path:
    """Returns the default config directory, checking SPECTRE_CONFIG_DIR env var first."""
    env_dir = os.environ.get("SPECTRE_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".ctf_cheatsheet_widget"

class ConfigManager:
    """Manages application configuration, user state, and preferences with full path parameterization."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = get_default_config_dir()
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.json"
        self.user_snippets_file = self.config_dir / "user_snippets.json"
        
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create config directory {self.config_dir}: {e}", exc_info=True)

        self.session_param_cache: Dict[str, str] = {}
        self.data = self.load_config()

    def get_cached_param(self, param_name: str, fallback: str = "") -> str:
        """Returns session cached value for a custom parameter."""
        return self.session_param_cache.get(param_name.upper(), fallback)

    def set_cached_param(self, param_name: str, value: str) -> None:
        """Saves custom parameter value into session memory."""
        if value:
            self.session_param_cache[param_name.upper()] = value

    def load_config(self) -> Dict[str, Any]:
        if self.config_file.exists():
            from core.validators import is_file_size_valid, MAX_CONFIG_FILE_SIZE
            if not is_file_size_valid(self.config_file, MAX_CONFIG_FILE_SIZE):
                logger.error(f"Config file {self.config_file} exceeds maximum size limit of {MAX_CONFIG_FILE_SIZE} bytes. Using defaults.")
            else:
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if not isinstance(loaded, dict):
                            logger.warning(f"Expected dict in config JSON at {self.config_file}, got {type(loaded).__name__}. Falling back to default configuration.")
                            loaded = {}
                        # Migrate old Ctrl+Shift+C hotkey to the new Strg+Super+<
                        if loaded.get("hotkey") in ["<ctrl>+<shift>+c", "ctrl+shift+c", "<ctrl>+<shift>+C", None]:
                            loaded["hotkey"] = "<ctrl>+<cmd>+<"
                        cfg = DEFAULT_CONFIG.copy()
                        cfg.update(loaded)
                        self.data = cfg
                        self.save_config()
                        return cfg
                except (json.JSONDecodeError, RecursionError) as e:
                    logger.error(f"Corrupted config JSON at {self.config_file}: {e}. Falling back to default configuration.")
                except (OSError, UnicodeDecodeError, KeyError, AttributeError) as e:
                    logger.error(f"Error reading config from {self.config_file}: {e}. Using defaults.")
        
        cfg = DEFAULT_CONFIG.copy()
        self.data = cfg
        self.save_config()
        return cfg

    def save_config(self) -> None:
        from core.atomic_write import atomic_write_json
        try:
            atomic_write_json(self.config_file, self.data, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"OS error saving config to {self.config_file}: {e}", exc_info=True)
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization error saving config to {self.config_file}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save_config()

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from core.logger import get_logger
from core.storage import StorageBackend, InMemoryStorageBackend, FileStorageBackend, PersistenceError

logger = get_logger("config")

DEFAULT_CONFIG: Dict[str, Any] = {
    "target_ip": "10.10.10.10",
    "attacker_ip": "10.10.14.5",
    "port": "4444",
    "username": "",
    "password": "",
    "wordlist": "/usr/share/wordlists/dirb/common.txt",
    "hotkey": "<ctrl>+<cmd>+<",
    "snip_hotkey": "<ctrl>+<cmd>+x",
    "quit_hotkey": "<ctrl>+<cmd>+q",
    "auto_hide_on_copy": False,
    "always_on_top": True,
    "loot_view_mode": "list",
    "ui_font": "segoe_ui",
    "code_font": "consolas",
    "report_font": "segoe_ui",
    "theme": "cyber_dark",
    "language": "en",
    "time_format": "24h",
    "workspace_dir": str(Path.home() / "spectre_projects"),
    "obsidian_vault_path": "",
    "obsidian_export_folder": "CTF/SpectreHUD",
    "obsidian_open_after_export": False,
}

def get_default_config_dir() -> Path:
    """Returns the default config directory, checking SPECTRE_CONFIG_DIR env var first."""
    env_dir = os.environ.get("SPECTRE_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".ctf_cheatsheet_widget"

class ConfigManager:
    """Manages application configuration, user state, and preferences with full path parameterization."""
    
    def __init__(self, config_dir: Optional[Path] = None, storage: Optional[StorageBackend] = None):
        if storage is not None:
            self.storage = storage
            self.config_dir = getattr(storage, "base_dir", get_default_config_dir())
        elif config_dir is not None:
            self.config_dir = Path(config_dir)
            self.storage = FileStorageBackend(base_dir=self.config_dir)
        else:
            self.config_dir = get_default_config_dir()
            self.storage = FileStorageBackend(base_dir=self.config_dir)

        self.config_file = self.config_dir / "config.json"
        self.user_snippets_file = self.config_dir / "user_snippets.json"

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
        loaded = self.storage.load_json("config")
        if isinstance(loaded, dict):
            migrated = False
            # Migrate old Ctrl+Shift+C hotkey to the new Strg+Super+<
            if loaded.get("hotkey") in ["<ctrl>+<shift>+c", "ctrl+shift+c", "<ctrl>+<shift>+C", None]:
                loaded["hotkey"] = "<ctrl>+<cmd>+<"
                migrated = True
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(loaded)
            self.data = cfg
            if migrated:
                try:
                    self.save_config()
                except PersistenceError:
                    pass
            return cfg
        
        cfg = DEFAULT_CONFIG.copy()
        self.data = cfg
        try:
            self.save_config()
        except PersistenceError:
            pass
        return cfg

    def save_config(self) -> None:
        if not self.storage.save_json("config", self.data):
            raise PersistenceError("Could not persist configuration to storage.")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        new_data = dict(self.data)
        new_data[key] = value
        if not self.storage.save_json("config", new_data):
            raise PersistenceError(f"Could not persist config key '{key}' to storage.")
        self.data = new_data

    def update(self, values: Dict[str, Any]) -> None:
        """Batch updates multiple configuration values in a single atomic storage write."""
        if not values:
            return
        new_data = dict(self.data)
        new_data.update(values)
        if not self.storage.save_json("config", new_data):
            raise PersistenceError("Could not persist batch configuration update to storage.")
        self.data = new_data

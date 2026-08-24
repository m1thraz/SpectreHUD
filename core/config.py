import json
import os
from pathlib import Path
from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
    "target_ip": "10.10.10.10",
    "attacker_ip": "10.10.14.5",
    "port": "4444",
    "wordlist": "/usr/share/wordlists/dirb/common.txt",
    "hotkey": "<ctrl>+<cmd>+<",
    "auto_hide_on_copy": False,
    "always_on_top": True,
    "theme": "cyber_dark"
}

class ConfigManager:
    """Manages application configuration, user state, and preferences."""
    
    def __init__(self, config_dir: Path = None):
        if config_dir is None:
            config_dir = Path.home() / ".ctf_cheatsheet_widget"
        self.config_dir = config_dir
        self.config_file = self.config_dir / "config.json"
        self.user_snippets_file = self.config_dir / "user_snippets.json"
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
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
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Migrate old Ctrl+Shift+C hotkey to the new Strg+Super+<
                    if loaded.get("hotkey") in ["<ctrl>+<shift>+c", "ctrl+shift+c", "<ctrl>+<shift>+C", None]:
                        loaded["hotkey"] = "<ctrl>+<cmd>+<"
                    cfg = DEFAULT_CONFIG.copy()
                    cfg.update(loaded)
                    self.data = cfg
                    self.save_config()
                    return cfg
            except Exception as e:
                print(f"Error loading config: {e}. Using defaults.")
        cfg = DEFAULT_CONFIG.copy()
        self.data = cfg
        self.save_config()
        return cfg

    def save_config(self) -> None:
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save_config()

"""
Internationalization (i18n) Engine for SpectreHUD.

Loads translations from JSON locale files (data/i18n/*.json) with fallback handling,
dynamic locale switching, and parameter interpolation.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal

from core.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_LOCALES: Dict[str, str] = {"de": "Deutsch", "en": "English"}

DEFAULT_LOCALE = "en"


def get_locales_dir() -> Path:
    """Resolves the directory containing translation JSON files (data/i18n)."""
    # 1. PyInstaller bundled path
    if hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "data" / "i18n"
        if bundled.exists():
            return bundled

    # 2. Workspace root relative path
    module_dir = Path(__file__).resolve().parent
    workspace_data = module_dir.parent / "data" / "i18n"
    if workspace_data.exists():
        return workspace_data

    # 3. Fallback to data/ in parent
    return module_dir.parent / "data" / "i18n"


def load_locale_file(locale_code: str, locales_dir: Optional[Path] = None) -> Dict[str, str]:
    """Loads a single locale JSON file (e.g. de.json or en.json)."""
    target_dir = locales_dir or get_locales_dir()
    json_path = target_dir / f"{locale_code}.json"
    if not json_path.exists() or not json_path.is_file():
        logger.warning(f"Translation file not found: {json_path}")
        return {}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load translation file {json_path}: {e}")

    return {}


def load_all_translations(locales_dir: Optional[Path] = None) -> Dict[str, Dict[str, str]]:
    """Loads all available locale JSON files from the locales directory."""
    target_dir = locales_dir or get_locales_dir()
    translations: Dict[str, Dict[str, str]] = {}

    for code in SUPPORTED_LOCALES.keys():
        translations[code] = load_locale_file(code, target_dir)

    # If any other *.json exists in data/i18n (e.g. user-added fr.json), load them too
    if target_dir.exists():
        for f in target_dir.glob("*.json"):
            code = f.stem.lower()
            if code not in translations:
                translations[code] = load_locale_file(code, target_dir)

    return translations


class I18nManager(QObject):
    """
    Central Internationalization (i18n) Manager for SpectreHUD.
    Provides reactive translation lookup, fallback handling, and runtime locale switching.
    """

    locale_changed = pyqtSignal(str)

    def __init__(self, default_locale: str = DEFAULT_LOCALE, locales_dir: Optional[Path] = None):
        super().__init__()
        self.locales_dir = locales_dir or get_locales_dir()
        self._current_locale = (
            default_locale if default_locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
        )
        self._translations: Dict[str, Dict[str, str]] = {}
        self.reload_translations()

    def reload_translations(self) -> None:
        """Reloads all translation dictionaries from disk."""
        self._translations = load_all_translations(self.locales_dir)

    @property
    def current_locale(self) -> str:
        return self._current_locale

    def set_locale(self, locale_code: str) -> None:
        clean = str(locale_code).lower().strip()
        if clean in SUPPORTED_LOCALES and clean != self._current_locale:
            self._current_locale = clean
            lang_name = SUPPORTED_LOCALES.get(clean, clean)
            logger.info(f"Language changed to: {lang_name} ({clean})")
            self.locale_changed.emit(clean)

    def t(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        """
        Translates a key for the current locale with fallback to German or key itself.
        Supports parameter interpolation with kwargs.
        """
        loc_dict = self._translations.get(self._current_locale, {})
        text = loc_dict.get(key)

        if text is None:
            # Fallback to German
            text = self._translations.get("de", {}).get(key)

        if text is None:
            # Fallback to provided default or raw key
            text = default if default is not None else key

        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError, IndexError) as e:
                logger.warning(f"Failed to format translation string for key '{key}': {e}")
                return text

        return text


# Global singleton instance
_i18n_instance: Optional[I18nManager] = None


def get_i18n() -> I18nManager:
    """Returns the global i18n manager instance, ensuring it is always a valid live QObject."""
    global _i18n_instance
    if _i18n_instance is not None:
        try:
            _ = _i18n_instance.locale_changed
        except (RuntimeError, AttributeError):
            _i18n_instance = None

    if _i18n_instance is None:
        _i18n_instance = I18nManager()
    return _i18n_instance


def t(key: str, default: Optional[str] = None, **kwargs) -> str:
    """Convenience global translation function."""
    return get_i18n().t(key, default=default, **kwargs)


def set_locale(locale_code: str) -> None:
    """Sets the global active locale."""
    get_i18n().set_locale(locale_code)


def get_locale() -> str:
    """Returns the current active locale code."""
    return get_i18n().current_locale

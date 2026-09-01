"""Discovery, validation, and loading for built-in and user themes."""

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Set

from core.logger import get_logger
from ui.styles.palette import CYBER_DARK_PALETTE

logger = get_logger(__name__)


class ThemeLoader:
    """Loads complete theme palettes and falls back safely to Cyber Dark."""

    BUILTIN_THEMES_DIR = Path(__file__).resolve().parent.parent / "data" / "themes"
    USER_THEMES_DIR = Path.home() / ".config" / "spectrehud" / "themes"
    FALLBACK_THEME_ID = "cyber_dark"

    def get_required_tokens(self) -> Set[str]:
        return set(CYBER_DARK_PALETTE)

    def validate_palette(self, palette: Mapping[str, Any]) -> List[str]:
        """Return required tokens that are absent or do not contain string values."""
        if not isinstance(palette, Mapping):
            return sorted(self.get_required_tokens())
        return sorted(
            token
            for token in self.get_required_tokens()
            if not isinstance(palette.get(token), str) or not str(palette[token]).strip()
        )

    @staticmethod
    def _read_definition(path: Path) -> Dict[str, Any] | None:
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            logger.warning("Ignoring unreadable theme file %s: %s", path, exc)
            return None
        if not isinstance(data, dict):
            logger.warning("Ignoring theme file with invalid root object: %s", path)
            return None
        return data

    def _theme_files(self) -> List[Path]:
        files: List[Path] = []
        for directory in (self.BUILTIN_THEMES_DIR, self.USER_THEMES_DIR):
            try:
                if directory.is_dir():
                    files.extend(sorted(directory.glob("*.json")))
            except OSError as exc:
                logger.warning("Could not inspect theme directory %s: %s", directory, exc)
        return files

    def list_themes(self) -> List[Dict[str, str]]:
        """Return valid themes for the settings dropdown, de-duplicated by id."""
        themes: Dict[str, Dict[str, str]] = {}
        for path in self._theme_files():
            definition = self._read_definition(path)
            if not definition:
                continue
            theme_id = definition.get("id")
            palette = definition.get("palette")
            if (
                not isinstance(theme_id, str)
                or not theme_id.strip()
                or self.validate_palette(palette)
            ):
                logger.warning("Ignoring invalid or incomplete theme definition: %s", path)
                continue
            themes.setdefault(
                theme_id,
                {
                    "id": theme_id,
                    "name": str(definition.get("name") or theme_id),
                    "author": str(definition.get("author") or "Unknown"),
                    "version": str(definition.get("version") or "1.0"),
                },
            )
        if self.FALLBACK_THEME_ID not in themes:
            themes[self.FALLBACK_THEME_ID] = {
                "id": self.FALLBACK_THEME_ID,
                "name": "Cyber Dark",
                "author": "SpectreHUD",
                "version": "1.0",
            }
        return sorted(themes.values(), key=lambda theme: theme["name"].casefold())

    def load_theme(self, theme_id: str) -> Dict[str, str]:
        """Load a complete palette, falling back to the built-in palette on any error."""
        selected_id = str(theme_id or self.FALLBACK_THEME_ID).strip()
        if selected_id == self.FALLBACK_THEME_ID:
            search_files = [self.BUILTIN_THEMES_DIR / "cyber_dark.json"]
        else:
            search_files = self._theme_files()
        for path in search_files:
            definition = self._read_definition(path)
            if not definition or definition.get("id") != selected_id:
                continue
            palette = definition.get("palette")
            missing = self.validate_palette(palette)
            if not missing:
                return {token: str(palette[token]) for token in self.get_required_tokens()}
            logger.warning(
                "Theme '%s' is missing required tokens: %s", selected_id, ", ".join(missing)
            )
            break
        if selected_id != self.FALLBACK_THEME_ID:
            logger.warning("Theme '%s' could not be loaded; using Cyber Dark.", selected_id)
        return dict(CYBER_DARK_PALETTE)

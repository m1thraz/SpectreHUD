"""
Icon creation utilities using qtawesome for SpectreHUD.

Provides a unified helper for building theme-consistent QIcons across
platforms and components.
"""

from typing import Mapping, Optional
from PyQt6.QtGui import QIcon
import qtawesome as qta

from ui.styles.palette import (
    BG_DARK,
    CYBER_CYAN,
    CYBER_DARK_PALETTE,
    TEXT_PRIMARY,
)

from core.theme_palette import SEVERITY_COLOR_TOKENS

_active_palette: dict[str, str] = dict(CYBER_DARK_PALETTE)
_active_icon_color = CYBER_CYAN
_active_icon_color_active = TEXT_PRIMARY
_DEFAULT_ACTIVE_COLOR = object()


def set_icon_palette(palette: Mapping[str, str]) -> None:
    """Use the active application palette for subsequently created default icons."""
    global _active_icon_color, _active_icon_color_active, _active_palette
    _active_palette = dict(palette)
    _active_icon_color = palette.get("CYBER_CYAN", CYBER_CYAN)
    _active_icon_color_active = palette.get("TEXT_PRIMARY", TEXT_PRIMARY)


def get_theme_color(token: str, default: Optional[str] = None) -> str:
    """Return the active theme's hex/rgba value for the requested palette token."""
    if token == "BG_PRIMARY":
        return _active_palette.get("BG_DARK", _active_palette.get("BG_SURFACE", default or BG_DARK))
    return _active_palette.get(token, default or _active_icon_color)


def get_severity_color(severity: str, default: Optional[str] = None) -> str:
    """Return the active theme color for the requested severity level."""
    token = SEVERITY_COLOR_TOKENS.get(str(severity or "").lower(), "ACCENT_BRAND")
    return get_theme_color(token, default=default)


def get_active_palette() -> dict[str, str]:
    """Return a copy of the currently active theme palette dictionary."""
    return dict(_active_palette)


def icon(
    name: str,
    color: Optional[str] = None,
    color_active: Optional[str] | object = _DEFAULT_ACTIVE_COLOR,
    **kwargs,
) -> QIcon:
    """
    Creates a QIcon using the active theme unless explicit state colours are supplied.

    Args:
        name: The icon identifier (e.g. 'fa5s.thumbtack', 'fa5s.pen', 'fa5s.crop-alt', 'fa5s.cog', 'fa5s.circle').
        color: Optional explicit base color.
        color_active: Optional explicit active color; ``None`` disables that state color.
        **kwargs: Additional options forwarded to qtawesome.icon.

    Returns:
        A styled QIcon instance, or an empty QIcon on fallback.
    """
    options = {"color": color or _active_icon_color}
    if color_active is _DEFAULT_ACTIVE_COLOR:
        options["color_active"] = _active_icon_color_active
    elif color_active is not None:
        options["color_active"] = color_active
    options.update(kwargs)
    try:
        return qta.icon(name, **options)
    except Exception:
        return QIcon()

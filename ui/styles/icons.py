"""
Icon creation utilities using qtawesome for SpectreHUD.

Provides a unified helper for building theme-consistent QIcons across
platforms and components.
"""

from typing import Mapping, Optional
from PyQt6.QtGui import QIcon
import qtawesome as qta

from ui.styles.palette import CYBER_CYAN, TEXT_PRIMARY

_active_icon_color = CYBER_CYAN
_active_icon_color_active = TEXT_PRIMARY
_DEFAULT_ACTIVE_COLOR = object()


def set_icon_palette(palette: Mapping[str, str]) -> None:
    """Use the active application palette for subsequently created default icons."""
    global _active_icon_color, _active_icon_color_active
    _active_icon_color = palette["CYBER_CYAN"]
    _active_icon_color_active = palette["TEXT_PRIMARY"]


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

"""
Icon creation utilities using qtawesome for SpectreHUD.

Provides a unified helper for building theme-consistent QIcons across
platforms and components.
"""

from typing import Optional
from PyQt6.QtGui import QIcon
import qtawesome as qta

from ui.styles.palette import CYBER_CYAN, TEXT_PRIMARY


def icon(
    name: str,
    color: str = CYBER_CYAN,
    color_active: Optional[str] = TEXT_PRIMARY,
    **kwargs,
) -> QIcon:
    """
    Creates a QIcon styled with the Cyber HUD theme palette.

    Args:
        name: The icon identifier (e.g. 'fa5s.thumbtack', 'fa5s.pen', 'fa5s.crop-alt', 'fa5s.cog', 'fa5s.circle').
        color: Base icon color, defaults to CYBER_CYAN.
        color_active: Active / pressed / hovered state color, defaults to TEXT_PRIMARY.
        **kwargs: Additional options forwarded to qtawesome.icon.

    Returns:
        A styled QIcon instance, or an empty QIcon on fallback.
    """
    options = {"color": color}
    if color_active is not None:
        options["color_active"] = color_active
    options.update(kwargs)
    try:
        return qta.icon(name, **options)
    except Exception:
        return QIcon()

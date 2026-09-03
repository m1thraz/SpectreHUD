"""
SpectreHUD Modular Styles Package.
Exports APP_THEME, get_app_icon, get_app_icon_path, and palette design tokens.
"""

from ui.styles.palette import *  # noqa: F401, F403 (re-export palette tokens)
from ui.styles.theme import (
    APP_THEME,
    build_app_theme,
    clamp_transparency,
    get_app_icon,
    get_app_icon_path,
    with_alpha,
)

__all__ = [
    "APP_THEME",
    "build_app_theme",
    "clamp_transparency",
    "get_app_icon",
    "get_app_icon_path",
    "with_alpha",
]

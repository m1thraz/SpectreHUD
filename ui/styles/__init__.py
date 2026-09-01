"""
SpectreHUD Modular Styles Package.
Exports APP_THEME, CYBER_DARK_QSS, get_app_icon, get_app_icon_path, and palette design tokens.
"""
from ui.styles.palette import *
from ui.styles.theme import (
    APP_THEME,
    CYBER_DARK_QSS,
    build_app_theme,
    clamp_transparency,
    get_app_icon,
    get_app_icon_path,
    with_alpha,
)

__all__ = [
    "APP_THEME",
    "CYBER_DARK_QSS",
    "build_app_theme",
    "clamp_transparency",
    "get_app_icon",
    "get_app_icon_path",
    "with_alpha",
]

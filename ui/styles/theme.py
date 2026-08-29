"""
Master Theme Assembler and Icon Provider for SpectreHUD.
"""
from pathlib import Path
from typing import Optional
from PyQt6.QtGui import QIcon

from ui.styles.typography import get_typography_qss
from ui.styles.buttons import BUTTONS_QSS
from ui.styles.tables import TABLES_QSS
from ui.styles.cards import get_cards_qss
from ui.styles.dialogs import get_dialogs_qss
from ui.styles.fonts import get_code_font_stack, get_ui_font_stack

def build_app_theme(ui_font_key: str = "segoe_ui", code_font_key: str = "consolas") -> str:
    """Builds the application QSS from validated curated font keys."""
    ui_font = get_ui_font_stack(ui_font_key)
    code_font = get_code_font_stack(code_font_key)
    return "\n".join([
        get_typography_qss(ui_font, code_font),
        BUTTONS_QSS,
        TABLES_QSS,
        get_cards_qss(code_font),
        get_dialogs_qss(ui_font, code_font),
    ])


APP_THEME = build_app_theme()

# Backward-compatibility alias
CYBER_DARK_QSS = APP_THEME


def get_app_icon_path() -> Optional[Path]:
    """Resolves data/icon.ico or data/icon.svg across standard source tree, PyInstaller bundles, and package layouts."""
    # 0. Check PyInstaller frozen bundle
    import sys
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundle_data = Path(sys._MEIPASS) / "data"
        for name in ("icon.ico", "icon.svg"):
            candidate = bundle_data / name
            if candidate.exists():
                return candidate

    # 1. Check relative to this repository / package root
    root_data = Path(__file__).resolve().parent.parent.parent / "data"
    for name in ("icon.ico", "icon.svg"):
        candidate = root_data / name
        if candidate.exists():
            return candidate

    # 2. Check importlib.resources for wheel/egg installs
    try:
        import importlib.resources as pkg_resources
        if hasattr(pkg_resources, 'files'):
            for name in ("icon.ico", "icon.svg"):
                traversable = pkg_resources.files('data') / name
                res_path = Path(str(traversable))
                if res_path.exists():
                    return res_path
    except Exception:
        pass

    return None


def get_app_icon() -> QIcon:
    """Returns the official SpectreHUD QIcon."""
    icon_path = get_app_icon_path()
    if icon_path and icon_path.exists():
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            return icon
    return QIcon()

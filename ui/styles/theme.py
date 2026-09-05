"""
Master Theme Assembler and Icon Provider for SpectreHUD.
"""

from pathlib import Path
import re
from typing import Mapping, Optional
from PyQt6.QtGui import QColor, QIcon

from ui.styles.typography import TYPOGRAPHY_QSS_TEMPLATE
from ui.styles.buttons import BUTTONS_QSS_TEMPLATE
from ui.styles.tables import TABLES_QSS_TEMPLATE
from ui.styles.cards import CARDS_QSS_TEMPLATE
from ui.styles.dialogs import DIALOGS_QSS_TEMPLATE
from core.fonts import get_code_font_stack, get_ui_font_stack
from ui.styles.palette import CYBER_DARK_PALETTE
from core.config import clamp_transparency

_TOKEN_PATTERN = re.compile(r"\{([A-Z][A-Z0-9_]*|ui_font|code_font)\}")


def with_alpha(base_color: str, opacity_percent: int) -> str:
    """Return a Qt-compatible rgba colour with the requested opacity."""
    color = QColor(str(base_color))
    if not color.isValid():
        raise ValueError(f"Theme base colour is invalid: {base_color!r}")
    opacity = max(0, min(100, int(opacity_percent)))
    alpha = f"{opacity / 100:.2f}".rstrip("0").rstrip(".")
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"


def build_app_theme(
    palette: Mapping[str, str],
    ui_font_key: str = "segoe_ui",
    code_font_key: str = "consolas",
    hud_transparency: object = 5,
    report_transparency: object = 0,
    bleed_through: object = 0,
) -> str:
    """Build application QSS from a validated palette and curated font keys."""
    ui_font = get_ui_font_stack(ui_font_key)
    code_font = get_code_font_stack(code_font_key)
    context = dict(palette)
    hud_value = clamp_transparency(hud_transparency, 5)
    report_value = clamp_transparency(report_transparency, 0)
    bleed_value = clamp_transparency(bleed_through, 0)

    # Durchblick / echte Transparenz wird rein durch bleed_through gesteuert:
    # Bei bleed_through == 0 bleibt die Oberfläche 100% opak (BG_DARK).
    if bleed_value > 0:
        hud_color = with_alpha(context["BG_DARK"], 100 - bleed_value)
    else:
        hud_color = context["BG_DARK"]

    report_color = context["BG_DARK"]

    context.update(
        {
            "ui_font": ui_font,
            "code_font": code_font,
            "HUD_INTENSITY": str(hud_value),
            "REPORT_INTENSITY": str(report_value),
            "BLEED_THROUGH": str(bleed_value),
            "HUD_BACKGROUND": hud_color,
            "HUD_GLASS_COLOR": hud_color,
            "REPORT_EDITOR_BACKGROUND": report_color,
        }
    )
    raw = "\n".join(
        [
            TYPOGRAPHY_QSS_TEMPLATE,
            BUTTONS_QSS_TEMPLATE,
            TABLES_QSS_TEMPLATE,
            CARDS_QSS_TEMPLATE,
            DIALOGS_QSS_TEMPLATE,
        ]
    )

    def replace_token(match: re.Match[str]) -> str:
        token = match.group(1)
        if token not in context:
            raise KeyError(f"Theme palette is missing required token: {token}")
        return str(context[token])

    return _TOKEN_PATTERN.sub(replace_token, raw)


APP_THEME = build_app_theme(CYBER_DARK_PALETTE)


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

        if hasattr(pkg_resources, "files"):
            for name in ("icon.ico", "icon.svg"):
                traversable = pkg_resources.files("data") / name
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

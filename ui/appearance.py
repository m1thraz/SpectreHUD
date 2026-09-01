"""Central application-theme application for startup and runtime updates."""

from typing import Mapping, Optional

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QToolTip

from core.config import ConfigManager
from core.theme_loader import ThemeLoader
from ui.styles import build_app_theme


class _TooltipColorGuard(QObject):
    """Restore theme colours when Qt copies an ancestor's local QSS to QTipLabel."""

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._background = ""
        self._text = ""

    def update_colors(self, theme_palette: Mapping[str, str]) -> None:
        self._background = theme_palette["BG_SURFACE"]
        self._text = theme_palette["TEXT_PRIMARY"]

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() == QEvent.Type.Show
            and watched.metaObject().className() == "QTipLabel"
        ):
            watched.setPalette(QToolTip.palette())
            # Qt can copy the MainScrollArea's local transparent declarations
            # onto its transient QTipLabel. Override only the two affected
            # colours; the global QToolTip rule still owns font and geometry.
            watched.setStyleSheet(
                f"background-color: {self._background}; color: {self._text};"
            )
        return False


def apply_tooltip_palette(theme_palette: Mapping[str, str]) -> None:
    """Pin tooltip base/text colours independently of ancestor widget QSS."""
    palette = QToolTip.palette()
    palette.setColor(
        QPalette.ColorRole.ToolTipBase,
        QColor(theme_palette["BG_SURFACE"]),
    )
    palette.setColor(
        QPalette.ColorRole.ToolTipText,
        QColor(theme_palette["TEXT_PRIMARY"]),
    )
    QToolTip.setPalette(palette)


def _install_tooltip_color_guard(
    app: QApplication,
    theme_palette: Mapping[str, str],
) -> None:
    guard = getattr(app, "_spectrehud_tooltip_color_guard", None)
    if guard is None:
        guard = _TooltipColorGuard(app)
        app.installEventFilter(guard)
        app._spectrehud_tooltip_color_guard = guard
    guard.update_colors(theme_palette)


def apply_application_style(
    app: QApplication,
    config: ConfigManager,
    theme_id: Optional[str] = None,
) -> str:
    """Apply the persisted appearance through one shared runtime path.

    ``theme_id`` allows font/appearance updates to keep using the currently
    active palette while a newly selected theme waits for its controlled
    restart.
    """
    applied_theme = theme_id or config.get(
        "theme", ThemeLoader.FALLBACK_THEME_ID
    )
    theme_palette = ThemeLoader().load_theme(applied_theme)
    app.setStyleSheet(
        build_app_theme(
            theme_palette,
            config.get("ui_font", "segoe_ui"),
            config.get("code_font", "consolas"),
            hud_transparency=config.get("hud_transparency", 5),
            report_transparency=config.get("report_transparency", 0),
        )
    )
    apply_tooltip_palette(theme_palette)
    _install_tooltip_color_guard(app, theme_palette)
    return applied_theme

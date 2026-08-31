"""Regression tests for popup surfaces (tooltips, combo lists) under light themes.

A widget-level stylesheet on an ancestor scroll area used to detach popups
from the application stylesheet, leaving them on the unpolished black palette
in light themes such as Daylight. These tests pin the central QSS rules and
the popup rendering inside the affected panels.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QPushButton, QToolTip
from PyQt6.QtGui import QPalette

from core.config import ConfigManager
from core.storage import InMemoryStorageBackend
from core.theme_loader import ThemeLoader
from ui.panels.content_panel import ContentPanel
from ui.settings_dialog import AppearanceSettingsPage
from ui.styles import build_app_theme

app = QApplication.instance() or QApplication(sys.argv)


def _apply_daylight_theme() -> None:
    config = ConfigManager(
        config_dir=None,
        storage=InMemoryStorageBackend(initial_data={"config": {"theme": "daylight"}}),
    )
    palette = ThemeLoader().load_theme("daylight")
    app.setStyleSheet(
        build_app_theme(palette, config.get("ui_font", "segoe_ui"), config.get("code_font", "consolas"))
    )


def _active_tip_label():
    return next(
        (w for w in app.allWidgets() if w.metaObject().className() == "QTipLabel"),
        None,
    )


def test_scroll_areas_are_styled_centally_not_per_widget():
    qss = build_app_theme(ThemeLoader().load_theme("daylight"))
    assert "QScrollArea#MainScrollArea" in qss
    assert "QScrollArea#SettingsScrollArea" in qss

    panel = ContentPanel()
    assert panel.scroll_area.objectName() == "MainScrollArea"
    assert panel.scroll_area.styleSheet() == ""
    panel.deleteLater()

    page = AppearanceSettingsPage(ConfigManager(config_dir=None, storage=InMemoryStorageBackend()))
    scroll_areas = page.findChildren(type(panel.scroll_area))
    assert scroll_areas, "appearance page should host its content in a scroll area"
    for scroll in scroll_areas:
        assert scroll.objectName() in ("MainScrollArea", "SettingsScrollArea")
        assert scroll.styleSheet() == ""
    page.deleteLater()


def test_tooltip_inside_content_panel_keeps_theme_colors():
    _apply_daylight_theme()

    panel = ContentPanel()
    button = QPushButton("Report toolbar button")
    button.setToolTip("Choose report editor layout")
    panel.content_layout.addWidget(button)
    panel.resize(600, 400)
    panel.show()
    app.processEvents()

    QToolTip.showText(button.mapToGlobal(button.rect().center()), "Choose report editor layout", button)
    app.processEvents()
    tip = _active_tip_label()
    assert tip is not None, "tooltip widget was not created"

    corner = tip.grab().toImage().pixelColor(2, 2)
    assert corner.lightness() > 128, f"tooltip background is dark ({corner.name()}) in daylight theme"

    QToolTip.hideText()
    panel.hide()
    panel.deleteLater()


def test_combo_popup_inside_settings_page_keeps_theme_colors():
    _apply_daylight_theme()

    page = AppearanceSettingsPage(ConfigManager(config_dir=None, storage=InMemoryStorageBackend()))
    page.resize(640, 480)
    page.show()
    app.processEvents()

    combo = page.combo_theme
    assert combo.count() > 0
    combo.showPopup()
    app.processEvents()

    view_palette = combo.view().palette()
    base = view_palette.color(QPalette.ColorRole.Base)
    assert base.lightness() > 128, f"theme list background is dark ({base.name()}) in daylight theme"

    combo.hidePopup()
    page.hide()
    page.deleteLater()

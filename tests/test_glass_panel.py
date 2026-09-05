"""Rendered glass remains opaque, theme-aware, and stable across repaints."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QPlainTextEdit

from core.theme_loader import ThemeLoader
from ui.glass_panel import GlassPanel
from ui.report_editor_tab import ReportEditorTab
from ui.styles import build_app_theme


@pytest.mark.parametrize("theme", [p.stem for p in ThemeLoader.BUILTIN_THEMES_DIR.glob("*.json")])
def test_rendered_glass_is_opaque_and_changes_with_intensity(qapp, theme):
    panel = GlassPanel()
    panel.setObjectName("HudFrame")
    panel.resize(180, 120)
    palette = ThemeLoader().load_theme(theme)
    try:
        panel.setStyleSheet(build_app_theme(palette, hud_transparency=0))
        panel.ensurePolished()
        low = panel.grab().toImage()
        assert panel.glassColor == QColor(palette["BG_DARK"])
        assert all(
            low.pixelColor(x, y) == QColor(palette["BG_DARK"])
            for x in range(low.width())
            for y in range(low.height())
        )
        panel.setStyleSheet(build_app_theme(palette, hud_transparency=15))
        middle = panel.grab().toImage()
        panel.setStyleSheet(build_app_theme(palette, hud_transparency=30))
        high = panel.grab().toImage()
        assert low != high
        assert low != middle != high

        def deviation(image):
            base = QColor(palette["BG_DARK"])
            return sum(
                abs(image.pixelColor(x, y).lightness() - base.lightness())
                for x in range(10, image.width() - 10, 4)
                for y in range(10, image.height() - 10, 4)
            )

        assert deviation(middle) < deviation(high)
        assert high == panel.grab().toImage()
        panel.setStyleSheet(build_app_theme(palette, hud_transparency=0))
        assert panel.grab().toImage() == low
        other = GlassPanel()
        assert panel._noise.cacheKey() == other._noise.cacheKey()
        other.deleteLater()
    finally:
        panel.deleteLater()


def test_report_text_viewport_exposes_glass_without_changing_content(qapp):
    editor = QPlainTextEdit()
    panel = ReportEditorTab._wrap_glass_surface(editor)
    panel.resize(400, 300)
    palette = ThemeLoader().load_theme("cyber_dark")
    editor.setProperty("class", "ReportSourceEditor")
    panel.setStyleSheet(build_app_theme(palette, report_transparency=30))
    editor.setPlainText("# Evidence\nUnicode: ä ı λ")
    panel.show()
    qapp.processEvents()
    try:
        assert editor.toPlainText() == "# Evidence\nUnicode: ä ı λ"
        assert not editor.viewport().autoFillBackground()
        image = panel.grab().toImage()
        # Empty areas in the viewport show the underlying vertical gradient.
        assert image.pixelColor(200, 100) != image.pixelColor(200, 260)
    finally:
        panel.close()
        panel.deleteLater()


def test_glass_panel_bleed_through_opacity(qapp):
    panel = GlassPanel()
    try:
        # Default: 0 (opaque)
        assert panel.bleedThrough == 0
        assert not panel.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert panel._panel_opacity == 1.0
        assert panel.glassColor.alpha() == 255

        # 15: 50% of the bleed range -> panel opacity 0.75, WA_TranslucentBackground True
        panel.set_bleed_through(15)
        assert panel.bleedThrough == 15
        assert panel.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert panel._panel_opacity == 0.75
        expected_alpha_15 = int(255 * 85 / 100.0)
        assert panel.glassColor.alpha() == expected_alpha_15

        # 30: maximum bleed -> panel opacity 0.5, WA_TranslucentBackground True
        panel.set_bleed_through(30)
        assert panel.bleedThrough == 30
        assert panel.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert panel._panel_opacity == 0.5
        expected_alpha_30 = int(255 * 70 / 100.0)
        assert panel.glassColor.alpha() == expected_alpha_30

        # Reset back to 0 -> fully opaque, WA_TranslucentBackground False
        panel.set_bleed_through(0)
        assert panel.bleedThrough == 0
        assert not panel.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert panel._panel_opacity == 1.0
        assert panel.glassColor.alpha() == 255

        # Clamping check: negative clamps to 0, >30 clamps to 30
        panel.set_bleed_through(-5)
        assert panel.bleedThrough == 0
        panel.set_bleed_through(50)
        assert panel.bleedThrough == 30
    finally:
        panel.deleteLater()

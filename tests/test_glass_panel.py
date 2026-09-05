"""Rendered glass remains opaque, theme-aware, and stable across repaints."""

import pytest
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
            low.pixelColor(x, y).alpha() == 255
            for x in range(low.width())
            for y in range(low.height())
        )
        panel.setStyleSheet(build_app_theme(palette, hud_transparency=30))
        high = panel.grab().toImage()
        assert low != high
        assert high == panel.grab().toImage()
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

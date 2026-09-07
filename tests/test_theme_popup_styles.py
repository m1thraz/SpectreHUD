"""Regression tests for HUD glass surfaces and popups under light themes."""

import os
from pathlib import Path
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QPushButton, QScrollArea, QToolTip
from PyQt6.QtGui import QPalette

from core.config import ConfigManager
from core.storage import InMemoryStorageBackend
from core.theme_loader import ThemeLoader
from ui.appearance import apply_application_style
from ui.panels.content_panel import ContentPanel
from ui.settings_dialog import (
    AppearanceSettingsPage,
    GeneralSettingsPage,
    HotkeySettingsPage,
)
from ui.styles import build_app_theme


def _apply_daylight_theme(qapp) -> None:
    config = ConfigManager(
        config_dir=None,
        storage=InMemoryStorageBackend(initial_data={"config": {"theme": "daylight"}}),
    )
    apply_application_style(qapp, config)


def _active_tip_label(qapp):
    return next(
        (w for w in qapp.allWidgets() if w.metaObject().className() == "QTipLabel"),
        None,
    )


def _run_isolated_qt_probe(name: str) -> None:
    """Run global QApplication styling in a fresh process.

    Replacing application QSS after many session-scoped Qt tests can hang or
    crash native Qt on Windows. These probes intentionally keep the real
    QApplication, popup, palette and rendering path while isolating its lifecycle
    from pytest's shared application instance.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), name],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"isolated Qt probe {name!r} failed with {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _assert_transparent_scroll_surfaces(
    scroll: QScrollArea,
    *,
    expected_local_style: str = "",
) -> None:
    assert scroll.styleSheet() == expected_local_style
    assert not scroll.autoFillBackground()
    assert not scroll.viewport().autoFillBackground()
    assert scroll.widget() is not None
    assert not scroll.widget().autoFillBackground()


def test_main_scroll_area_scopes_transparency_to_scroll_surfaces(qapp):
    qss = build_app_theme(ThemeLoader().load_theme("daylight"))
    assert "QScrollArea#MainScrollArea" in qss
    assert "QScrollArea#SettingsScrollArea" in qss

    panel = ContentPanel()
    assert panel.scroll_area.objectName() == "MainScrollArea"
    _assert_transparent_scroll_surfaces(
        panel.scroll_area,
        expected_local_style=(
            "QScrollArea#MainScrollArea, QWidget#MainScrollViewport, "
            "QFrame#SnippetCard, QFrame#SnippetCard QWidget, "
            'QFrame#lootCard[boardCard="false"], QFrame#lootCard[boardCard="false"] QWidget, '
            "ReportEditorTab, ReportEditorTab QWidget "
            "{ background: transparent; border: none; }"
        ),
    )
    panel.deleteLater()


def test_settings_scroll_areas_remain_transparent_without_local_styles(qapp):
    qss = build_app_theme(ThemeLoader().load_theme("daylight"))
    assert "QScrollArea#SettingsScrollArea" in qss

    for page_type in (HotkeySettingsPage, AppearanceSettingsPage, GeneralSettingsPage):
        page = page_type(ConfigManager(config_dir=None, storage=InMemoryStorageBackend()))
        scroll_areas = page.findChildren(QScrollArea)
        assert scroll_areas, f"{page_type.__name__} should host content in a scroll area"
        for scroll in scroll_areas:
            assert scroll.objectName() == "SettingsScrollArea"
            _assert_transparent_scroll_surfaces(scroll)
        page.deleteLater()


def _probe_tooltip_inside_content_panel_keeps_theme_colors(qapp):
    _apply_daylight_theme(qapp)

    panel = ContentPanel()
    button = QPushButton("Report toolbar button")
    button.setToolTip("Choose report editor layout")
    panel.content_layout.addWidget(button)
    panel.resize(600, 400)
    panel.show()
    qapp.processEvents()

    QToolTip.showText(
        button.mapToGlobal(button.rect().center()),
        "Choose report editor layout",
        button,
    )
    qapp.processEvents()
    tip = _active_tip_label(qapp)
    assert tip is not None, "tooltip widget was not created"

    corner = tip.grab().toImage().pixelColor(2, 2)
    assert corner.lightness() > 128, (
        f"tooltip background is dark ({corner.name()}) in daylight theme"
    )

    QToolTip.hideText()
    panel.hide()
    panel.deleteLater()


@pytest.mark.integration
def test_tooltip_inside_content_panel_keeps_theme_colors():
    _run_isolated_qt_probe("tooltip")


def _probe_combo_popup_inside_settings_page_keeps_theme_colors(qapp):
    _apply_daylight_theme(qapp)

    page = AppearanceSettingsPage(ConfigManager(config_dir=None, storage=InMemoryStorageBackend()))
    page.resize(640, 480)
    page.show()
    qapp.processEvents()

    combo = page.combo_theme
    assert combo.count() > 0
    combo.showPopup()
    qapp.processEvents()

    view_palette = combo.view().palette()
    base = view_palette.color(QPalette.ColorRole.Base)
    assert base.lightness() > 128, (
        f"theme list background is dark ({base.name()}) in daylight theme"
    )

    combo.hidePopup()
    page.hide()
    page.deleteLater()


@pytest.mark.integration
def test_combo_popup_inside_settings_page_keeps_theme_colors():
    _run_isolated_qt_probe("combo")


if __name__ == "__main__":
    probe_name = sys.argv[1] if len(sys.argv) > 1 else ""
    probe = {
        "tooltip": _probe_tooltip_inside_content_panel_keeps_theme_colors,
        "combo": _probe_combo_popup_inside_settings_page_keeps_theme_colors,
    }.get(probe_name)
    if probe is None:
        raise SystemExit(f"unknown Qt probe: {probe_name!r}")

    from tests.qt_subprocess import create_probe_application

    application = create_probe_application()
    try:
        probe(application)
        application.processEvents()
    finally:
        QToolTip.hideText()
        application.processEvents()


@pytest.mark.parametrize("kind", ["cheatsheet", "history", "notes", "loot"])
def test_non_board_cards_keep_flat_backgrounds(qapp, kind):
    from PyQt6.QtCore import QPoint
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QWidget, QVBoxLayout
    from ui.snippet_card import SnippetCard
    from ui.history_card import HistoryCard
    from ui.quick_note_card import QuickNoteCard
    from ui.loot_card import LootCard

    root = QWidget()
    root.setObjectName("FlatTestRoot")
    root.setStyleSheet(
        build_app_theme(ThemeLoader().load_theme("cyber_dark"))
        + "QWidget#FlatTestRoot { background-color: #202126; }"
    )
    layout = QVBoxLayout(root)
    panel = ContentPanel()
    layout.addWidget(panel)
    entry = {
        "id": "flat",
        "title": "Example",
        "content": "example value",
        "text": "example note",
        "type": "note",
        "category": "recon",
    }
    if kind == "cheatsheet":
        card = SnippetCard(
            {**entry, "template": "curl http://example.test", "description": "Example"}, {}
        )
    else:
        card = {"history": HistoryCard, "notes": QuickNoteCard, "loot": LootCard}[kind](entry)
    panel.content_layout.addWidget(card)
    root.resize(900, 600)
    root.show()
    for _ in range(5):
        qapp.processEvents()
    try:
        image = root.grab().toImage()
        point = card.mapTo(root, QPoint(card.width() // 2, 3))
        assert image.pixelColor(point) == QColor("#202126")
        content = getattr(card, "lbl_command", None) or card.lbl_content
        point = content.mapTo(root, QPoint(3, 3))
        assert image.pixelColor(point) == QColor("#202126")
    finally:
        root.close()
        root.deleteLater()

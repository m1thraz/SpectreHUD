"""Regression tests for curated font preferences."""

from types import MethodType, SimpleNamespace
from unittest.mock import Mock

from PyQt6.QtWidgets import QApplication

from core.config import ConfigManager
from core.reporting.template import render_report_html
from core.storage import InMemoryStorageBackend
from ui.app_controller import AppController
from ui.styles import build_app_theme
from ui.styles.palette import CYBER_DARK_PALETTE
from ui.styles.fonts import (
    CODE_FONT_OPTIONS,
    CODE_FONT_STACKS,
    REPORT_FONT_OPTIONS,
    REPORT_FONT_STACKS,
    UI_FONT_OPTIONS,
    UI_FONT_STACKS,
)


app = QApplication.instance() or QApplication([])


def _runtime_style_harness():
    config = ConfigManager(storage=InMemoryStorageBackend())
    controller = SimpleNamespace(
        config=config,
        _applied_theme=config.get("theme"),
        _applied_ui_font=config.get("ui_font"),
        _applied_code_font=config.get("code_font"),
        report_ctrl=SimpleNamespace(refresh_font_configuration=Mock()),
        restart_requested=SimpleNamespace(emit=Mock()),
        _update_footer_status=lambda: None,
    )
    controller.apply_application_style = MethodType(
        AppController.apply_application_style, controller
    )
    return controller


def test_font_option_keys_are_complete_and_unique():
    for options, stacks in (
        (UI_FONT_OPTIONS, UI_FONT_STACKS),
        (CODE_FONT_OPTIONS, CODE_FONT_STACKS),
        (REPORT_FONT_OPTIONS, REPORT_FONT_STACKS),
    ):
        keys = [key for key, _label in options]
        assert len(keys) == len(set(keys))
        assert set(keys) == set(stacks)


def test_qss_uses_selected_ui_and_code_fonts():
    qss = build_app_theme(CYBER_DARK_PALETTE, "inter", "jetbrains_mono")
    assert UI_FONT_STACKS["inter"] in qss
    assert CODE_FONT_STACKS["jetbrains_mono"] in qss
    assert "QToolTip" in qss
    assert "color: #f0f6fc;" in qss


def test_settings_apply_updates_running_ui_font_without_restart():
    controller = _runtime_style_harness()
    previous_stylesheet = app.styleSheet()
    try:
        controller.config.set("ui_font", "inter")

        AppController._on_settings_applied(controller, {"ui_font": "inter"})

        assert UI_FONT_STACKS["inter"] in app.styleSheet()
        assert controller._applied_ui_font == "inter"
        controller.restart_requested.emit.assert_not_called()
    finally:
        app.setStyleSheet(previous_stylesheet)


def test_settings_apply_updates_running_code_font_without_restart():
    controller = _runtime_style_harness()
    previous_stylesheet = app.styleSheet()
    try:
        controller.config.set("code_font", "jetbrains_mono")

        AppController._on_settings_applied(
            controller, {"code_font": "jetbrains_mono"}
        )

        assert CODE_FONT_STACKS["jetbrains_mono"] in app.styleSheet()
        assert controller._applied_code_font == "jetbrains_mono"
        controller.restart_requested.emit.assert_not_called()
    finally:
        app.setStyleSheet(previous_stylesheet)


def test_font_apply_does_not_activate_pending_theme_before_restart():
    controller = _runtime_style_harness()
    previous_stylesheet = app.styleSheet()
    try:
        controller.config.update({"theme": "daylight", "ui_font": "inter"})

        AppController._on_settings_applied(
            controller, {"theme": "daylight", "ui_font": "inter"}
        )

        assert "#0d1117" in app.styleSheet()
        assert controller._applied_theme == "cyber_dark"
        assert controller._applied_ui_font == "inter"
    finally:
        app.setStyleSheet(previous_stylesheet)


def test_invalid_font_preferences_fall_back_to_safe_defaults():
    qss = build_app_theme(CYBER_DARK_PALETTE, "missing-ui", "missing-code")
    assert UI_FONT_STACKS["segoe_ui"] in qss
    assert CODE_FONT_STACKS["consolas"] in qss

    report_html = render_report_html("<p>Report</p>", report_font="missing-report")
    assert REPORT_FONT_STACKS["segoe_ui"] in report_html


def test_report_html_uses_selected_report_font():
    report_html = render_report_html("<p>Report</p>", report_font="georgia")
    assert REPORT_FONT_STACKS["georgia"] in report_html
    assert 'contenteditable="true"' in report_html
    assert "resize: both" in report_html
    assert "downloadEditedHtml" in report_html


def test_report_font_remains_independent_from_application_fonts():
    controller = _runtime_style_harness()
    previous_stylesheet = app.styleSheet()
    try:
        app.setStyleSheet("/* application style sentinel */")
        controller.config.set("report_font", "georgia")

        AppController._on_settings_applied(controller, {"report_font": "georgia"})

        assert app.styleSheet() == "/* application style sentinel */"
        controller.report_ctrl.refresh_font_configuration.assert_called_once_with()
        report_html = render_report_html("<p>Report</p>", report_font="georgia")
        assert REPORT_FONT_STACKS["georgia"] in report_html
    finally:
        app.setStyleSheet(previous_stylesheet)

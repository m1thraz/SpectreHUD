"""Regression tests for curated font preferences."""

from core.reporting.template import render_report_html
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

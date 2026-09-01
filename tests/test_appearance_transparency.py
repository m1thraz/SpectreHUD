"""Regression coverage for runtime appearance and independent transparency."""

from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QToolTip

from core.config import ConfigManager
from core.storage import InMemoryStorageBackend
from core.theme_loader import ThemeLoader
from ui.appearance import apply_application_style
from ui.app_controller import AppController
from ui.styles import build_app_theme
from ui.styles.fonts import CODE_FONT_STACKS, UI_FONT_STACKS
from ui.styles.palette import CYBER_DARK_PALETTE


def _controller_harness(config: ConfigManager):
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


def _apply_style_without_native_qt_state(config: ConfigManager, theme_id=None):
    """Apply the real QSS builder to a Python mock instead of global QApplication.

    Application-wide stylesheet replacement is a native Qt operation. Replacing
    and restoring it repeatedly on the session-scoped QApplication can access
    widgets pending deferred deletion and has crashed Qt on Windows/Python 3.12.
    Popup/tooltip integration remains covered in ``test_theme_popup_styles.py``.
    """
    app = Mock()
    with patch("ui.appearance._install_tooltip_color_guard"):
        applied_theme = apply_application_style(app, config, theme_id=theme_id)

    qss = app.setStyleSheet.call_args.args[0]
    return app, applied_theme, qss


def _assert_hud_background(qss: str, expected: str) -> None:
    assert (
        "QFrame#HudFrame {\n"
        f"    background-color: {expected};"
    ) in qss


def _assert_report_background(qss: str, expected: str) -> None:
    assert (
        "QPlainTextEdit.ReportSourceEditor {\n"
        f"    background-color: {expected};"
    ) in qss
    assert (
        "QTextEdit.ReportPreview {\n"
        f"    background-color: {expected};"
    ) in qss


def test_missing_transparency_preferences_use_reference_defaults():
    config = ConfigManager(storage=InMemoryStorageBackend(initial_data={"config": {}}))

    assert config.get("hud_transparency") == 5
    assert config.get("report_transparency") == 0


@pytest.mark.parametrize(
    ("stored_hud", "stored_report", "expected_hud", "expected_report"),
    [
        (-1, 31, 0, 30),
        (80, -20, 30, 0),
        ("invalid", None, 5, 0),
    ],
)
def test_loaded_transparency_preferences_are_clamped(
    stored_hud,
    stored_report,
    expected_hud,
    expected_report,
):
    config = ConfigManager(
        storage=InMemoryStorageBackend(
            initial_data={
                "config": {
                    "hud_transparency": stored_hud,
                    "report_transparency": stored_report,
                }
            }
        )
    )

    assert config.get("hud_transparency") == expected_hud
    assert config.get("report_transparency") == expected_report


@pytest.mark.parametrize(
    ("transparency", "expected"),
    [
        (0, "rgba(13, 17, 23, 1)"),
        (5, "rgba(13, 17, 23, 0.95)"),
        (20, "rgba(13, 17, 23, 0.8)"),
    ],
)
def test_hud_transparency_controls_only_hud_opacity(transparency, expected):
    qss = build_app_theme(
        CYBER_DARK_PALETTE,
        hud_transparency=transparency,
        report_transparency=0,
    )

    _assert_hud_background(qss, expected)
    _assert_report_background(qss, "rgba(13, 17, 23, 1)")


@pytest.mark.parametrize(
    ("transparency", "expected"),
    [
        (0, "rgba(13, 17, 23, 1)"),
        (10, "rgba(13, 17, 23, 0.9)"),
    ],
)
def test_report_transparency_controls_only_editor_surfaces(
    transparency,
    expected,
):
    qss = build_app_theme(
        CYBER_DARK_PALETTE,
        hud_transparency=5,
        report_transparency=transparency,
    )

    _assert_hud_background(qss, "rgba(13, 17, 23, 0.95)")
    _assert_report_background(qss, expected)


def test_theme_change_reuses_transparency_with_new_base_colors():
    daylight = ThemeLoader().load_theme("daylight")
    qss = build_app_theme(
        daylight,
        hud_transparency=20,
        report_transparency=10,
    )

    _assert_hud_background(qss, "rgba(245, 247, 250, 0.8)")
    _assert_report_background(qss, "rgba(245, 247, 250, 0.9)")


def test_save_apply_updates_both_transparencies_without_restart():
    config = ConfigManager(storage=InMemoryStorageBackend())
    controller = _controller_harness(config)
    runtime_app = Mock()
    with (
        patch("ui.app_controller.QApplication") as application_type,
        patch("ui.appearance.apply_tooltip_palette"),
        patch("ui.appearance._install_tooltip_color_guard"),
    ):
        application_type.instance.return_value = runtime_app
        config.update({"hud_transparency": 20, "report_transparency": 10})

        AppController._on_settings_applied(
            controller,
            {"hud_transparency": 20, "report_transparency": 10},
        )

        qss = runtime_app.setStyleSheet.call_args.args[0]
        _assert_hud_background(qss, "rgba(13, 17, 23, 0.8)")
        _assert_report_background(qss, "rgba(13, 17, 23, 0.9)")
        controller.restart_requested.emit.assert_not_called()


def test_font_and_transparency_updates_share_one_runtime_apply():
    config = ConfigManager(storage=InMemoryStorageBackend())
    controller = _controller_harness(config)
    runtime_app = Mock()
    with (
        patch("ui.app_controller.QApplication") as application_type,
        patch("ui.appearance.apply_tooltip_palette"),
        patch("ui.appearance._install_tooltip_color_guard"),
    ):
        application_type.instance.return_value = runtime_app
        config.update(
            {
                "ui_font": "inter",
                "code_font": "jetbrains_mono",
                "hud_transparency": 12,
                "report_transparency": 7,
            }
        )

        AppController._on_settings_applied(
            controller,
            {
                "ui_font": "inter",
                "code_font": "jetbrains_mono",
                "hud_transparency": 12,
                "report_transparency": 7,
            },
        )

        qss = runtime_app.setStyleSheet.call_args.args[0]
        runtime_app.setStyleSheet.assert_called_once()
        assert UI_FONT_STACKS["inter"] in qss
        assert CODE_FONT_STACKS["jetbrains_mono"] in qss
        _assert_hud_background(qss, "rgba(13, 17, 23, 0.88)")
        _assert_report_background(qss, "rgba(13, 17, 23, 0.93)")


def test_daylight_apply_updates_tooltip_palette_and_keeps_global_qss():
    config = ConfigManager(
        storage=InMemoryStorageBackend(
            initial_data={"config": {"theme": "daylight"}}
        )
    )
    old_palette = QToolTip.palette()
    try:
        _app, _theme, qss = _apply_style_without_native_qt_state(config)

        daylight = ThemeLoader().load_theme("daylight")
        tooltip_palette = QToolTip.palette()
        assert tooltip_palette.color(QPalette.ColorRole.ToolTipBase).name() == daylight["BG_SURFACE"]
        assert tooltip_palette.color(QPalette.ColorRole.ToolTipText).name() == daylight["TEXT_PRIMARY"]
        assert "QToolTip {" in qss
        assert f"background-color: {daylight['BG_SURFACE']};" in qss
        assert f"color: {daylight['TEXT_PRIMARY']};" in qss
    finally:
        QToolTip.setPalette(old_palette)


def test_reapplying_theme_refreshes_tooltip_palette_without_resetting_values():
    config = ConfigManager(
        storage=InMemoryStorageBackend(
            initial_data={
                "config": {
                    "theme": "daylight",
                    "hud_transparency": 18,
                    "report_transparency": 6,
                }
            }
        )
    )
    old_palette = QToolTip.palette()
    try:
        _apply_style_without_native_qt_state(config)
        config.set("theme", "nord")
        _app, _theme, qss = _apply_style_without_native_qt_state(config)

        nord = ThemeLoader().load_theme("nord")
        tooltip_palette = QToolTip.palette()
        assert tooltip_palette.color(QPalette.ColorRole.ToolTipBase).name() == nord["BG_SURFACE"]
        assert tooltip_palette.color(QPalette.ColorRole.ToolTipText).name() == nord["TEXT_PRIMARY"]
        _assert_hud_background(qss, "rgba(46, 52, 64, 0.82)")
        _assert_report_background(qss, "rgba(46, 52, 64, 0.94)")
        assert config.get("hud_transparency") == 18
        assert config.get("report_transparency") == 6
    finally:
        QToolTip.setPalette(old_palette)

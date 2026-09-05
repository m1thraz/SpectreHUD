"""Runtime appearance and independent glass intensity using legacy saved keys."""

from unittest.mock import Mock, patch

import pytest
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QToolTip

from core.config import ConfigManager
from core.storage import InMemoryStorageBackend
from core.theme_loader import ThemeLoader
from ui.appearance import apply_application_style
from ui.coordinators.settings_coordinator import SettingsCoordinator
from ui.styles import build_app_theme
from core.fonts import CODE_FONT_STACKS, UI_FONT_STACKS
from ui.styles.palette import CYBER_DARK_PALETTE


def _controller_harness(config: ConfigManager):
    return SettingsCoordinator(
        config=config,
        event_bus=Mock(),
        workspace_coord=Mock(),
        report_ctrl=Mock(),
        footer=Mock(),
        window=Mock(),
        loot_manager=Mock(),
        clipboard_history=Mock(),
        update_footer_status=Mock(),
        load_active_project_state=Mock(),
        refresh_filter_pills=Mock(),
        refresh_content=Mock(),
        retranslate_ui=Mock(),
    )


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


def _assert_hud_background(qss: str, expected: tuple[str, int]) -> None:
    _assert_glass_properties(qss, "QFrame#HudFrame", expected)
    color, _ = expected
    assert f"background-color: {color};" in qss


def _assert_report_background(qss: str, expected: tuple[str, int]) -> None:
    _assert_glass_properties(qss, "QFrame.ReportGlassPanel", expected)
    assert "QPlainTextEdit.ReportSourceEditor {\n    background-color: transparent;" in qss
    assert "QTextEdit.ReportPreview {\n    background-color: transparent;" in qss


def _assert_glass_properties(qss, selector, expected):
    color, intensity = expected
    assert f"qproperty-glassColor: {color};" in qss
    assert f"qproperty-glassIntensity: {intensity};" in qss


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
        (0, ("#0d1117", 0)),
        (5, ("#0d1117", 5)),
        (20, ("#0d1117", 20)),
    ],
)
def test_legacy_hud_preference_controls_only_hud_glass(transparency, expected):
    qss = build_app_theme(
        CYBER_DARK_PALETTE,
        hud_transparency=transparency,
        report_transparency=0,
    )

    _assert_hud_background(qss, expected)
    _assert_report_background(qss, ("#0d1117", 0))


@pytest.mark.parametrize(
    ("transparency", "expected"),
    [
        (0, ("#0d1117", 0)),
        (10, ("#0d1117", 10)),
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

    _assert_hud_background(qss, ("#0d1117", 5))
    _assert_report_background(qss, expected)


def test_theme_change_reuses_transparency_with_new_base_colors():
    daylight = ThemeLoader().load_theme("daylight")
    qss = build_app_theme(
        daylight,
        hud_transparency=20,
        report_transparency=10,
    )

    _assert_hud_background(qss, ("#f5f7fa", 20))
    _assert_report_background(qss, ("#f5f7fa", 10))


def test_save_apply_updates_both_transparencies_without_restart():
    config = ConfigManager(storage=InMemoryStorageBackend())
    controller = _controller_harness(config)
    runtime_app = Mock()
    with (
        patch("ui.coordinators.settings_coordinator.QApplication") as application_type,
        patch("ui.appearance.apply_tooltip_palette"),
        patch("ui.appearance._install_tooltip_color_guard"),
    ):
        application_type.instance.return_value = runtime_app
        config.update({"hud_transparency": 20, "report_transparency": 10})

        controller.apply(
            {"hud_transparency": 20, "report_transparency": 10},
        )

        qss = runtime_app.setStyleSheet.call_args.args[0]
        _assert_hud_background(qss, ("#0d1117", 20))
        _assert_report_background(qss, ("#0d1117", 10))


def test_font_and_transparency_updates_share_one_runtime_apply():
    config = ConfigManager(storage=InMemoryStorageBackend())
    controller = _controller_harness(config)
    runtime_app = Mock()
    with (
        patch("ui.coordinators.settings_coordinator.QApplication") as application_type,
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

        controller.apply(
            {
                "ui_font": "inter",
                "code_font": "jetbrains_mono",
                "hud_transparency": 12,
                "report_transparency": 7,
            }
        )

        qss = runtime_app.setStyleSheet.call_args.args[0]
        runtime_app.setStyleSheet.assert_called_once()
        assert UI_FONT_STACKS["inter"] in qss
        assert CODE_FONT_STACKS["jetbrains_mono"] in qss
        _assert_hud_background(qss, ("#0d1117", 12))
        _assert_report_background(qss, ("#0d1117", 7))


def test_daylight_apply_updates_tooltip_palette_and_keeps_global_qss():
    config = ConfigManager(
        storage=InMemoryStorageBackend(initial_data={"config": {"theme": "daylight"}})
    )
    old_palette = QToolTip.palette()
    try:
        _app, _theme, qss = _apply_style_without_native_qt_state(config)

        daylight = ThemeLoader().load_theme("daylight")
        tooltip_palette = QToolTip.palette()
        assert (
            tooltip_palette.color(QPalette.ColorRole.ToolTipBase).name() == daylight["BG_SURFACE"]
        )
        assert (
            tooltip_palette.color(QPalette.ColorRole.ToolTipText).name() == daylight["TEXT_PRIMARY"]
        )
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
        _assert_hud_background(qss, ("#2e3440", 18))
        _assert_report_background(qss, ("#2e3440", 6))
        assert config.get("hud_transparency") == 18
        assert config.get("report_transparency") == 6
    finally:
        QToolTip.setPalette(old_palette)


def test_bleed_through_clamping_and_default():
    config = ConfigManager(storage=InMemoryStorageBackend(initial_data={"config": {}}))
    assert config.get("bleed_through") == 0

    config_clamped = ConfigManager(
        storage=InMemoryStorageBackend(
            initial_data={
                "config": {
                    "bleed_through": 99,
                }
            }
        )
    )
    assert config_clamped.get("bleed_through") == 30

    config_neg = ConfigManager(
        storage=InMemoryStorageBackend(
            initial_data={
                "config": {
                    "bleed_through": -10,
                }
            }
        )
    )
    assert config_neg.get("bleed_through") == 0


def test_build_app_theme_bleed_through():
    palette = CYBER_DARK_PALETTE
    # When 0 (default): bleedThrough is 0, HUD_GLASS_COLOR is opaque BG_DARK
    qss_zero = build_app_theme(palette, hud_transparency=10, bleed_through=0)
    assert "qproperty-bleedThrough: 0;" in qss_zero
    assert f"qproperty-glassColor: {palette['BG_DARK']};" in qss_zero

    # When 20: bleedThrough is 20, HUD_GLASS_COLOR has rgba alpha (100 - 20 = 80%)
    qss_bleed = build_app_theme(palette, hud_transparency=10, bleed_through=20)
    assert "qproperty-bleedThrough: 20;" in qss_bleed
    assert "rgba(" in qss_bleed


def test_settings_coordinator_applies_bleed_through_to_window():
    config = ConfigManager(storage=InMemoryStorageBackend(initial_data={"config": {}}))
    harness = _controller_harness(config)
    harness.window.set_bleed_through = Mock()

    harness.apply({"bleed_through": 25})
    harness.window.set_bleed_through.assert_called_once_with(25)

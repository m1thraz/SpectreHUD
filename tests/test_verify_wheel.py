"""Regression tests for the release-wheel verifier."""

from scripts.verify_wheel import REQUIRED_FILES, get_project_version


def test_reporting_template_engine_is_required_instead_of_removed_models_module():
    """Keep the verifier aligned with the reporting package's current layout."""
    assert "core/reporting/template_engine.py" in REQUIRED_FILES
    assert "core/reporting/models.py" not in REQUIRED_FILES


def test_clipboard_history_and_monitor_are_required_instead_of_legacy_watcher():
    """Verifier must require decoupled clipboard modules instead of legacy clipboard_watcher."""
    assert "core/clipboard_history.py" in REQUIRED_FILES
    assert "ui/clipboard_monitor.py" in REQUIRED_FILES
    assert "core/clipboard_watcher.py" not in REQUIRED_FILES


def test_wheel_verifier_uses_the_current_release_version():
    """Stale wheels must not be selected from a reused dist directory."""
    from core.cli import APP_VERSION
    assert get_project_version() == APP_VERSION


def test_linux_platform_modules_are_required_in_release_wheel():
    expected = {
        "core/platform/__init__.py",
        "core/platform/capabilities.py",
        "core/platform/paths.py",
        "core/platform/opener.py",
        "core/platform/network.py",
    }

    assert expected.issubset(REQUIRED_FILES)


def test_linux_desktop_assets_are_required_in_release_wheel():
    expected = {
        "resources/linux/spectrehud.desktop",
        "resources/linux/icons/hicolor/48x48/apps/spectrehud.png",
        "resources/linux/icons/hicolor/128x128/apps/spectrehud.png",
        "resources/linux/icons/hicolor/256x256/apps/spectrehud.png",
        "resources/linux/icons/hicolor/scalable/apps/spectrehud.svg",
    }

    assert expected.issubset(REQUIRED_FILES)


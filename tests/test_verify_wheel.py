"""Regression tests for the release-wheel verifier."""

from scripts.verify_wheel import REQUIRED_FILES, get_project_version


def test_reporting_template_engine_is_required_instead_of_removed_models_module():
    """Keep the verifier aligned with the reporting package's current layout."""
    assert "core/reporting/template_engine.py" in REQUIRED_FILES
    assert "core/reporting/models.py" not in REQUIRED_FILES


def test_wheel_verifier_uses_the_current_release_version():
    """Stale wheels must not be selected from a reused dist directory."""
    assert get_project_version() == "2.0.3"


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


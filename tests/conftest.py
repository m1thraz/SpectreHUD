"""Shared pytest isolation for SpectreHUD's filesystem-backed services."""

import os

import pytest


# Qt must be configured before a QApplication is constructed by an imported
# test module. Individual tests may still override this for platform checks.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """Provide the single QApplication shared by pytest-style Qt tests."""
    from PyQt6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application
    tooltip_guard = getattr(application, "_spectrehud_tooltip_color_guard", None)
    if tooltip_guard is not None:
        application.removeEventFilter(tooltip_guard)
        tooltip_guard.deleteLater()
        delattr(application, "_spectrehud_tooltip_color_guard")
    application.processEvents()


@pytest.fixture(autouse=True)
def isolate_spectrehud_user_data(tmp_path, monkeypatch):
    """Route every test's implicit app paths into fresh temporary folders.

    Tests that need custom paths can still set the variables themselves, but
    no test can accidentally fall back to the user's real configuration or
    project workspace after another test cleans up its environment variables.
    """
    config_dir = tmp_path / "config"
    projects_dir = tmp_path / "projects"
    monkeypatch.setenv("SPECTRE_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("SPECTRE_PROJECTS_DIR", str(projects_dir))

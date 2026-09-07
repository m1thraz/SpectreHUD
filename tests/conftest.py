"""Shared pytest isolation for SpectreHUD's filesystem-backed services."""

import os
import sys

import pytest


# Qt must be configured before a QApplication is constructed by an imported
# test module. Individual tests may still override this for platform checks.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Importing main.py installs the production exception hook. Test runs must not
# turn asynchronous Qt failures into modal dialogs that no offscreen user can close.
os.environ.setdefault("SPECTREHUD_NO_GUI_CRASH_POPUP", "1")


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Provide the only QApplication owned by the pytest process."""
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
    yield

    # Qt defers QObject destruction until the event loop runs. Without draining
    # those events, global signals and event filters accumulate across tests and
    # make unrelated locale or stylesheet changes progressively slower.
    qt_widgets = sys.modules.get("PyQt6.QtWidgets")
    if qt_widgets is None:
        return
    application = qt_widgets.QApplication.instance()
    if application is None:
        return

    for widget in application.topLevelWidgets():
        controller = getattr(widget, "app", None)
        if controller is not None and hasattr(controller, "dispose"):
            controller.dispose()
        widget.deleteLater()

    from PyQt6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

"""Shared pytest isolation for SpectreHUD's filesystem-backed services."""

import os
from pathlib import Path
import re
import sys

import pytest


# Qt must be configured before a QApplication is constructed by an imported
# test module. Individual tests may still override this for platform checks.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Importing main.py installs the production exception hook. Test runs must not
# turn asynchronous Qt failures into modal dialogs that no offscreen user can close.
os.environ.setdefault("SPECTREHUD_NO_GUI_CRASH_POPUP", "1")

_session_qapp = None


def _ensure_qapp():
    """Lazily construct the shared session QApplication on first demand."""
    global _session_qapp
    if _session_qapp is None:
        from PyQt6.QtWidgets import QApplication

        _session_qapp = QApplication.instance() or QApplication([])
    return _session_qapp


@pytest.fixture(scope="session")
def qapp():
    """Provide the only QApplication owned by the pytest process."""
    application = _ensure_qapp()
    yield application


_UI_IMPORT_PATTERN = re.compile(rb"^\s*(?:from|import)\s+(?:PyQt6|ui)\b", re.MULTILINE)
_UI_FILE_CACHE: dict[str, bool] = {}


def _is_ui_test_file(path_str: str) -> bool:
    cached = _UI_FILE_CACHE.get(path_str)
    if cached is not None:
        return cached
    try:
        is_ui = bool(_UI_IMPORT_PATTERN.search(Path(path_str).read_bytes()))
    except OSError:
        is_ui = False
    _UI_FILE_CACHE[path_str] = is_ui
    return is_ui


def pytest_collection_modifyitems(config, items):
    """Categorize tests with ui or unit markers based on import requirements."""
    ui_marker = pytest.mark.ui
    unit_marker = pytest.mark.unit
    for item in items:
        file_path = str(getattr(item, "path", getattr(item, "fspath", "")))
        if file_path and _is_ui_test_file(file_path):
            if item.get_closest_marker("ui") is None:
                item.add_marker(ui_marker)
        else:
            if (
                item.get_closest_marker("unit") is None
                and item.get_closest_marker("integration") is None
            ):
                item.add_marker(unit_marker)


def pytest_runtest_setup(item):
    """Ensure QApplication is ready before any test that uses Qt or UI widgets."""
    if (
        "PyQt6.QtWidgets" in sys.modules
        or item.get_closest_marker("ui") is not None
        or item.get_closest_marker("integration") is not None
    ):
        _ensure_qapp()


def pytest_sessionfinish(session, exitstatus):
    """Clean up QApplication resources if Qt was initialized during this session."""
    global _session_qapp
    if _session_qapp is not None:
        tooltip_guard = getattr(_session_qapp, "_spectrehud_tooltip_color_guard", None)
        if tooltip_guard is not None:
            _session_qapp.removeEventFilter(tooltip_guard)
            tooltip_guard.deleteLater()
            delattr(_session_qapp, "_spectrehud_tooltip_color_guard")
        _session_qapp.processEvents()


@pytest.fixture(autouse=True)
def isolate_spectrehud_user_data(tmp_path, monkeypatch):
    """Route every test's implicit app paths into fresh temporary folders.

    Tests that need custom paths can still set the variables themselves, but
    no test can accidentally fall back to the user's real configuration or
    project workspace after another test cleans up its environment variables.
    """
    config_dir = tmp_path / "config"
    log_dir = tmp_path / "logs"
    projects_dir = tmp_path / "projects"
    monkeypatch.setenv("SPECTRE_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("SPECTRE_LOG_DIR", str(log_dir))
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

"""Test-only composition helper for constructing the application window."""

from core.container import ServiceContainer
from ui.clipboard_monitor import ClipboardMonitor
from ui.main_window import MainWindow


def create_main_window(**services) -> MainWindow:
    """Build a ``MainWindow`` with isolated or explicitly supplied services."""
    if services:
        clipboard_history = services.pop("clipboard_watcher")
        container = ServiceContainer.from_services(
            **services,
            clipboard_history=clipboard_history,
            clipboard_monitor_factory=ClipboardMonitor,
        )
    else:
        container = ServiceContainer.create_isolated_test_container(
            clipboard_monitor_factory=ClipboardMonitor
        )
    return MainWindow(container=container)

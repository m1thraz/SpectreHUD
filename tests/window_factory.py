"""Test-only composition helper for constructing the application window."""

from core.container import ServiceContainer
from ui.main_window import MainWindow


def create_main_window(**services) -> MainWindow:
    """Build a ``MainWindow`` with isolated or explicitly supplied services."""
    if services:
        container = ServiceContainer.from_services(**services)
    else:
        container = ServiceContainer.create_isolated_test_container()
    return MainWindow(container=container)

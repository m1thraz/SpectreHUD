"""
SpectreHUD UI Coordinators.

Provides modular coordinators for Workspaces, Navigation, Clipboard, and Export workflows.
"""

from ui.coordinators.workspace_coordinator import WorkspaceCoordinator
from ui.coordinators.navigation_coordinator import NavigationCoordinator
from ui.coordinators.clipboard_coordinator import ClipboardCoordinator
from ui.coordinators.export_coordinator import ExportCoordinator

__all__ = [
    "WorkspaceCoordinator",
    "NavigationCoordinator",
    "ClipboardCoordinator",
    "ExportCoordinator",
]

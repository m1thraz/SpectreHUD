"""Central QApplication lifecycle for isolated Qt probe subprocesses."""

from PyQt6.QtWidgets import QApplication


def create_probe_application() -> QApplication:
    """Create the process-local application used by a standalone probe."""
    return QApplication.instance() or QApplication([])

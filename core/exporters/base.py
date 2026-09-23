"""UI-free primitives shared by external exporters."""

from core.reporting import (
    ExportArtifact,
    ExportError,
    ExportErrorCode,
    ExportResult,
    ExportStatus,
)


class ExternalExportError(RuntimeError):
    """Raised when an external export cannot be completed safely."""


__all__ = [
    "ExportArtifact",
    "ExportError",
    "ExportErrorCode",
    "ExportResult",
    "ExportStatus",
    "ExternalExportError",
]

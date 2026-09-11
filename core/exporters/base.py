"""UI-free contracts shared by external exporters."""

from typing import Protocol

from core.reporting import (
    ExportArtifact,
    ExportError,
    ExportErrorCode,
    ExportResult,
    ExportStatus,
)


class ExternalExportError(RuntimeError):
    """Raised when an external export cannot be completed safely."""


class ExternalExporter(Protocol):
    """Small common boundary for one-way external export adapters."""

    def export_report(self, *args, **kwargs) -> ExportResult: ...

    def append_loot(self, *args, **kwargs) -> ExportResult: ...


__all__ = [
    "ExportArtifact",
    "ExportError",
    "ExportErrorCode",
    "ExportResult",
    "ExportStatus",
    "ExternalExportError",
    "ExternalExporter",
]

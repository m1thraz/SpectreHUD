"""UI-free contracts shared by external exporters."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence


class ExternalExportError(RuntimeError):
    """Raised when an external export cannot be completed safely."""


@dataclass(frozen=True)
class ExportResult:
    """Describes a completed export without exposing any UI concerns."""

    note_path: Path
    attachment_paths: tuple[Path, ...] = ()
    warnings: tuple[str, ...] = ()
    skipped_entry_ids: tuple[str, ...] = ()
    obsidian_uri: str = ""


class ExternalExporter(Protocol):
    """Small common boundary for one-way external export adapters."""

    def export_report(self, *args, **kwargs) -> ExportResult:
        ...

    def append_loot(self, *args, **kwargs) -> ExportResult:
        ...

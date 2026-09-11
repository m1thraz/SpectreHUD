"""UI-free data models and contracts for export results and artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional


class ExportStatus(str, Enum):
    """Lifecycle status of an export operation."""

    SUCCESS = "success"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ExportErrorCode(str, Enum):
    """Categorized error codes for failed exports."""

    DESTINATION_ERROR = "destination_error"
    INVALID_REPORT = "invalid_report"
    MISSING_ASSET = "missing_asset"
    UNSUPPORTED_FORMAT = "unsupported_format"
    INTERNAL_ERROR = "internal_error"
    CONFIG_ERROR = "config_error"


@dataclass(frozen=True)
class ExportArtifact:
    """An individual file produced during an export operation."""

    path: Path
    format: str
    bytes_written: int = 0


@dataclass(frozen=True)
class ExportError:
    """Structured error information when an export fails."""

    code: ExportErrorCode
    message: str
    details: Optional[str] = None


@dataclass(frozen=True, init=False)
class ExportResult:
    """Describes the outcome of an export operation without exposing UI concerns."""

    status: ExportStatus
    artifacts: tuple[ExportArtifact, ...]
    warnings: tuple[str, ...]
    error: Optional[ExportError]
    skipped_entry_ids: tuple[str, ...]
    metadata: dict[str, Any]

    def __init__(
        self,
        status_or_path: ExportStatus | Path | str | None = None,
        artifacts_or_attachments: Iterable[ExportArtifact | Path] = (),
        warnings: Iterable[str] = (),
        *,
        status: Optional[ExportStatus] = None,
        artifacts: Iterable[ExportArtifact] = (),
        error: Optional[ExportError] = None,
        skipped_entry_ids: Iterable[str] = (),
        metadata: Optional[dict[str, Any]] = None,
        note_path: Optional[Path | str] = None,
        attachment_paths: Iterable[Path] = (),
        obsidian_uri: str = "",
    ) -> None:
        object.__setattr__(self, "metadata", dict(metadata or {}))
        object.__setattr__(self, "skipped_entry_ids", tuple(skipped_entry_ids))
        object.__setattr__(self, "warnings", tuple(warnings))

        if obsidian_uri:
            self.metadata["obsidian_uri"] = obsidian_uri

        # Legacy compatibility: ExportResult(note_path, attachment_paths, warnings, ...)
        if isinstance(status_or_path, (Path, str)):
            primary_path = Path(status_or_path)
            fmt = primary_path.suffix.lstrip(".").lower() or "file"
            size = primary_path.stat().st_size if primary_path.exists() else 0
            primary_art = ExportArtifact(path=primary_path, format=fmt, bytes_written=size)

            art_list = [primary_art]
            for att in artifacts_or_attachments:
                att_path = Path(att.path if isinstance(att, ExportArtifact) else att)
                att_fmt = "attachment" if not isinstance(att, ExportArtifact) else att.format
                att_size = att_path.stat().st_size if att_path.exists() else 0
                art_list.append(
                    ExportArtifact(path=att_path, format=att_fmt, bytes_written=att_size)
                )

            object.__setattr__(self, "status", status or ExportStatus.SUCCESS)
            object.__setattr__(self, "artifacts", tuple(art_list))
            object.__setattr__(self, "error", error)
            return

        resolved_status = status or (
            status_or_path if isinstance(status_or_path, ExportStatus) else ExportStatus.SUCCESS
        )
        object.__setattr__(self, "status", resolved_status)
        object.__setattr__(self, "error", error)

        # Build artifacts tuple
        if artifacts:
            object.__setattr__(self, "artifacts", tuple(artifacts))
        elif note_path is not None:
            np = Path(note_path)
            fmt = np.suffix.lstrip(".").lower() or "file"
            size = np.stat().st_size if np.exists() else 0
            art_list = [ExportArtifact(path=np, format=fmt, bytes_written=size)]
            for att in attachment_paths:
                p = Path(att)
                s = p.stat().st_size if p.exists() else 0
                art_list.append(ExportArtifact(path=p, format="attachment", bytes_written=s))
            object.__setattr__(self, "artifacts", tuple(art_list))
        elif artifacts_or_attachments:
            art_list = []
            for item in artifacts_or_attachments:
                if isinstance(item, ExportArtifact):
                    art_list.append(item)
                else:
                    p = Path(item)
                    s = p.stat().st_size if p.exists() else 0
                    art_list.append(ExportArtifact(path=p, format="file", bytes_written=s))
            object.__setattr__(self, "artifacts", tuple(art_list))
        else:
            object.__setattr__(self, "artifacts", ())

    def __bool__(self) -> bool:
        """Evaluate truthiness based on SUCCESS status."""
        return self.status == ExportStatus.SUCCESS

    @property
    def is_success(self) -> bool:
        return self.status == ExportStatus.SUCCESS

    @property
    def is_cancelled(self) -> bool:
        return self.status == ExportStatus.CANCELLED

    @property
    def is_failed(self) -> bool:
        return self.status == ExportStatus.FAILED

    @property
    def primary_artifact(self) -> Optional[ExportArtifact]:
        return self.artifacts[0] if self.artifacts else None

    @property
    def note_path(self) -> Path:
        """Backwards compatibility for callers expecting `result.note_path`."""
        if self.artifacts:
            return self.artifacts[0].path
        return Path()

    @property
    def attachment_paths(self) -> tuple[Path, ...]:
        """Backwards compatibility for callers expecting `result.attachment_paths`."""
        return tuple(a.path for a in self.artifacts[1:] if a.format in ("image", "attachment"))

    @property
    def obsidian_uri(self) -> str:
        """Backwards compatibility for callers expecting `result.obsidian_uri`."""
        return str(self.metadata.get("obsidian_uri", ""))

    @classmethod
    def success(
        cls,
        artifacts: Iterable[ExportArtifact] = (),
        warnings: Iterable[str] = (),
        skipped_entry_ids: Iterable[str] = (),
        metadata: Optional[dict[str, Any]] = None,
    ) -> ExportResult:
        return cls(
            status=ExportStatus.SUCCESS,
            artifacts=artifacts,
            warnings=warnings,
            skipped_entry_ids=skipped_entry_ids,
            metadata=metadata,
        )

    @classmethod
    def failure(
        cls,
        error: ExportError,
        artifacts: Iterable[ExportArtifact] = (),
        warnings: Iterable[str] = (),
        metadata: Optional[dict[str, Any]] = None,
    ) -> ExportResult:
        return cls(
            status=ExportStatus.FAILED,
            error=error,
            artifacts=artifacts,
            warnings=warnings,
            metadata=metadata,
        )

    @classmethod
    def cancelled(
        cls,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ExportResult:
        return cls(
            status=ExportStatus.CANCELLED,
            metadata=metadata,
        )

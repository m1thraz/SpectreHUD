"""UI-free data models and contracts for export results and artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class ExportResult:
    """Describes the outcome of an export operation without exposing UI concerns."""

    status: ExportStatus
    artifacts: tuple[ExportArtifact, ...] = ()
    warnings: tuple[str, ...] = ()
    error: Optional[ExportError] = None
    skipped_entry_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Results cross plugin boundaries, so normalize mutable caller-owned collections.
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "skipped_entry_ids", tuple(self.skipped_entry_ids))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

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
            artifacts=tuple(artifacts),
            warnings=tuple(warnings),
            skipped_entry_ids=tuple(skipped_entry_ids),
            metadata=dict(metadata or {}),
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
            artifacts=tuple(artifacts),
            warnings=tuple(warnings),
            metadata=dict(metadata or {}),
        )

    @classmethod
    def cancelled(
        cls,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ExportResult:
        return cls(
            status=ExportStatus.CANCELLED,
            metadata=dict(metadata or {}),
        )

"""Typed outcomes shared by project persistence transactions."""

import errno
from dataclasses import dataclass
from enum import Enum
from typing import Generic, Optional, TypeVar


T = TypeVar("T")


class PersistFailureReason(str, Enum):
    IO_ERROR = "io_error"
    VALIDATION_FAILED = "validation_failed"
    DISK_FULL = "disk_full"
    PERMISSION_DENIED = "permission_denied"
    SCHEMA_MISMATCH = "schema_mismatch"
    PROJECT_LOCKED = "project_locked"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PersistResult(Generic[T]):
    success: bool
    failure_reason: Optional[PersistFailureReason] = None
    rollback_performed: bool = False
    value: Optional[T] = None

    def __post_init__(self) -> None:
        if self.success and self.failure_reason is not None:
            raise ValueError("Successful persistence results cannot have a failure reason.")
        if not self.success and self.failure_reason is None:
            raise ValueError("Failed persistence results require a failure reason.")

    @classmethod
    def ok(cls, value: Optional[T] = None) -> "PersistResult[T]":
        return cls(success=True, value=value)

    @classmethod
    def failed(
        cls,
        reason: PersistFailureReason,
        *,
        rollback_performed: bool = False,
    ) -> "PersistResult[T]":
        return cls(
            success=False,
            failure_reason=reason,
            rollback_performed=rollback_performed,
        )


def classify_persistence_error(error: BaseException) -> PersistFailureReason:
    if isinstance(error, PermissionError):
        return PersistFailureReason.PERMISSION_DENIED
    if isinstance(error, OSError):
        if error.errno == errno.ENOSPC:
            return PersistFailureReason.DISK_FULL
        return PersistFailureReason.IO_ERROR
    if isinstance(error, (TypeError, ValueError, UnicodeError, RecursionError)):
        return PersistFailureReason.VALIDATION_FAILED
    return PersistFailureReason.UNKNOWN

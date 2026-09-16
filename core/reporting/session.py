"""Headless lifecycle boundary for an editable project report session."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from core.reporting.draft_manager import (
    discard_draft as discard_recovery_draft,
    get_draft,
    has_recoverable_draft,
    save_draft as save_recovery_draft,
)
from core.reporting.file_manager import ReportFileManager


class ReportPersistFailureReason(str, Enum):
    """Machine-readable reason why report persistence did not complete."""

    WRITE_REJECTED = "write_rejected"
    UNEXPECTED_ERROR = "unexpected_error"


@dataclass(frozen=True)
class ReportPersistResult:
    """Outcome returned by report and recovery-draft writes."""

    success: bool
    failure_reason: Optional[ReportPersistFailureReason] = None
    detail: str = ""

    @classmethod
    def succeeded(cls) -> "ReportPersistResult":
        return cls(success=True)

    @classmethod
    def failed(
        cls, reason: ReportPersistFailureReason, *, detail: str = ""
    ) -> "ReportPersistResult":
        return cls(success=False, failure_reason=reason, detail=detail)


@dataclass(frozen=True)
class ReportRecoveryDraft:
    """Recoverable Markdown plus the timestamp displayed by the UI."""

    markdown: str
    saved_at: datetime


@dataclass(frozen=True)
class ReportLoadState:
    """Disk-backed state needed to initialize an editor session."""

    project_name: str
    project_dir: Path
    markdown: str
    recovery_draft: Optional[ReportRecoveryDraft] = None


class ReportSessionService:
    """Coordinates report.md and crash-recovery persistence without UI policy."""

    def __init__(self, file_manager: ReportFileManager):
        self._file_manager = file_manager

    def load_project(self, project_name: str) -> ReportLoadState:
        project_dir = self._file_manager.project_manager.get_project_dir(project_name)
        markdown = self._file_manager.load(project_name)
        recovery_draft = None
        if has_recoverable_draft(project_dir, markdown):
            draft = get_draft(project_dir)
            if draft is not None:
                recovery_draft = ReportRecoveryDraft(markdown=draft[0], saved_at=draft[1])
        return ReportLoadState(
            project_name=project_name,
            project_dir=project_dir,
            markdown=markdown,
            recovery_draft=recovery_draft,
        )

    def save_document(
        self, project_name: str, markdown: str, *, clear_recovery_draft: bool
    ) -> ReportPersistResult:
        try:
            if not self._file_manager.save(markdown, project_name=project_name):
                return ReportPersistResult.failed(ReportPersistFailureReason.WRITE_REJECTED)
            if clear_recovery_draft:
                project_dir = self._file_manager.project_manager.get_project_dir(project_name)
                discard_recovery_draft(project_dir)
        except Exception as exc:
            return ReportPersistResult.failed(
                ReportPersistFailureReason.UNEXPECTED_ERROR,
                detail=str(exc),
            )
        return ReportPersistResult.succeeded()

    def save_draft(self, project_name: str, markdown: str) -> ReportPersistResult:
        try:
            project_dir = self._file_manager.project_manager.get_project_dir(project_name)
            if not save_recovery_draft(project_dir, markdown):
                return ReportPersistResult.failed(ReportPersistFailureReason.WRITE_REJECTED)
        except Exception as exc:
            return ReportPersistResult.failed(
                ReportPersistFailureReason.UNEXPECTED_ERROR,
                detail=str(exc),
            )
        return ReportPersistResult.succeeded()

    @staticmethod
    def discard_draft(project_dir: Path) -> bool:
        return discard_recovery_draft(project_dir)

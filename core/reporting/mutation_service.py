"""Typed, headless boundary for persisted report-content mutations."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from core.reporting.file_manager import (
    ReportBackupError,
    ReportFileManager,
    ReportReadError,
    ReportSaveError,
)
from core.reporting.loot_sync import LootReportState, classify_loot_report_state
from core.reporting.loot_reconciliation import (
    LootReconciliationAction,
    LootReconciliationError,
    LootReconciliationItem,
    LootReconciliationSelection,
    analyze_loot_reconciliation,
)


class ReportMutationFailureReason(str, Enum):
    """Machine-readable reason why a report mutation did not complete."""

    BACKUP_FAILED = "backup_failed"
    READ_FAILED = "read_failed"
    SAVE_FAILED = "save_failed"
    RECONCILIATION_CHANGED = "reconciliation_changed"
    UNEXPECTED_ERROR = "unexpected_error"


@dataclass(frozen=True)
class ReportMutationResult:
    """Result shared by replacement and additive report mutations."""

    success: bool
    content: str = ""
    added_count: int = 0
    resolved_count: int = 0
    replaced_count: int = 0
    accepted_count: int = 0
    duplicated_count: int = 0
    detached_count: int = 0
    deleted_count: int = 0
    used_fallback: bool = False
    fallback_categories: tuple[str, ...] = ()
    failure_reason: Optional[ReportMutationFailureReason] = None
    detail: str = ""

    @classmethod
    def failed(
        cls, reason: ReportMutationFailureReason, *, detail: str = ""
    ) -> "ReportMutationResult":
        return cls(success=False, failure_reason=reason, detail=detail)


class ReportMutationService:
    """Runs destructive or additive mutations while preserving file-manager safety."""

    def __init__(self, file_manager: ReportFileManager):
        self._file_manager = file_manager

    def has_report(self, project_name: str) -> bool:
        return self._file_manager.exists(project_name)

    def regenerate(
        self,
        *,
        project_name: str,
        loot_manager: Any,
        clipboard_history: Any,
        template: Any = None,
    ) -> ReportMutationResult:
        try:
            content = self._file_manager.regenerate(
                loot_manager,
                clipboard_history,
                project_name=project_name,
                template=template,
            )
        except ReportBackupError as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.BACKUP_FAILED, detail=str(exc)
            )
        except ReportReadError as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.READ_FAILED, detail=str(exc)
            )
        except ReportSaveError as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.SAVE_FAILED, detail=str(exc)
            )
        except Exception as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.UNEXPECTED_ERROR, detail=str(exc)
            )
        return ReportMutationResult(success=True, content=content)

    def append_missing_loot(
        self,
        *,
        project_name: str,
        loot_manager: Any,
        template: Any = None,
    ) -> ReportMutationResult:
        try:
            result = self._file_manager.append_missing_loot(
                loot_manager,
                project_name=project_name,
                template=template,
            )
        except ReportBackupError as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.BACKUP_FAILED, detail=str(exc)
            )
        except ReportReadError as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.READ_FAILED, detail=str(exc)
            )
        except ReportSaveError as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.SAVE_FAILED, detail=str(exc)
            )
        except Exception as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.UNEXPECTED_ERROR, detail=str(exc)
            )
        return ReportMutationResult(
            success=True,
            content=result.content,
            added_count=result.added_count,
            used_fallback=result.used_fallback,
            fallback_categories=result.fallback_categories,
        )

    def reconcile_loot(
        self,
        *,
        project_name: str,
        loot_manager: Any,
        decisions: dict[str, LootReconciliationAction | LootReconciliationSelection | str],
        append_missing: bool = False,
        template: Any = None,
    ) -> ReportMutationResult:
        try:
            result = self._file_manager.reconcile_loot(
                loot_manager,
                decisions,
                append_missing=append_missing,
                project_name=project_name,
                template=template,
            )
        except LootReconciliationError as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.RECONCILIATION_CHANGED, detail=str(exc)
            )
        except ReportBackupError as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.BACKUP_FAILED, detail=str(exc)
            )
        except ReportReadError as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.READ_FAILED, detail=str(exc)
            )
        except ReportSaveError as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.SAVE_FAILED, detail=str(exc)
            )
        except Exception as exc:
            return ReportMutationResult.failed(
                ReportMutationFailureReason.UNEXPECTED_ERROR, detail=str(exc)
            )
        return ReportMutationResult(
            success=True,
            content=result.text,
            added_count=result.added_count,
            resolved_count=result.resolved_count,
            replaced_count=result.replaced_count,
            accepted_count=result.accepted_count,
            duplicated_count=result.duplicated_count,
            detached_count=result.detached_count,
            deleted_count=result.deleted_count,
            used_fallback=result.used_fallback,
            fallback_categories=result.fallback_categories,
        )

    @staticmethod
    def compare_loot(markdown: str, loot_manager: Any) -> LootReportState:
        entries = loot_manager.get_all_entries() if loot_manager is not None else []
        return classify_loot_report_state(markdown, entries)

    @staticmethod
    def describe_loot_differences(
        markdown: str, loot_manager: Any
    ) -> tuple[LootReconciliationItem, ...]:
        entries = loot_manager.get_all_entries() if loot_manager is not None else []
        return analyze_loot_reconciliation(markdown, entries)

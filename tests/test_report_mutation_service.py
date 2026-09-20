"""Headless tests for typed report-content mutations."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.reporting import (
    LootReconciliationError,
    ReportBackupError,
    ReportFileManager,
    ReportMutationFailureReason,
    ReportMutationService,
    ReportReadError,
    ReportReadResult,
    ReportReadStatus,
    ReportSaveError,
)


def _read_error() -> ReportReadError:
    return ReportReadError(
        ReportReadResult(
            ReportReadStatus.READ_FAILED,
            Path("report.md"),
            detail="access denied",
        )
    )


@pytest.fixture
def dependencies() -> tuple[ReportMutationService, MagicMock]:
    file_manager = MagicMock(spec=ReportFileManager)
    return ReportMutationService(file_manager), file_manager


def test_regenerate_returns_persisted_content(dependencies) -> None:
    service, file_manager = dependencies
    file_manager.regenerate.return_value = "# Generated"

    result = service.regenerate(
        project_name="Box",
        loot_manager="loot",
        clipboard_history="history",
        template="template",
    )

    assert result.success
    assert result.content == "# Generated"
    file_manager.regenerate.assert_called_once_with(
        "loot", "history", project_name="Box", template="template"
    )


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ReportBackupError("backup"), ReportMutationFailureReason.BACKUP_FAILED),
        (_read_error(), ReportMutationFailureReason.READ_FAILED),
        (ReportSaveError("save"), ReportMutationFailureReason.SAVE_FAILED),
        (RuntimeError("unexpected"), ReportMutationFailureReason.UNEXPECTED_ERROR),
    ],
)
def test_regenerate_maps_failures(dependencies, error, reason) -> None:
    service, file_manager = dependencies
    file_manager.regenerate.side_effect = error

    result = service.regenerate(project_name="Box", loot_manager=None, clipboard_history=None)

    assert not result.success
    assert result.failure_reason is reason
    assert result.detail == str(error)


def test_append_missing_loot_preserves_result_metadata(dependencies) -> None:
    service, file_manager = dependencies
    file_manager.append_missing_loot.return_value = MagicMock(
        content="# Updated",
        added_count=2,
        used_fallback=True,
        fallback_categories=("custom",),
    )

    result = service.append_missing_loot(
        project_name="Box", loot_manager="loot", template="template"
    )

    assert result.success
    assert result.content == "# Updated"
    assert result.added_count == 2
    assert result.used_fallback
    assert result.fallback_categories == ("custom",)


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ReportBackupError("backup"), ReportMutationFailureReason.BACKUP_FAILED),
        (_read_error(), ReportMutationFailureReason.READ_FAILED),
        (ReportSaveError("save"), ReportMutationFailureReason.SAVE_FAILED),
        (RuntimeError("unexpected"), ReportMutationFailureReason.UNEXPECTED_ERROR),
    ],
)
def test_append_missing_loot_maps_failures(dependencies, error, reason) -> None:
    service, file_manager = dependencies
    file_manager.append_missing_loot.side_effect = error

    result = service.append_missing_loot(project_name="Box", loot_manager=None)

    assert not result.success
    assert result.failure_reason is reason
    assert result.detail == str(error)


def test_compare_loot_uses_current_manager_entries(dependencies) -> None:
    service, _ = dependencies
    loot_manager = MagicMock()
    loot_manager.get_all_entries.return_value = [
        {"id": "loot-1", "title": "Nmap", "content": "22/tcp open"}
    ]

    state = service.compare_loot("# Report", loot_manager)

    assert len(state.missing) == 1


def test_reconcile_loot_preserves_typed_counts(dependencies) -> None:
    service, file_manager = dependencies
    file_manager.reconcile_loot.return_value = MagicMock(
        text="# Reconciled",
        added_count=1,
        resolved_count=2,
        replaced_count=1,
        accepted_count=0,
        duplicated_count=0,
        detached_count=1,
        deleted_count=0,
        used_fallback=False,
        fallback_categories=(),
    )

    result = service.reconcile_loot(
        project_name="Box",
        loot_manager="loot",
        decisions={"loot-1": "apply_loot"},
        append_missing=True,
        template="template",
    )

    assert result.success
    assert result.content == "# Reconciled"
    assert result.resolved_count == 2
    assert result.replaced_count == 1
    assert result.detached_count == 1
    assert result.added_count == 1


def test_reconcile_loot_maps_changed_review_state(dependencies) -> None:
    service, file_manager = dependencies
    file_manager.reconcile_loot.side_effect = LootReconciliationError("changed")

    result = service.reconcile_loot(project_name="Box", loot_manager="loot", decisions={})

    assert not result.success
    assert result.failure_reason is ReportMutationFailureReason.RECONCILIATION_CHANGED


def test_reconcile_loot_maps_report_read_failure(dependencies) -> None:
    service, file_manager = dependencies
    file_manager.reconcile_loot.side_effect = _read_error()

    result = service.reconcile_loot(project_name="Box", loot_manager="loot", decisions={})

    assert not result.success
    assert result.failure_reason is ReportMutationFailureReason.READ_FAILED

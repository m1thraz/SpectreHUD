"""Headless tests for the editable report session lifecycle."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.reporting import (
    DraftDiscardResult,
    DraftDiscardStatus,
    ReportFileManager,
    ReportPersistFailureReason,
    ReportReadError,
    ReportReadResult,
    ReportReadStatus,
    ReportSessionService,
)


def _service(project_dir: Path) -> tuple[ReportSessionService, MagicMock]:
    file_manager = MagicMock(spec=ReportFileManager)
    file_manager.project_manager = MagicMock()
    file_manager.project_manager.get_project_dir.return_value = project_dir
    return ReportSessionService(file_manager), file_manager


def test_load_project_exposes_saved_markdown_without_recovery(tmp_path: Path) -> None:
    service, file_manager = _service(tmp_path)
    file_manager.load.return_value = "# Saved"

    state = service.load_project("Box")

    assert state.project_name == "Box"
    assert state.project_dir == tmp_path
    assert state.markdown == "# Saved"
    assert state.recovery_draft is None


def test_load_project_exposes_recoverable_draft(tmp_path: Path) -> None:
    service, file_manager = _service(tmp_path)
    file_manager.load.return_value = "# Saved"
    saved_at = datetime(2026, 9, 13, 12, 30)

    with (
        patch("core.reporting.session.has_recoverable_draft", return_value=True),
        patch("core.reporting.session.get_draft", return_value=("# Draft", saved_at)),
    ):
        state = service.load_project("Box")

    assert state.recovery_draft is not None
    assert state.recovery_draft.markdown == "# Draft"
    assert state.recovery_draft.saved_at == saved_at


def test_load_project_propagates_report_read_failure(tmp_path: Path) -> None:
    service, file_manager = _service(tmp_path)
    failure = ReportReadError(
        ReportReadResult(
            ReportReadStatus.READ_FAILED,
            tmp_path / "report.md",
            detail="mount unavailable",
        )
    )
    file_manager.load.side_effect = failure

    with (
        patch("core.reporting.session.has_recoverable_draft") as has_draft,
        pytest.raises(ReportReadError),
    ):
        service.load_project("Box")

    has_draft.assert_not_called()


def test_manual_save_clears_recovery_draft_after_success(tmp_path: Path) -> None:
    service, file_manager = _service(tmp_path)
    file_manager.save.return_value = True

    cleanup = DraftDiscardResult(DraftDiscardStatus.REMOVED, tmp_path / ".report.md.draft")
    with patch("core.reporting.session.discard_recovery_draft", return_value=cleanup) as discard:
        result = service.save_document("Box", "# Updated", clear_recovery_draft=True)

    assert result.success
    file_manager.save.assert_called_once_with("# Updated", project_name="Box")
    discard.assert_called_once_with(tmp_path)
    assert result.draft_cleanup is cleanup


def test_manual_save_succeeds_but_reports_failed_draft_cleanup(tmp_path: Path) -> None:
    service, file_manager = _service(tmp_path)
    file_manager.save.return_value = True
    cleanup = DraftDiscardResult(
        DraftDiscardStatus.FAILED,
        tmp_path / ".report.md.draft",
        detail="access denied",
    )

    with patch("core.reporting.session.discard_recovery_draft", return_value=cleanup):
        result = service.save_document("Box", "# Updated", clear_recovery_draft=True)

    assert result.success
    assert result.draft_cleanup is cleanup


def test_cleanup_exception_does_not_turn_completed_report_save_into_failure(
    tmp_path: Path,
) -> None:
    service, file_manager = _service(tmp_path)
    file_manager.save.return_value = True

    with patch(
        "core.reporting.session.discard_recovery_draft",
        side_effect=RuntimeError("unexpected cleanup failure"),
    ):
        result = service.save_document("Box", "# Updated", clear_recovery_draft=True)

    assert result.success
    assert result.draft_cleanup is not None
    assert result.draft_cleanup.status is DraftDiscardStatus.FAILED
    assert result.draft_cleanup.detail == "unexpected cleanup failure"


def test_autosave_keeps_recovery_draft_after_success(tmp_path: Path) -> None:
    service, file_manager = _service(tmp_path)
    file_manager.save.return_value = True

    with patch("core.reporting.session.discard_recovery_draft") as discard:
        result = service.save_document("Box", "# Updated", clear_recovery_draft=False)

    assert result.success
    discard.assert_not_called()


def test_rejected_save_has_typed_failure(tmp_path: Path) -> None:
    service, file_manager = _service(tmp_path)
    file_manager.save.return_value = False

    result = service.save_document("Box", "# Updated", clear_recovery_draft=True)

    assert not result.success
    assert result.failure_reason is ReportPersistFailureReason.WRITE_REJECTED


def test_unexpected_save_error_has_typed_failure(tmp_path: Path) -> None:
    service, file_manager = _service(tmp_path)
    file_manager.save.side_effect = RuntimeError("disk offline")

    result = service.save_document("Box", "# Updated", clear_recovery_draft=True)

    assert not result.success
    assert result.failure_reason is ReportPersistFailureReason.UNEXPECTED_ERROR
    assert result.detail == "disk offline"


def test_draft_snapshot_reports_write_rejection(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)

    with patch("core.reporting.session.save_recovery_draft", return_value=False):
        result = service.save_draft("Box", "# In flight")

    assert not result.success
    assert result.failure_reason is ReportPersistFailureReason.WRITE_REJECTED

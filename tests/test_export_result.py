"""Tests for the unified export outcome model (ExportResult, ExportArtifact, etc.)."""

from pathlib import Path
import pytest

from core.reporting import (
    ExportArtifact,
    ExportError,
    ExportErrorCode,
    ExportResult,
    ExportStatus,
)


def test_export_result_success_creation():
    art = ExportArtifact(path=Path("/tmp/report.html"), format="html", bytes_written=1024)
    res = ExportResult.success(
        artifacts=[art],
        warnings=["Non-critical warning"],
        metadata={"custom_key": 42},
    )

    assert res.is_success is True
    assert res.is_failed is False
    assert res.is_cancelled is False
    assert res.status == ExportStatus.SUCCESS
    assert bool(res) is True
    assert res.primary_artifact == art
    assert res.warnings == ("Non-critical warning",)
    assert res.metadata["custom_key"] == 42
    assert res.error is None


def test_export_result_failure_creation():
    err = ExportError(
        code=ExportErrorCode.DESTINATION_ERROR,
        message="Cannot write destination",
        details="Permission denied",
    )
    res = ExportResult.failure(error=err)

    assert res.is_success is False
    assert res.is_failed is True
    assert res.is_cancelled is False
    assert res.status == ExportStatus.FAILED
    assert bool(res) is False
    assert res.error == err
    assert res.error.code == ExportErrorCode.DESTINATION_ERROR
    assert res.error.message == "Cannot write destination"
    assert res.error.details == "Permission denied"


def test_export_result_cancelled_creation():
    res = ExportResult.cancelled()

    assert res.is_success is False
    assert res.is_failed is False
    assert res.is_cancelled is True
    assert res.status == ExportStatus.CANCELLED
    assert bool(res) is False
    assert res.error is None


def test_export_result_normalizes_boundary_collections():
    artifact = ExportArtifact(path=Path("/vault/notes/Forest.md"), format="markdown")
    metadata = {"suggested_open_uri": "obsidian://open?vault=Vault&file=Forest"}

    res = ExportResult(
        status=ExportStatus.SUCCESS,
        artifacts=[artifact],  # type: ignore[arg-type]
        warnings=["Warning 1"],  # type: ignore[arg-type]
        skipped_entry_ids=["loot-1"],  # type: ignore[arg-type]
        metadata=metadata,
    )
    metadata.clear()

    assert res.artifacts == (artifact,)
    assert res.warnings == ("Warning 1",)
    assert res.skipped_entry_ids == ("loot-1",)
    assert res.metadata == {
        "suggested_open_uri": "obsidian://open?vault=Vault&file=Forest"
    }


def test_export_artifact_frozen():
    art = ExportArtifact(path=Path("/tmp/test.html"), format="html", bytes_written=50)
    with pytest.raises(Exception):
        art.bytes_written = 100  # type: ignore[misc]

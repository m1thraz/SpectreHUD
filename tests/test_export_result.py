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
    assert res.note_path == Path("/tmp/report.html")
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


def test_export_result_legacy_positional_compatibility():
    note = Path("/vault/notes/Forest.md")
    att1 = Path("/vault/notes/attachments/p1.png")
    att2 = Path("/vault/notes/attachments/p2.png")

    res = ExportResult(
        note,
        [att1, att2],
        ["Warning 1"],
        obsidian_uri="obsidian://open?vault=Vault&file=Forest",
    )

    assert res.is_success is True
    assert bool(res) is True
    assert res.note_path == note
    assert res.attachment_paths == (att1, att2)
    assert res.warnings == ("Warning 1",)
    assert res.obsidian_uri == "obsidian://open?vault=Vault&file=Forest"
    assert len(res.artifacts) == 3
    assert res.artifacts[0].path == note
    assert res.artifacts[1].path == att1


def test_export_artifact_frozen():
    art = ExportArtifact(path=Path("/tmp/test.html"), format="html", bytes_written=50)
    with pytest.raises(Exception):
        art.bytes_written = 100  # type: ignore[misc]

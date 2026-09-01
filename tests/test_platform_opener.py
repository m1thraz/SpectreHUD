"""Tests for opening local paths without launching a real desktop application."""

from pathlib import Path
from unittest.mock import patch

from core.platform.opener import open_path


def test_open_path_opens_existing_file_with_local_qt_url(tmp_path):
    target = tmp_path / "report.html"
    target.write_text("report", encoding="utf-8")

    with patch("PyQt6.QtGui.QDesktopServices.openUrl", return_value=True) as opener:
        assert open_path(target) is True

    url = opener.call_args.args[0]
    assert url.isLocalFile()
    assert Path(url.toLocalFile()).resolve() == target.resolve()


def test_open_path_opens_existing_directory_with_local_qt_url(tmp_path):
    target = tmp_path / "project"
    target.mkdir()

    with patch("PyQt6.QtGui.QDesktopServices.openUrl", return_value=True) as opener:
        assert open_path(target) is True

    assert Path(opener.call_args.args[0].toLocalFile()).resolve() == target.resolve()


def test_open_path_rejects_missing_path_without_desktop_call(tmp_path):
    target = tmp_path / "missing"

    with patch("PyQt6.QtGui.QDesktopServices.openUrl") as opener:
        assert open_path(target) is False

    opener.assert_not_called()


def test_open_path_reports_qt_desktop_failure(tmp_path):
    target = tmp_path / "project"
    target.mkdir()

    with patch("PyQt6.QtGui.QDesktopServices.openUrl", return_value=False):
        assert open_path(target) is False


def test_open_path_contains_qt_runtime_failure(tmp_path):
    target = tmp_path / "project"
    target.mkdir()

    with patch(
        "PyQt6.QtGui.QDesktopServices.openUrl",
        side_effect=RuntimeError("desktop service unavailable"),
    ):
        assert open_path(target) is False

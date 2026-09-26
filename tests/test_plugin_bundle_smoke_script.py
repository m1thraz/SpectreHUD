"""Safety tests for the packaged-runtime plugin smoke harness."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from scripts.smoke_test_plugin_bundle import (
    PACKAGED_RUNTIME_TIMEOUT_SECONDS,
    _extract_bundle,
)


pytestmark = pytest.mark.release


def test_packaged_runtime_timeout_allows_cold_native_dependency_scan() -> None:
    assert PACKAGED_RUNTIME_TIMEOUT_SECONDS >= 120


def test_bundle_extraction_rejects_parent_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../outside.txt", "unsafe")

    with pytest.raises(RuntimeError, match="Unsafe path"):
        _extract_bundle(archive, tmp_path / "extracted")

    assert not (tmp_path / "outside.txt").exists()

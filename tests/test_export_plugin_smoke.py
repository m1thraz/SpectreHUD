"""Headless release-smoke coverage for separately distributed export plugins."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from core.plugin_smoke import run_export_plugin_smoke


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCX_PLUGIN_ROOT = PROJECT_ROOT / "plugins-src" / "spectrehud-docx"


def test_smoke_runner_loads_and_executes_external_docx_plugin(tmp_path: Path) -> None:
    result_file = tmp_path / "smoke-result.json"

    exit_code = run_export_plugin_smoke(
        plugin_root=DOCX_PLUGIN_ROOT,
        plugin_id="spectrehud.docx",
        output_dir=tmp_path / "output",
        result_file=result_file,
    )

    payload = json.loads(result_file.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["schema"] == 1
    assert payload["plugin_id"] == "spectrehud.docx"
    assert payload["availability"] == "available"
    assert payload["export_status"] == "success"
    assert len(payload["artifacts"]) == 1
    assert Path(payload["artifacts"][0]).is_file()


def test_smoke_runner_reports_missing_plugin_without_starting_the_gui(
    tmp_path: Path,
) -> None:
    result_file = tmp_path / "smoke-result.json"

    exit_code = run_export_plugin_smoke(
        plugin_root=tmp_path / "empty-plugins",
        plugin_id="spectrehud.missing",
        output_dir=tmp_path / "output",
        result_file=result_file,
    )

    payload = json.loads(result_file.read_text(encoding="utf-8"))
    assert exit_code != 0
    assert payload == {
        "schema": 1,
        "plugin_id": "spectrehud.missing",
        "availability": "not_found",
        "export_status": "not_run",
        "artifacts": [],
        "message": "Export plugin was not discovered.",
    }


def test_smoke_boundary_remains_headless() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import core.plugin_smoke; "
            "assert not any(name.startswith('PyQt6') for name in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

"""Tests for release-critical package metadata."""

from pathlib import Path
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

import pytest


pytestmark = pytest.mark.release


def test_project_metadata_uses_pep_621_compatible_license_table():
    """Setuptools can build the project without downloading a newer backend."""
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")

    from core.cli import APP_VERSION
    assert f'version = "{APP_VERSION}"' in content
    assert 'spectrehud = "spectrehud_launcher:main"' in content
    assert 'license = { text = "MIT" }' in content
    assert 'requires = ["setuptools>=61.0", "wheel"]' in content
    # Release tests build without isolation so they remain usable in restricted CI
    # environments; the active development environment must therefore provide bdist_wheel.
    assert '"wheel>=0.41.0"' in content


def test_windows_spec_includes_runtime_data_directories():
    """Translations, templates, and themes must be present in the one-file EXE."""
    spec = (Path(__file__).parent.parent / "SpectreHUD.spec").read_text(encoding="utf-8")

    assert '(str(data_dir / "i18n"), "data/i18n")' in spec
    assert '(str(data_dir / "report_templates"), "data/report_templates")' in spec
    assert '(str(data_dir / "themes"), "data/themes")' in spec


def test_release_workflow_has_least_privilege_permissions():
    """release.yml must enforce least-privilege permissions at top level and isolate write rights."""
    import re

    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "release.yml"
    content = workflow_path.read_text(encoding="utf-8")

    # Top-level permissions must be read-only (before jobs:)
    header, _, jobs_section = content.partition("jobs:")
    assert re.search(r"^permissions:\s*\r?\n\s+contents:\s*read", header, re.MULTILINE), (
        "Top-level permissions in release.yml must be 'contents: read'"
    )
    assert "contents: write" not in header, "Top-level permissions must not include write rights"

    # Write permissions must be restricted to publish-release
    assert "publish-release:" in jobs_section
    publish_part = jobs_section.split("publish-release:")[1].split("steps:")[0]
    for req_perm in ("contents: write", "id-token: write", "attestations: write"):
        assert req_perm in publish_part, f"publish-release must have {req_perm}"

    # Build jobs must NOT have write permissions
    for job_name in ("verify-version", "build-windows-exe", "build-linux-deb", "build-wheel"):
        job_part = jobs_section.split(f"{job_name}:")[1].split("steps:")[0]
        assert "contents: write" not in job_part, f"{job_name} must not have write permissions"


def test_release_workflow_actions_are_pinned_to_commit_shas():
    """All external GitHub Actions in release.yml must be pinned to immutable 40-character commit SHAs."""
    import re

    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "release.yml"
    lines = workflow_path.read_text(encoding="utf-8").splitlines()

    uses_lines = [line.strip() for line in lines if line.strip().startswith("uses:")]
    assert len(uses_lines) >= 10, "Expected at least 10 action invocations in release.yml"

    sha_pattern = re.compile(r"^uses:\s+([a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+)@([a-f0-9]{40})(\s+#\s+.+)?$")
    for line in uses_lines:
        match = sha_pattern.match(line)
        assert match is not None, f"Action is not pinned to a 40-character commit SHA: {line}"
        # Ensure a human-readable tag/version comment is attached
        assert match.group(3) is not None, f"Action commit SHA lacks version comment: {line}"


def test_all_workflow_actions_are_pinned_to_commit_shas():
    """All external GitHub Actions across all workflows must be pinned to immutable 40-character commit SHAs."""
    import re

    workflows_dir = Path(__file__).parent.parent / ".github" / "workflows"
    workflow_files = sorted(list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml")))
    assert len(workflow_files) >= 3, f"Expected at least 3 workflow files, found {len(workflow_files)}"

    sha_pattern = re.compile(r"^uses:\s+([a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+)@([a-f0-9]{40})(\s+#\s+.+)?$")
    total_actions = 0
    for wf in workflow_files:
        lines = wf.read_text(encoding="utf-8").splitlines()
        uses_lines = [line.strip() for line in lines if line.strip().startswith("uses:")]
        assert uses_lines, f"Workflow {wf.name} has no action invocations"
        for line in uses_lines:
            total_actions += 1
            match = sha_pattern.match(line)
            assert match is not None, f"Action in {wf.name} is not pinned to a 40-character commit SHA: {line}"
            assert match.group(3) is not None, f"Action in {wf.name} commit SHA lacks version comment: {line}"

    assert total_actions >= 20, f"Expected at least 20 action invocations across workflows, found {total_actions}"


def test_release_workflow_includes_supply_chain_artifacts():
    """release.yml must generate SBOM, SHA256 checksums, and signed build provenance attestations."""
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "release.yml"
    content = workflow_path.read_text(encoding="utf-8")

    assert "anchore/sbom-action@" in content
    assert "spectrehud.spdx.json" in content
    assert "sha256sum" in content
    assert "SHA256SUMS" in content
    assert "actions/attest-build-provenance@" in content


def test_release_constraints_pin_dependencies_and_preserve_open_pyproject_bounds():
    """pyproject.toml must keep open bounds while constraints-release.txt provides exact version pins."""
    import tomllib

    repo_root = Path(__file__).parent.parent
    pyproject_path = repo_root / "pyproject.toml"
    constraints_path = repo_root / "constraints-release.txt"

    assert constraints_path.exists(), "constraints-release.txt must exist for reproducible release builds"

    # 1. pyproject.toml maintains open bounds
    pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    runtime_deps = pyproject_data["project"]["dependencies"]
    for dep in runtime_deps:
        assert ">=" in dep, f"pyproject.toml dependency should maintain open lower bound: {dep}"
        assert "==" not in dep, f"pyproject.toml should not pin exact version: {dep}"

    # 2. constraints-release.txt provides exact pins for all runtime dependencies
    constraints_content = constraints_path.read_text(encoding="utf-8")
    expected_pinned_packages = [
        "PyQt6==",
        "PyQt6-Qt6==",
        "PyQt6-sip==",
        "pynput==",
        "pyperclip==",
        "cryptography==",
        "qtawesome==",
        "pyinstaller==",
        "setuptools==",
        "wheel==",
    ]
    for pkg in expected_pinned_packages:
        assert pkg in constraints_content, f"constraints-release.txt missing exact pin for {pkg}"


def test_workflows_install_against_release_constraints():
    """Release workflow and packaging CI jobs must install dependencies against constraints-release.txt."""
    repo_root = Path(__file__).parent.parent
    release_workflow = (repo_root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    ci_workflow = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    # In release.yml, build jobs must use -c constraints-release.txt
    assert "-c constraints-release.txt" in release_workflow

    # In ci.yml, the packaging validation jobs must also use constraints-release.txt
    assert "-c constraints-release.txt" in ci_workflow

    # Wheel builds must enforce pinned build backend via --no-build-isolation
    assert "--no-build-isolation" in release_workflow, "release.yml must build wheel with --no-build-isolation"
    assert "--no-build-isolation" in ci_workflow, "ci.yml must build wheel with --no-build-isolation"


def test_coverage_gate_configuration():
    """Coverage must be enforced as a gate in pyproject.toml and ci.yml."""
    repo_root = Path(__file__).parent.parent
    pyproject_path = repo_root / "pyproject.toml"
    ci_path = repo_root / ".github" / "workflows" / "ci.yml"

    pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    coverage_report = pyproject_data.get("tool", {}).get("coverage", {}).get("report", {})
    assert coverage_report.get("fail_under", 0) >= 80, "Coverage fail_under must be at least 80%"

    ci_content = ci_path.read_text(encoding="utf-8")
    assert "--fail-under=80" in ci_content, "CI workflow must enforce --fail-under=80"


def test_ruff_and_mypy_quality_gates():
    """Ruff must select B and C4 rules and Mypy UI layer must not disable standard typing checks."""
    repo_root = Path(__file__).parent.parent
    pyproject_data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))

    # Ruff rules
    ruff_select = pyproject_data.get("tool", {}).get("ruff", {}).get("lint", {}).get("select", [])
    assert "B" in ruff_select, "Ruff must select B (flake8-bugbear)"
    assert "C4" in ruff_select, "Ruff must select C4 (flake8-comprehensions)"

    # Mypy ui.* overrides
    overrides = pyproject_data.get("tool", {}).get("mypy", {}).get("overrides", [])
    ui_override = next((o for o in overrides if o.get("module") == "ui.*"), None)
    assert ui_override is not None, "Mypy overrides for ui.* must exist"
    disabled = ui_override.get("disable_error_code", [])

    prohibited_disabled = ["call-arg", "func-returns-value", "has-type", "truthy-function", "return-value", "index"]
    for code in prohibited_disabled:
        assert code not in disabled, f"Mypy ui.* must not disable {code}"



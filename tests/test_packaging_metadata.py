"""Tests for release-critical package metadata."""

from pathlib import Path

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
    import yaml

    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "release.yml"
    data = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    # Top-level permissions must be read-only
    assert data.get("permissions") == {"contents": "read"}

    # Write permissions must be restricted to publish-release
    publish_job = data["jobs"]["publish-release"]
    assert publish_job.get("permissions") == {
        "contents": "write",
        "id-token": "write",
        "attestations": "write",
    }

    # Build jobs must NOT have write permissions
    for job_name in ("verify-version", "build-windows-exe", "build-linux-deb", "build-wheel"):
        job = data["jobs"][job_name]
        job_perms = job.get("permissions", {})
        assert job_perms.get("contents") != "write"


def test_release_workflow_actions_are_pinned_to_commit_shas():
    """All external GitHub Actions in release.yml must be pinned to immutable 40-character commit SHAs."""
    import re

    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "release.yml"
    lines = workflow_path.read_text(encoding="utf-8").splitlines()

    uses_lines = [line.strip() for line in lines if line.strip().startswith("uses:")]
    assert len(uses_lines) >= 10, "Expected at least 10 action invocations in release.yml"

    sha_pattern = re.compile(r"^uses:\s+([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)@([a-f0-9]{40})(\s+#\s+.+)?$")
    for line in uses_lines:
        match = sha_pattern.match(line)
        assert match is not None, f"Action is not pinned to a 40-character commit SHA: {line}"
        # Ensure a human-readable tag/version comment is attached
        assert match.group(3) is not None, f"Action commit SHA lacks version comment: {line}"


def test_release_workflow_includes_supply_chain_artifacts():
    """release.yml must generate SBOM, SHA256 checksums, and signed build provenance attestations."""
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "release.yml"
    content = workflow_path.read_text(encoding="utf-8")

    assert "anchore/sbom-action@" in content
    assert "spectrehud.spdx.json" in content
    assert "sha256sum" in content
    assert "SHA256SUMS" in content
    assert "actions/attest-build-provenance@" in content


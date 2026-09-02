"""Tests for release-critical package metadata."""

from pathlib import Path


def test_project_metadata_uses_pep_621_compatible_license_table():
    """Setuptools can build the project without downloading a newer backend."""
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")

    from core.cli import APP_VERSION
    assert f'version = "{APP_VERSION}"' in content
    assert 'spectrehud = "spectrehud_launcher:main"' in content
    assert 'license = { text = "MIT" }' in content
    assert 'requires = ["setuptools>=61.0", "wheel"]' in content


def test_windows_spec_includes_runtime_data_directories():
    """Translations, templates, and themes must be present in the one-file EXE."""
    spec = (Path(__file__).parent.parent / "SpectreHUD.spec").read_text(encoding="utf-8")

    assert '(str(data_dir / "i18n"), "data/i18n")' in spec
    assert '(str(data_dir / "report_templates"), "data/report_templates")' in spec
    assert '(str(data_dir / "themes"), "data/themes")' in spec


def test_ci_keeps_release_tests_and_validates_installed_linux_wheel():
    workflow = (
        Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")
    windows_job, linux_job = workflow.split("\n  package-linux:\n", maxsplit=1)

    assert "python -m pytest -m release" in windows_job
    assert "name: Package validation (Linux, Python 3.11)" in linux_job
    assert "runs-on: ubuntu-latest" in linux_job
    assert "python -m build --wheel" in linux_job
    assert "python scripts/verify_wheel.py dist/" in linux_job
    assert 'python -m venv "$venv_dir"' in linux_job
    assert '"$venv_dir/bin/python" -m pip install "$wheel_path"' in linux_job
    assert 'cd "$RUNNER_TEMP"' in linux_job
    assert '"$venv_dir/bin/spectrehud" --version' in linux_job
    assert '"$venv_dir/bin/spectrehud" --help' in linux_job

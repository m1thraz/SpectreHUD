"""Tests for release-critical package metadata."""

from pathlib import Path


def test_project_metadata_uses_pep_621_compatible_license_table():
    """Setuptools can build the project without downloading a newer backend."""
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")

    assert 'version = "2.0.0"' in content
    assert 'license = { text = "MIT" }' in content
    assert 'requires = ["setuptools>=61.0", "wheel"]' in content


def test_windows_spec_includes_runtime_data_directories():
    """Translations and report templates must be present in the one-file EXE."""
    spec = (Path(__file__).parent.parent / "SpectreHUD.spec").read_text(encoding="utf-8")

    assert '(str(data_dir / "i18n"), "data/i18n")' in spec
    assert '(str(data_dir / "report_templates"), "data/report_templates")' in spec

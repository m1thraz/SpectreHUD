"""Regression tests for the release-wheel verifier."""

from scripts.verify_wheel import REQUIRED_FILES


def test_reporting_template_engine_is_required_instead_of_removed_models_module():
    """Keep the verifier aligned with the reporting package's current layout."""
    assert "core/reporting/template_engine.py" in REQUIRED_FILES
    assert "core/reporting/models.py" not in REQUIRED_FILES

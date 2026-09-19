from pathlib import Path

import pytest

from scripts.stress_test_report_export import SCENARIOS, build_stress_markdown


SOURCE = Path("docs/examples/sample-report-source.md")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda item: item.slug)
def test_stress_scenarios_preserve_structure_and_include_sentinel(scenario):
    source = SOURCE.read_text(encoding="utf-8")

    markdown = build_stress_markdown(source, scenario.slug)

    assert markdown.count("spectre:section:start:") == source.count(
        "spectre:section:start:"
    )
    assert markdown.count("spectre:section:end:") == source.count("spectre:section:end:")
    assert scenario.required_phrase in markdown


def test_unknown_stress_scenario_is_rejected():
    with pytest.raises(ValueError, match="unknown stress scenario"):
        build_stress_markdown("# Report", "missing")


def test_stress_matrix_covers_the_high_risk_print_shapes():
    descriptions = " ".join(scenario.description for scenario in SCENARIOS).lower()

    for expected in ("findings", "table", "code", "attack-path", "screenshots"):
        assert expected in descriptions

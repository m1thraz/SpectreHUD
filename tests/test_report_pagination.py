"""Tests for deterministic Professional Print pagination planning."""

from pathlib import Path

import pytest

from core.reporting import (
    HtmlReportExporter,
    PaginationBlock,
    PaginationPlanner,
    PrintLayoutPolicy,
    ReportExportProfile,
    plan_professional_pagination,
)


def test_planner_moves_atomic_block_to_next_page_when_it_fits_there():
    planner = PaginationPlanner(printable_height_mm=100.0)

    plan = planner.plan(
        (
            PaginationBlock("intro", 75.0),
            PaginationBlock(
                "evidence",
                35.0,
                policy=PrintLayoutPolicy(keep_together=True),
            ),
        )
    )

    assert plan.break_before_ids == ("evidence",)
    assert plan.placements[1].page_number == 2
    assert plan.placements[1].offset_mm == 0.0


def test_planner_reserves_following_content_for_semantic_lead():
    planner = PaginationPlanner(printable_height_mm=100.0)

    plan = planner.plan(
        (
            PaginationBlock("body", 70.0),
            PaginationBlock(
                "finding",
                8.0,
                policy=PrintLayoutPolicy(keep_with_next=True),
                following_height_mm=28.0,
            ),
        )
    )

    assert plan.break_before_ids == ("finding",)
    assert plan.placements[1].page_number == 2


def test_planner_does_not_create_futile_break_for_oversized_atomic_block():
    planner = PaginationPlanner(printable_height_mm=100.0)

    plan = planner.plan(
        (
            PaginationBlock("intro", 20.0),
            PaginationBlock(
                "long-code",
                240.0,
                policy=PrintLayoutPolicy(keep_together=True),
            ),
        )
    )

    assert plan.break_before_ids == ()
    assert plan.placements[1].page_number == 1


def test_planner_honors_explicit_page_start_without_adding_soft_break():
    planner = PaginationPlanner(printable_height_mm=100.0)

    plan = planner.plan(
        (
            PaginationBlock("intro", 60.0),
            PaginationBlock("manual", 0.0, explicit_page_start=True),
            PaginationBlock("next", 30.0),
        )
    )

    assert plan.break_before_ids == ()
    assert plan.placements[1].page_number == 2
    assert plan.placements[2].offset_mm == 0.0


def test_planner_rejects_invalid_measurements_and_duplicate_ids():
    with pytest.raises(ValueError, match="cannot be negative"):
        PaginationBlock("invalid", -1.0)

    with pytest.raises(ValueError, match="Duplicate pagination block id"):
        PaginationPlanner().plan(
            (PaginationBlock("duplicate", 1.0), PaginationBlock("duplicate", 1.0))
        )


def test_html_adapter_adds_idempotent_soft_break_at_finding_boundary():
    html = (
        '<section class="report-section report-findings">'
        "<h2>Technical Findings</h2>"
        f"<p>{'intro ' * 130}</p>"
        '<article class="report-finding">'
        '<div data-print-layout="keep-with-next" class="finding-lead">Finding lead</div>'
        "<p>Finding details.</p>"
        "</article></section>"
    )

    planned = plan_professional_pagination(html, printable_height_mm=100.0)

    assert '<article class="report-finding" data-print-plan="page-start">' in planned
    assert plan_professional_pagination(planned, printable_height_mm=100.0) == planned


def test_html_adapter_allows_medium_finding_to_use_remaining_page_space():
    html = (
        '<section class="report-section report-findings">'
        "<h2>Technical Findings</h2>"
        f"<p>{'context ' * 10}</p>"
        '<article class="report-finding">'
        '<div data-print-layout="keep-with-next" class="finding-lead">Finding lead</div>'
        f"<p>{'finding detail ' * 25}</p>"
        "</article></section>"
    )

    planned = plan_professional_pagination(html, printable_height_mm=115.0)

    assert '<article class="report-finding" data-print-plan="page-start">' not in planned


def test_html_adapter_preserves_manual_break_as_hard_reset():
    html = (
        '<section class="report-section report-scope">'
        f"<p>{'scope ' * 100}</p></section>"
        '<div class="spectre-page-break" contenteditable="false"></div>'
        '<section class="report-section report-remediation">'
        "<h2>Remediation</h2><p>Plan.</p></section>"
    )

    planned = plan_professional_pagination(html, printable_height_mm=100.0)

    assert 'class="spectre-page-break" contenteditable="false"' in planned
    assert '<section class="report-section report-remediation">' in planned


def test_html_adapter_leaves_atomic_fragmentation_to_semantic_css():
    html = (
        f"<p>{'narrative ' * 100}</p>"
        '<pre data-print-layout="keep-together"><code>short evidence</code></pre>'
    )

    planned = plan_professional_pagination(html, printable_height_mm=100.0)

    assert 'data-print-plan="page-start"' not in planned
    assert 'data-print-layout="keep-together"' in planned


def test_sample_without_manual_breaks_keeps_last_finding_lead_with_its_body():
    source_path = Path(__file__).resolve().parents[1] / "docs" / "examples" / "sample-report-source.md"
    markdown = source_path.read_text(encoding="utf-8").replace(
        "<!-- spectre:pagebreak -->", ""
    )

    rendered = HtmlReportExporter.build_full_html(
        markdown,
        project_name="Northstar Research Portal",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )

    last_finding = rendered.split('<article class="report-finding severity-low"', 1)[1]
    assert '<div data-print-layout="keep-with-next" class="finding-lead">' in last_finding


def test_exporter_applies_planner_only_to_professional_profile(monkeypatch):
    calls: list[str] = []

    def record_plan(html: str) -> str:
        calls.append(html)
        return html + "<!-- pagination-planned -->"

    monkeypatch.setattr("core.reporting.exporter.plan_professional_pagination", record_plan)
    markdown = "## Findings\n\nNarrative."

    professional = HtmlReportExporter.build_full_html(
        markdown,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )
    interactive = HtmlReportExporter.build_full_html(markdown)

    assert len(calls) == 1
    assert "pagination-planned" in professional
    assert "pagination-planned" not in interactive
    assert '[data-print-plan~="page-start"]' in professional

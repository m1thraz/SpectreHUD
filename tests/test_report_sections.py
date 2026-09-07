"""Contract tests for persistent report sections and semantic HTML export."""

from core.reporting.exporter import HtmlReportExporter
from core.reporting.profiles import ReportExportProfile
from core.reporting.section_markers import (
    reconcile_section_markers,
    segment_report_markdown,
    wrap_section_markdown,
)
from core.reporting.template_engine import (
    ReportContext,
    ReportTemplate,
    TemplateRenderer,
    TemplateSection,
)
from core.reporting.loot_sync import preserve_markers_in_preview_roundtrip


def _all_sections_template() -> ReportTemplate:
    return ReportTemplate(
        id="sections",
        name="Sections",
        language="en",
        category="pentest",
        complexity="complex",
        sections=[
            TemplateSection("header_metadata"),
            TemplateSection("executive_summary"),
            TemplateSection("scope_limitations"),
            TemplateSection("phase_section", category_id="recon"),
            TemplateSection("remediation_table"),
            TemplateSection("appendix"),
        ],
    )


def test_template_renderer_persists_ordered_section_identity():
    renderer = TemplateRenderer()
    template = _all_sections_template()
    context = ReportContext()
    rendered = renderer.render(template, context)
    expected = [
        "header_metadata",
        "executive_summary",
        "scope_limitations",
        "phase_section:recon",
        "remediation_table",
        "appendix",
    ]

    positions = []
    for identity in expected:
        start = f"<!-- spectre:section:start:{identity} -->"
        end = f"<!-- spectre:section:end:{identity} -->"
        assert start in rendered
        assert end in rendered
        positions.append(rendered.index(start))
    assert positions == sorted(positions)

    structured = [segment for segment in segment_report_markdown(rendered) if segment.is_structured]
    for section, segment in zip(template.sections, structured):
        expected_content = renderer.SECTION_RENDERERS[section.type](section, context, "en").strip()
        assert segment.markdown == expected_content


def test_duplicate_section_identity_uses_report_local_ordinals():
    template = ReportTemplate(
        id="duplicate",
        name="Duplicate",
        language="en",
        category="pentest",
        complexity="complex",
        sections=[TemplateSection("executive_summary"), TemplateSection("executive_summary")],
    )
    rendered = TemplateRenderer().render(template, ReportContext())
    assert "section:start:executive_summary:1" in rendered
    assert "section:start:executive_summary:2" in rendered


def test_segmenter_preserves_sections_and_free_text_exactly():
    first = wrap_section_markdown("## Summary\n\nEdited by user", "executive_summary")
    second = wrap_section_markdown("## Recon\n\nEvidence", "phase_section:recon")
    markdown = f"Preface\n\n{first}\n\nBetween\n\n{second}\n\nAfter"

    segments = segment_report_markdown(markdown)

    assert [segment.markdown for segment in segments if not segment.is_structured] == [
        "Preface\n\n",
        "\nBetween\n\n",
        "\nAfter",
    ]
    structured = [segment for segment in segments if segment.is_structured]
    assert structured[0].section_type == "executive_summary"
    assert structured[0].markdown == "## Summary\n\nEdited by user"
    assert structured[1].category_id == "recon"
    assert structured[1].markdown == "## Recon\n\nEvidence"


def test_segmenter_falls_back_without_losing_malformed_or_unknown_content():
    malformed = "Before\n<!-- spectre:section:start:executive_summary -->\nManual"
    unknown = wrap_section_markdown("Future body", "future_section")

    malformed_segments = segment_report_markdown(malformed)
    unknown_segments = segment_report_markdown(unknown)

    assert "".join(segment.markdown for segment in malformed_segments) == malformed
    assert "".join(segment.markdown for segment in unknown_segments) == unknown
    assert not unknown_segments[0].is_structured


def test_export_profiles_default_to_interactive_and_professional_wraps_semantics():
    markdown = (
        wrap_section_markdown("## Executive\n\nSummary", "executive_summary")
        + "\n\n"
        + wrap_section_markdown("## Recon\n\nFinding", "phase_section:recon")
    )

    default_html = HtmlReportExporter.build_full_html(markdown)
    interactive_html = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.INTERACTIVE
    )
    professional_html = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )

    assert default_html == interactive_html
    assert '<section class="report-section report-executive">' in professional_html
    assert '<section class="report-section report-phase" data-phase="recon">' in professional_html
    assert 'data-report-profile="interactive"' in default_html
    assert 'data-report-profile="professional_print"' in professional_html
    assert "spectre:section" not in default_html
    assert "spectre:section" not in professional_html


def test_legacy_professional_export_preserves_all_content_without_mutation():
    markdown = "Preface\n\n## Legacy section\n\nManual text"
    html = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    assert "Preface" in html
    assert "Legacy section" in html
    assert "Manual text" in html
    assert markdown == "Preface\n\n## Legacy section\n\nManual text"


def test_preview_roundtrip_restores_section_pairs_around_edited_content():
    original = (
        wrap_section_markdown("## Summary\n\nOriginal", "executive_summary")
        + "\n\nManual bridge\n\n"
        + wrap_section_markdown("## Recon\n\nFinding", "phase_section:recon")
    )
    converted = "## Summary\n\nEdited\n\nManual bridge\n\n## Recon\n\nFinding"

    reconciled = reconcile_section_markers(original, converted)

    assert reconciled.index("section:start:executive_summary") < reconciled.index("## Summary")
    assert reconciled.index("section:end:executive_summary") < reconciled.index("Manual bridge")
    assert reconciled.index("section:start:phase_section:recon") < reconciled.index("## Recon")
    assert reconciled.rstrip().endswith("<!-- spectre:section:end:phase_section:recon -->")
    assert "Edited" in reconciled

    full_roundtrip = preserve_markers_in_preview_roundtrip(original, converted)
    assert "section:start:executive_summary" in full_roundtrip
    assert "section:end:phase_section:recon" in full_roundtrip


def test_professional_html_exposes_every_known_section_wrapper():
    markdown = TemplateRenderer().render(_all_sections_template(), ReportContext())
    html = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )

    for css_class in (
        "report-header-metadata",
        "report-executive",
        "report-scope",
        "report-phase",
        "report-remediation",
        "report-appendix",
    ):
        assert f'class="report-section {css_class}"' in html
    assert 'data-phase="recon"' in html
    assert "spectre:section" not in html

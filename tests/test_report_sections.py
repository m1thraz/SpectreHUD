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
    context = ReportContext(
        loot_entries=[
            {
                "id": "loot-recon",
                "category": "recon",
                "type": "note",
                "title": "Open service",
                "content": "TCP/443 is reachable.",
                "severity": "low",
            }
        ]
    )
    markdown = TemplateRenderer().render(_all_sections_template(), context)
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


def test_both_profiles_render_generated_findings_semantically_but_not_legacy_blocks():
    context = ReportContext(
        loot_entries=[
            {
                "id": "loot-access",
                "category": "access",
                "type": "note",
                "title": "Authentication bypass",
                "content": "The endpoint accepted an invalid token.",
                "severity": "high",
                "target_ip": "10.10.10.42",
                "timestamp": "2026-09-07 10:42:00",
            },
            {
                "id": "loot-command",
                "category": "access",
                "type": "note",
                "title": "Long command evidence",
                "content": "```bash\ncurl --request POST https://target.example/"
                "very/long/path --header 'Authorization: Bearer token'\n```",
                "severity": "medium",
                "target_ip": "",
                "timestamp": "",
            },
        ]
    )
    template = ReportTemplate(
        id="finding",
        name="Finding",
        language="en",
        category="pentest",
        complexity="complex",
        sections=[TemplateSection("phase_section", category_id="access")],
    )
    markdown = TemplateRenderer().render(template, context)

    interactive = HtmlReportExporter.build_full_html(markdown)
    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    legacy = HtmlReportExporter.build_full_html(
        "## Initial Access\n\n### Legacy finding\n\nManual content",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )

    for rendered in (interactive, professional):
        assert rendered.count('<article class="report-finding') == 2
        assert '<article class="report-finding severity-high">' in rendered
        assert '<article class="report-finding severity-medium">' in rendered
        assert '<div class="finding-meta">' in rendered
        assert '<section class="finding-description"><h4>Description</h4>' in rendered
        assert '<code class="language-bash">curl --request POST' in rendered
        assert "spectre:finding" not in rendered
        assert "spectre:loot" not in rendered
    assert '<article class="report-finding' not in legacy
    assert "Legacy finding" in legacy


def test_professional_omits_only_empty_phase_sections():
    empty = wrap_section_markdown(
        "## Empty Phase\n\n*No entries captured for this phase.*\n\n"
        "_Notes & observations for this phase:_\n\n> ",
        "phase_section:postex",
    )
    noted = wrap_section_markdown(
        "## Manual Phase\n\n*No entries captured for this phase.*\n\n"
        "_Notes & observations for this phase:_\n\n> Preserve this manual note.",
        "phase_section:misc",
    )
    markdown = empty + "\n\n" + noted

    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    interactive = HtmlReportExporter.build_full_html(markdown)

    assert 'data-phase="postex"' not in professional
    assert "Empty Phase" not in professional
    assert 'data-phase="misc"' in professional
    assert "Preserve this manual note." in professional
    assert "Empty Phase" in interactive


def test_professional_cover_precedes_body_and_is_profile_isolated():
    markdown = wrap_section_markdown(
        """# Security Assessment Report: Atlas

| | |
|---|---|
| **Client / Organization** | `Northwind` |
| **Lead Tester** | `` |
| **Scope / Target** | `10.10.10.42` |
| **Report Date** | `2026-09-07` |
| **Classification** | `Confidential` |""",
        "header_metadata",
    )

    professional = HtmlReportExporter.build_full_html(
        markdown,
        project_name="Atlas",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )
    interactive = HtmlReportExporter.build_full_html(markdown, project_name="Atlas")

    cover_start = professional.index('<section class="report-cover"')
    metadata_start = professional.index('<section class="report-section report-header-metadata">')
    assert cover_start < metadata_start
    assert "break-after: page" in professional
    assert "--report-accent: #315f66" in professional
    assert '<main class="report-body" contenteditable="false"' in professional
    assert "Northwind" in professional
    assert "10.10.10.42" in professional
    assert "Confidential" in professional
    assert "Lead Tester</span>" not in professional
    assert '<section class="report-cover"' not in interactive
    assert "Professional Print is deliberately isolated" not in interactive
    assert '<main class="report-body" contenteditable="true"' in interactive


def test_professional_severity_is_text_only_and_uses_existing_top_severity():
    markdown = wrap_section_markdown(
        """## Executive Summary

### <span class="severity-pill severity-high">🟠 HIGH</span> Finding

**Total:** 🔴 0 Critical · 🟠 1 High · 🟡 0 Medium · 🟢 0 Low""",
        "executive_summary",
    )

    professional = HtmlReportExporter.build_full_html(
        markdown,
        project_name="Atlas",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )
    interactive = HtmlReportExporter.build_full_html(markdown, project_name="Atlas")

    assert '<span class="report-cover-severity severity-high">HIGH</span>' in professional
    assert '<span class="severity-pill severity-high">HIGH</span>' in professional
    assert not any(emoji in professional for emoji in ("🔴", "🟠", "🟡", "🟢", "🔵"))
    assert "🟠 HIGH</span>" in interactive


def test_professional_cover_omits_optional_metadata_when_unavailable():
    markdown = wrap_section_markdown("## Executive Summary\n\nNo findings.", "executive_summary")
    professional = HtmlReportExporter.build_full_html(
        markdown,
        project_name="Atlas",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )

    assert '<h1 class="report-cover-title">Atlas</h1>' in professional
    assert '<div class="report-cover-meta">' not in professional

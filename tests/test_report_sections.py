"""Contract tests for persistent report sections and semantic HTML export."""

from core.reporting import HtmlReportExporter
from core.reporting import ReportExportProfile
from core.reporting import TemplateRepository
from core.reporting import (
    normalize_leading_section_pagebreaks,
    reconcile_section_markers,
    segment_report_markdown,
    wrap_section_markdown,
)
from core.reporting import (
    ReportContext,
    ReportTemplate,
    TemplateRenderer,
    TemplateSection,
)
from core.reporting import preserve_markers_in_preview_roundtrip
from core.reporting import ReportEvidenceItem, ReportFindingItem


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
            TemplateSection("attack_path"),
            TemplateSection("finding_section"),
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
        "attack_path",
        "finding_section",
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
    assert 'class="report-section report-executive" id="executive-summary"' in professional_html
    assert 'class="report-section report-phase" data-phase="recon" id="phase-recon"' in professional_html
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


def test_professional_html_exposes_meaningful_semantic_section_wrappers():
    context = ReportContext(
        loot_entries=[
            {
                "id": "loot-recon",
                "category": "recon",
                "type": "note",
                "title": "Open service",
                "content": "TCP/443 is reachable.",
                "severity": "low",
                "recommendation": "Restrict the service to approved source networks.",
            }
        ]
    )
    markdown = TemplateRenderer().render(_all_sections_template(), context)
    html = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )

    for css_class in (
        "report-executive",
        "report-attack-path",
        "report-findings",
        "report-phase",
        "report-remediation",
    ):
        assert f'class="report-section {css_class}"' in html
    for css_class in ("report-header-metadata", "report-scope", "report-appendix"):
        assert f'class="report-section {css_class}"' not in html
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
                "recommendation": "Reject invalid tokens and rotate signing keys.",
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
        assert '<article class="report-finding severity-high"' in rendered
        assert '<article class="report-finding severity-medium"' in rendered
        assert '<div class="finding-meta">' in rendered
        assert '<section class="finding-description"><h4>Description</h4>' in rendered
        assert '<section class="finding-recommendation"><h4>Recommendation</h4>' in rendered
        assert "Reject invalid tokens and rotate signing keys." in rendered
        assert '<code class="language-bash">curl --request POST' in rendered
        assert "spectre:finding" not in rendered
        assert "spectre:loot" not in rendered
    assert 'class="report-finding severity-high"' in professional
    assert 'id="finding-f-001"' in professional
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


def test_professional_omits_generated_empty_sections_but_interactive_keeps_them():
    renderer = TemplateRenderer()
    template = ReportTemplate(
        id="empty",
        name="Empty",
        language="en",
        category="pentest",
        complexity="complex",
        sections=[
            TemplateSection("executive_summary", title="1. Executive Summary"),
            TemplateSection("scope_limitations", title="2. Scope & Methodology"),
            TemplateSection("attack_path", title="3. Attack Path"),
            TemplateSection("finding_section", title="4. Technical Findings"),
            TemplateSection("remediation_table", title="5. Remediation"),
            TemplateSection("appendix", title="6. Appendix"),
        ],
    )
    markdown = renderer.render(template, ReportContext())

    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    interactive = HtmlReportExporter.build_full_html(markdown)

    for title in (
        "1. Executive Summary",
        "2. Scope &amp; Methodology",
        "3. Attack Path",
        "4. Technical Findings",
        "5. Remediation",
        "6. Appendix",
    ):
        assert title not in professional
    assert "1. Executive Summary" in interactive
    assert "2. Scope &amp; Methodology" in interactive
    assert "No documented attack path is available" in interactive
    assert "No technical findings are documented" in interactive
    assert "No clipboard history recorded" in interactive


def test_professional_prunes_empty_fields_without_hiding_manual_content():
    executive = wrap_section_markdown(
        """## 1. Executive Summary

### Findings Matrix

| # | Finding | Severity | Phase | Status |
|---|---|---|---|---|
| 1 | Authentication bypass | HIGH | access | Open |

**Total:** 0 Critical · 1 High · 0 Medium · 0 Low

### Key Highlights

- **Initial Access Vector:**
- **Business Impact & Risk:**""",
        "executive_summary",
    )
    scope = wrap_section_markdown(
        """## 2. Scope & Methodology

- **In Scope:** Public login endpoint
- **Out of Scope:**
- **Methodology:**
- **Limitations & Constraints:**""",
        "scope_limitations",
    )
    appendix = wrap_section_markdown(
        """## Appendix A: Terminal Command History

#### 1. `10:42:00`
```bash
curl https://target.example
```

## Appendix B: Screenshots

*No screenshots captured in this project.*""",
        "appendix",
    )

    professional = HtmlReportExporter.build_full_html(
        executive + "\n\n" + scope + "\n\n" + appendix,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )

    assert 'class="report-section report-executive"' in professional
    assert "Authentication bypass" in professional
    assert "Key Highlights" not in professional
    assert "Initial Access Vector" not in professional
    assert 'class="report-section report-scope"' in professional
    assert "Public login endpoint" in professional
    assert "Out of Scope" not in professional
    assert 'class="report-section report-appendix"' in professional
    assert "curl https://target.example" in professional
    assert "Appendix B: Screenshots" not in professional


def test_professional_keeps_manual_notes_in_otherwise_empty_sections():
    sections = [
        wrap_section_markdown(
            "## Scope & Methodology\n\nManual scoping note.", "scope_limitations"
        ),
        wrap_section_markdown(
            "## Technical Findings\n\n_Notes & observations for this phase:_\n\n"
            "> Manual finding note.",
            "finding_section",
        ),
        wrap_section_markdown("## Appendix\n\nManual supporting material.", "appendix"),
        wrap_section_markdown(
            "# Security Assessment Report\n\nManual distribution note.",
            "header_metadata",
        ),
    ]

    professional = HtmlReportExporter.build_full_html(
        "\n\n".join(sections), profile=ReportExportProfile.PROFESSIONAL_PRINT
    )

    assert "Manual scoping note." in professional
    assert "Manual finding note." in professional
    assert "Manual supporting material." in professional
    assert "Manual distribution note." in professional


def test_professional_renumbers_only_visible_pentest_sections():
    markdown = "\n\n".join(
        [
            wrap_section_markdown(
                "## 1. Executive Summary\n\nSummary content.", "executive_summary"
            ),
            wrap_section_markdown(
                "## 2. Scope & Methodology\n\n- **In Scope:**",
                "scope_limitations",
            ),
            wrap_section_markdown("## 3. Attack Path\n\n1. Initial access", "attack_path"),
            wrap_section_markdown(
                "## 4. Technical Findings\n\nManual finding context.",
                "finding_section",
            ),
            wrap_section_markdown(
                "## 5. Remediation\n\n| Priority | Recommendation | Affects Finding # |\n"
                "|---|---|---|\n| P2 | Rotate credentials | Finding #1 |",
                "remediation_table",
            ),
        ]
    )

    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )

    assert "1. Executive Summary" in professional
    assert "2. Attack Path" in professional
    assert "3. Technical Findings" in professional
    assert "4. Remediation" in professional
    assert "2. Scope" not in professional
    assert "5. Remediation" not in professional


def test_professional_does_not_renumber_ctf_phase_narrative():
    markdown = "\n\n".join(
        [
            wrap_section_markdown(
                "## 1. Reconnaissance\n\nCaptured evidence.", "phase_section:recon"
            ),
            wrap_section_markdown(
                "## 3. Privilege Escalation\n\nRoot proof.", "phase_section:privesc"
            ),
        ]
    )

    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )

    assert "1. Reconnaissance" in professional
    assert "3. Privilege Escalation" in professional
    assert "2. Privilege Escalation" not in professional


def test_professional_numbering_closes_multiple_suppressed_gaps():
    markdown = "\n\n".join(
        [
            wrap_section_markdown(
                "## 1. Executive Summary\n\nSummary content.", "executive_summary"
            ),
            wrap_section_markdown("## 2. Scope\n\n- **In Scope:**", "scope_limitations"),
            wrap_section_markdown(
                "## 3. Attack Path\n\n*No documented attack path is available.*",
                "attack_path",
            ),
            wrap_section_markdown(
                "## 4. Technical Findings\n\nManual finding content.",
                "finding_section",
            ),
            wrap_section_markdown(
                "## 5. Remediation\n\n| Priority | Recommendation | Affects Finding # |\n"
                "|---|---|---|\n| P2 | Rotate credentials | Finding #1 |",
                "remediation_table",
            ),
        ]
    )

    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )

    assert "1. Executive Summary" in professional
    assert "2. Technical Findings" in professional
    assert "3. Remediation" in professional
    assert "4. Technical Findings" not in professional
    assert "5. Remediation" not in professional


def test_executive_priority_actions_use_only_real_recommendations(tmp_path):
    template = TemplateRepository(user_templates_dir=tmp_path / "templates").get_template(
        "pentest_executive_en"
    )
    context = ReportContext(
        loot_entries=[
            {
                "id": "critical",
                "category": "privesc",
                "type": "note",
                "title": "Writable privileged service",
                "content": "Evidence",
                "severity": "critical",
                "recommendation": "Remove write access from unprivileged users.",
            },
            {
                "id": "high",
                "category": "access",
                "type": "note",
                "title": "Authentication bypass",
                "content": "Evidence",
                "severity": "high",
                "recommendation": "Reject unsigned authentication tokens.",
            },
            {
                "id": "medium",
                "category": "recon",
                "type": "note",
                "title": "Exposed service",
                "content": "Evidence",
                "severity": "medium",
                "recommendation": "",
            },
        ]
    )
    markdown = TemplateRenderer().render(template, context)
    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    action_plan = professional.split('class="report-section report-remediation"', 1)[
        1
    ].split("</section>", 1)[0]

    assert "Writable privileged service" in professional
    assert "Authentication bypass" in professional
    assert "Exposed service" in professional
    assert "Remove write access from unprivileged users." in action_plan
    assert "Reject unsigned authentication tokens." in action_plan
    assert "Exposed service" not in action_plan
    assert action_plan.index("P1") < action_plan.index("P2")


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

    assert professional.index('<section class="report-cover"') >= 0
    assert '<section class="report-section report-header-metadata">' not in professional
    assert "break-after: page" in professional
    assert "--report-accent: #315f66" in professional
    assert '<main class="report-body" contenteditable="true"' in professional
    assert "downloadEditedHtml()" in professional
    assert "Save Edited HTML" in professional
    assert "Northwind" in professional
    assert "10.10.10.42" in professional
    assert "Confidential" in professional
    assert "Lead Tester</span>" not in professional
    assert '<section class="report-cover"' not in interactive
    assert "Security Assessment Report: Atlas" in interactive
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
    assert '<p class="report-severity-total"><strong>Total:</strong>' in professional
    assert ".report-severity-total {" in professional
    assert "font-size: 8.5px;" in professional
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


def test_representative_builtin_reports_follow_distinct_narratives(tmp_path):
    repository = TemplateRepository(user_templates_dir=tmp_path / "templates")
    renderer = TemplateRenderer()
    loot = [
        {
            "id": "recon-1",
            "category": "recon",
            "type": "note",
            "title": "Exposed administration service",
            "content": "TCP/8443 exposed an administration interface.",
            "severity": "medium",
        },
        {
            "id": "access-1",
            "category": "access",
            "type": "flag",
            "title": "Authentication bypass",
            "content": "user.txt",
            "severity": "high",
        },
        {
            "id": "privesc-1",
            "category": "privesc",
            "type": "flag",
            "title": "Privilege escalation",
            "content": "root.txt",
            "severity": "critical",
        },
    ]
    context = ReportContext(
        loot_entries=loot,
        project_name="Atlas",
        target_ip="10.10.10.42",
        metadata={"client": "Northwind", "classification": "Confidential"},
    )

    standard = renderer.render(repository.get_template("pentest_standard_en"), context)
    walkthrough = renderer.render(repository.get_template("ctf_walkthrough_en"), context)
    executive = renderer.render(repository.get_template("pentest_executive_en"), context)

    assert "## 3. Attack Path / Assessment Narrative" in standard
    assert standard.count("## 4. Technical Findings") == 1
    assert "section:start:phase_section" not in standard
    assert "## 1. Reconnaissance & Port Scanning" in walkthrough
    assert "## 2. Initial Access & User Flag" in walkthrough
    assert "user.txt" in walkthrough
    assert "root.txt" in walkthrough
    assert "section:start:attack_path" not in walkthrough
    assert "1. Executive Summary & Findings Overview" in executive
    assert "3. Priority Actions" in executive
    assert "section:start:phase_section" not in executive
    assert "section:start:finding_section" not in executive

    for name, markdown, language in (
        ("pentest-standard", standard, "en"),
        ("ctf-walkthrough", walkthrough, "en"),
        ("pentest-executive", executive, "en"),
    ):
        output_path = tmp_path / f"{name}.html"
        assert HtmlReportExporter.export_to_file(
            markdown,
            output_path,
            project_name="Atlas",
            language=language,
            profile=ReportExportProfile.PROFESSIONAL_PRINT,
        )
        html = output_path.read_text(encoding="utf-8")
        assert 'data-report-profile="professional_print"' in html
        assert "spectre:section" not in html


def test_professional_print_shell_uses_paged_media_without_duplicate_branding():
    markdown = wrap_section_markdown(
        """# Security Assessment Report: Atlas

| | |
|---|---|
| **Classification** | `Confidential` |""",
        "header_metadata",
    )
    markdown += (
        "\n\n---\n\n_Generated with SpectreHUD Pentest & CTF Companion on 2026-09-07 at 16:44:00_"
    )

    professional = HtmlReportExporter.build_full_html(
        markdown,
        project_name="Atlas",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )
    interactive = HtmlReportExporter.build_full_html(markdown, project_name="Atlas")

    assert '@top-left {\n            content: "Atlas";' in professional
    assert '@top-right {\n            content: "Penetration Test Report";' in professional
    assert '@bottom-left {\n            content: "Confidential";' in professional
    assert 'content: "Page " counter(page);' in professional
    assert "@page :first" in professional
    assert '<div class="report-cover-brand">SpectreHUD</div>' in professional
    assert "Generated with SpectreHUD" not in professional
    assert "Generated with SpectreHUD Pentest &amp; CTF Companion" not in professional
    assert '<footer class="report-footer">' not in professional
    assert "Disable browser headers and footers" in professional

    assert '<footer class="report-footer">' in interactive
    assert "Generated with SpectreHUD Pentest &amp; CTF Companion" in interactive
    assert '@top-left {\n            content: "Atlas";' not in interactive
    assert "Disable browser headers and footers" not in interactive


def test_professional_page_metadata_cannot_escape_generated_css():
    professional = HtmlReportExporter.build_full_html(
        "## Summary\n\nContent.",
        project_name='Atlas</style><script>alert("x")</script>',
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )

    assert "</style><script>" not in professional
    assert "Atlas\\3c /style\\3e \\3c script\\3e alert(" in professional


def test_professional_finding_metadata_is_compact_and_drops_only_visible_seconds():
    markdown = (
        "<!-- spectre:finding:start:finding-1 -->\n"
        "### Finding\n\n"
        "**Severity:** HIGH  \n"
        "**Target:** target.example.internal  \n"
        "**Phase:** Initial Access  \n"
        "**Observed:** `2026-09-07 16:44:37`\n\n"
        "#### Description\n\n"
        "Evidence.\n"
        "<!-- spectre:finding:end:finding-1 -->"
    )

    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    interactive = HtmlReportExporter.build_full_html(markdown)

    assert '<span class="finding-meta-value"><code>2026-09-07 16:44</code></span>' in professional
    assert "2026-09-07 16:44:37" not in professional
    assert "2026-09-07 16:44:37" in interactive
    assert ".finding-meta-item:not(:last-child)::after" in professional
    assert 'content: "·";' in professional
    assert ".finding-meta-item:not(:last-child)::after" not in interactive


def test_professional_tables_receive_stable_layout_roles():
    executive = wrap_section_markdown(
        """## 1. Executive Summary

| # | Finding | Severity | Phase | Status |
|---|---|---|---|---|
| 1 | Authentication bypass | HIGH | access | Open |""",
        "executive_summary",
    )
    remediation = wrap_section_markdown(
        """## 2. Remediation

| Priority | Recommendation | Affects Finding # |
|---|---|---|
| P2 | Reject unsigned tokens | Finding #1 |""",
        "remediation_table",
    )

    professional = HtmlReportExporter.build_full_html(
        executive + "\n\n" + remediation,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )

    assert '<table class="findings-matrix" data-print-layout="breakable">' in professional
    assert '<table class="action-plan" data-print-layout="breakable">' in professional
    assert ".findings-matrix th:nth-child(2)" in professional
    assert "white-space: nowrap;" in professional
    assert ".action-plan th:nth-child(2)" in professional
    assert ".action-plan td:nth-child(2) { width: 72%; }" in professional
    assert "display: table-header-group;" in professional
    assert "table-layout: fixed;" in professional


def test_professional_findings_matrix_uses_the_shared_severity_badges():
    executive = wrap_section_markdown(
        """## 1. Executive Summary

### Findings Matrix

| # | Finding | Severity | Phase | Status |
|---|---|---|---|---|
| 1 | Remote code execution | CRITICAL | access | Open |
| 2 | Stored scripting | HIGH | access | Open |
| 3 | Weak credential policy | MEDIUM | privesc | In Progress |
| 4 | Verbose banner | LOW | recon | Resolved |
| 5 | Informational note | INFO | misc | Open |

**Total:** <span class="severity-pill severity-critical">CRITICAL</span> 1 · <span class="severity-pill severity-high">HIGH</span> 1 · <span class="severity-pill severity-medium">MEDIUM</span> 1 · <span class="severity-pill severity-low">LOW</span> 1""",
        "executive_summary",
    )

    professional = HtmlReportExporter.build_full_html(
        executive, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    interactive = HtmlReportExporter.build_full_html(executive)

    for severity in ("critical", "high", "medium", "low", "info"):
        badge = f'<span class="severity-pill severity-{severity}">{severity.upper()}</span>'
        assert badge in professional
    assert "<td>CRITICAL</td>" not in professional
    assert "<td>HIGH</td>" not in professional
    assert "<td>CRITICAL</td>" in interactive
    assert "<td>HIGH</td>" in interactive
    assert "<td>F-001</td>" in professional
    assert "<td>1</td>" in interactive


def test_professional_four_column_remediation_table_enhanced():
    remediation = wrap_section_markdown(
        """## 5. Remediation & Action Plan

| Priority | Vulnerability | Recommended Action | Status |
|----------|---------------|--------------------|--------|
| CRITICAL | Sudo NOPASSWD /usr/bin/less | Remove sudoers rule | Open |
| HIGH | Weak SSH Key | – | In Progress |""",
        "remediation_table",
    )

    professional = HtmlReportExporter.build_full_html(
        remediation,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )

    assert (
        '<table class="action-plan action-plan-4col" data-print-layout="breakable">'
        in professional
    )
    assert 'class="severity-pill severity-critical"' in professional
    assert 'class="severity-pill severity-high"' in professional
    assert '<span class="report-empty-cell">–</span>' in professional
    assert ".action-plan.action-plan-4col td:nth-child(2)" in professional


def test_professional_pagination_rules_are_profile_isolated_and_keep_explicit_breaks():
    markdown = wrap_section_markdown(
        "## Findings\n\n<!-- spectre:pagebreak -->\n\nManual finding context.",
        "finding_section",
    )

    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    interactive = HtmlReportExporter.build_full_html(markdown)

    assert 'class="spectre-page-break"' in professional
    assert 'class="spectre-page-break"' in interactive
    assert 'body[data-report-profile="professional_print"] .report-finding {' in professional
    assert (
        'body[data-report-profile="professional_print"] .finding-recommendation h4,' in professional
    )
    assert 'body[data-report-profile="professional_print"] .report-appendix {' in professional
    assert (
        'body[data-report-profile="professional_print"] .report-appendix::before {' in professional
    )
    assert 'content: "APPENDIX";' in professional
    assert 'font: 7.25pt "Segoe UI", sans-serif;' in professional
    assert 'body[data-report-profile="professional_print"] .report-finding {' not in interactive


def test_professional_moves_leading_pagebreak_before_semantic_section():
    markdown = wrap_section_markdown(
        "<!-- spectre:pagebreak -->\n\n## 5. Remediation\n\nPlan details.",
        "remediation_table",
    )

    normalized = normalize_leading_section_pagebreaks(markdown)
    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )

    assert normalized.index("spectre:pagebreak") < normalized.index("spectre:section:start")
    assert professional.index('class="spectre-page-break"') < professional.index(
        'class="report-section report-remediation"'
    )
    remediation = professional.split('class="report-section report-remediation"', 1)[1]
    assert 'class="spectre-page-break"' not in remediation


def test_professional_attack_path_renders_as_timeline_without_changing_interactive_html():
    markdown = wrap_section_markdown(
        """## 3. Attack Path

The validated path from exposure to impact is summarized below.

### Attack Chain

1. **Reconnaissance & Enumeration**: Public API enumerated
   - *Description:* An undocumented administrative route was discovered.
   - *Finding:* Unauthenticated API access <!-- finding:finding_1 -->
2. **Initial Access & Exploitation**: Administrative records retrieved
   - *Description:* The route accepted requests without a valid session.
   - *Finding:* Stored operator payload <!-- finding:finding_2 -->""",
        "attack_path",
    )

    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    interactive = HtmlReportExporter.build_full_html(markdown)

    assert '<div class="attack-path-timeline">' in professional
    assert professional.count('class="attack-path-step"') == 2
    assert '<div class="attack-path-node">01</div>' in professional
    assert '<div class="attack-path-phase">Reconnaissance &amp; Enumeration</div>' in professional
    assert "An undocumented administrative route was discovered." in professional
    assert '<span class="attack-path-finding-label">Finding</span>' in professional
    assert "finding:finding_1" not in professional
    assert 'body[data-report-profile="professional_print"] .attack-path-step {' in professional

    assert 'class="attack-path-timeline"' not in interactive
    assert "<ol>" in interactive


def test_professional_manual_attack_path_uses_neutral_step_label():
    markdown = wrap_section_markdown(
        "## Attack Path\n\n1. Enumerate the public endpoint.\n2. Validate impact.",
        "attack_path",
    )
    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )

    assert '<div class="attack-path-phase">Step 01</div>' in professional
    assert '<div class="attack-path-phase">Step 02</div>' in professional
    assert "Reconnaissance" not in professional


def test_professional_attack_path_preserves_unstructured_markdown_between_and_after_steps():
    markdown = wrap_section_markdown(
        """## Attack Path

1. **Reconnaissance**: Enumerate the public endpoint
   - *Description:* The public surface was mapped.

Manual reviewer note between generated steps.

2. **Initial Access**: Validate impact
   - *Finding:* Synthetic access finding

Manual conclusion after the final generated step.""",
        "attack_path",
    )

    professional = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )

    assert professional.count('class="attack-path-step"') == 2
    assert professional.count('class="attack-path-timeline"') == 2
    assert (
        professional.index("Enumerate the public endpoint")
        < professional.index("Manual reviewer note between generated steps.")
        < professional.index("Validate impact")
        < professional.index("Manual conclusion after the final generated step.")
    )


def test_professional_long_code_can_flow_across_pages_without_splitting_short_code():
    markdown = wrap_section_markdown(
        "## Findings\n\n" + "```bash\n" + "\n".join(["id"] * 36) + "\n```",
        "finding_section",
    )
    html = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    assert (
        '<pre class="report-code-long" data-print-layout="breakable">'
        '<code class="language-bash">' in html
    )
    assert '[data-print-layout~="breakable"]' in html
    assert "break-inside: auto;" in html


def test_professional_keeps_short_finding_closing_sections_together():
    html = HtmlReportExporter.build_full_html(
        "## Findings\n\nNarrative.",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )

    assert (
        'body[data-report-profile="professional_print"] .finding-recommendation,' in html
    )
    assert 'body[data-report-profile="professional_print"] .finding-references {' in html
    assert "box-decoration-break: clone;" in html


def test_professional_projects_status_and_phase_names_into_recognizable_generated_matrix():
    finding = ReportFindingItem(
        id="finding_1",
        title="Authentication bypass",
        severity="high",
        phase="access",
        status="resolved",
    )
    summary = wrap_section_markdown(
        "## 1. Executive Summary\n\n### Findings Matrix\n\n"
        "| # | Finding | Severity | Phase | Status |\n"
        "|---|---|---|---|---|\n"
        "| 1 | Authentication bypass | HIGH | access | Open |",
        "executive_summary",
    )
    source = (
        summary
        + "\n\n"
        + wrap_section_markdown(
            "## 2. Technical Findings\n\n" + finding.to_markdown("en"),
            "finding_section",
        )
    )
    professional = HtmlReportExporter.build_full_html(
        source, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    professional_de = HtmlReportExporter.build_full_html(
        source, language="de", profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    interactive = HtmlReportExporter.build_full_html(source)
    assert "<td>Resolved</td>" in professional
    assert "<td>Initial Access &amp; Exploitation</td>" in professional
    assert "<td>Initialer Zugriff &amp; Exploitation</td>" in professional_de
    assert "<td>Open</td>" in interactive
    assert "<td>access</td>" in interactive
    assert "| access | Open |" in source

    manual = source.replace("Authentication bypass | HIGH", "Manual note | HIGH")
    untouched = HtmlReportExporter.build_full_html(
        manual, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    assert "<td>Open</td>" in untouched
    assert "<td>Initial Access &amp; Exploitation</td>" in untouched

    summary_only = HtmlReportExporter.build_full_html(
        summary, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    assert "<td>Open</td>" in summary_only
    assert "<td>Initial Access &amp; Exploitation</td>" in summary_only

    custom_phase = source.replace("| access | Open |", "| customer-validation | Open |")
    custom = HtmlReportExporter.build_full_html(
        custom_phase, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    assert "<td>customer-validation</td>" in custom


def test_professional_finding_metadata_references_and_nested_code_evidence():
    evidence = ReportEvidenceItem(
        id="ev_1",
        type="terminal",
        language="bash",
        content="echo before\n```\necho after",
    )
    finding = ReportFindingItem(
        id="finding_2",
        title="Privileged shell",
        severity="critical",
        cvss_score=9.8,
        cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        status="accepted_risk",
        targets=["192.0.2.1", "192.0.2.2"],
        description="Technical evidence:\n\n" + evidence.to_persisted_markdown(),
        references=["CVE-2026-1234"],
    )
    source = wrap_section_markdown(
        "## 4. Technical Findings\n\n" + finding.to_markdown("en"),
        "finding_section",
    )
    html = HtmlReportExporter.build_full_html(
        source, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    assert 'class="finding-meta-item finding-meta-cvss-vector"' in html
    assert "192.0.2.1, 192.0.2.2" in html
    assert "Accepted Risk" in html
    assert 'class="finding-references"' in html
    assert "CVE-2026-1234" in html
    assert html.count('<pre data-print-layout="keep-together">') == 1
    assert "echo before\n```\necho after" in html
    assert "spectre:evidence" not in html
    assert "spectre:finding" not in html


def test_professional_cover_and_header_category_awareness():
    # 1. Standard Pentest (default)
    pentest_md = (
        wrap_section_markdown(
            "# Security Assessment Report\n\n| | |\n|---|---|\n| **Client / Organization** | `Acme` |\n",
            "header_metadata",
        )
        + "\n\n"
        + wrap_section_markdown("## 1. Technical Findings\n\nFinding text", "finding_section")
    )

    html_pentest = HtmlReportExporter.build_full_html(
        pentest_md, profile=ReportExportProfile.PROFESSIONAL_PRINT, language="en"
    )
    assert '<span class="report-cover-kicker">PENETRATION TEST REPORT</span>' in html_pentest
    assert 'content: "Penetration Test Report";' in html_pentest

    # German Pentest
    html_pentest_de = HtmlReportExporter.build_full_html(
        pentest_md, profile=ReportExportProfile.PROFESSIONAL_PRINT, language="de"
    )
    assert '<span class="report-cover-kicker">PENETRATIONSTEST-BERICHT</span>' in html_pentest_de
    assert 'content: "Penetrationstest-Bericht";' in html_pentest_de

    # 2. CTF explicit category
    html_ctf = HtmlReportExporter.build_full_html(
        pentest_md,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        language="en",
        category="ctf",
    )
    assert '<span class="report-cover-kicker">CTF WRITEUP</span>' in html_ctf
    assert 'content: "CTF Writeup";' in html_ctf

    # 3. CTF auto-detected from title
    ctf_walkthrough_md = (
        wrap_section_markdown(
            "# CTF Walkthrough Report\n\n| | |\n|---|---|\n| **Client / Organization** | `HTB` |\n",
            "header_metadata",
        )
        + "\n\n"
        + wrap_section_markdown("## Initial Foothold\n\nFoothold notes", "phase_section:access")
    )

    html_ctf_auto = HtmlReportExporter.build_full_html(
        ctf_walkthrough_md, profile=ReportExportProfile.PROFESSIONAL_PRINT, language="en"
    )
    assert '<span class="report-cover-kicker">CTF WALKTHROUGH</span>' in html_ctf_auto
    assert 'content: "CTF Walkthrough";' in html_ctf_auto

    # German CTF Walkthrough
    html_ctf_de = HtmlReportExporter.build_full_html(
        ctf_walkthrough_md, profile=ReportExportProfile.PROFESSIONAL_PRINT, language="de"
    )
    assert '<span class="report-cover-kicker">CTF WALKTHROUGH</span>' in html_ctf_de
    assert 'content: "CTF Walkthrough";' in html_ctf_de

    # 4. Security Audit category
    html_audit = HtmlReportExporter.build_full_html(
        pentest_md,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        language="en",
        category="audit",
    )
    assert '<span class="report-cover-kicker">SECURITY AUDIT REPORT</span>' in html_audit
    assert 'content: "Security Audit Report";' in html_audit


def test_professional_print_css_hardening():
    markdown = wrap_section_markdown("## 1. Technical Findings\n\nFinding text", "finding_section")
    html = HtmlReportExporter.build_full_html(
        markdown, profile=ReportExportProfile.PROFESSIONAL_PRINT
    )
    assert "print-color-adjust: exact !important;" in html
    assert "-webkit-print-color-adjust: exact !important;" in html
    assert 'body[data-report-profile="professional_print"] img {' in html
    assert "max-height: 220mm;" in html


def test_professional_metadata_extraction_aliases():
    md = (
        wrap_section_markdown(
            """# Assessment Report

| | |
|---|---|
| **Kunde** | Initech Global |
| **Ziel** | 192.168.1.100 |
| **Datum** | 2026-09-12 |
| **Vertraulichkeit** | Streng vertraulich |
| **Version** | v2.3 |
""",
            "header_metadata",
        )
        + "\n\n"
        + wrap_section_markdown("## Findings\n\nSome finding", "finding_section")
    )

    html = HtmlReportExporter.build_full_html(
        md, profile=ReportExportProfile.PROFESSIONAL_PRINT, language="de"
    )

    assert "Initech Global" in html
    assert "192.168.1.100" in html
    assert "2026-09-12" in html
    assert "Streng vertraulich" in html
    assert "v2.3" in html
    assert '<span class="report-cover-meta-label">Auftraggeber</span>' in html
    assert '<span class="report-cover-meta-label">Ziel / Scope</span>' in html


def test_professional_heading_renumbering_consistent():
    # Mix of unnumbered and numbered sections
    sec1 = wrap_section_markdown("## Executive Summary\n\nSummary text", "executive_summary")
    sec2 = wrap_section_markdown("## Scope & Limitations\n\nScope details", "scope_limitations")
    sec3 = wrap_section_markdown("## 5. Technical Findings\n\nFinding text", "finding_section")
    sec4 = wrap_section_markdown("## Remediation Plan\n\nRemediation details", "remediation_table")

    combined = f"{sec1}\n\n{sec2}\n\n{sec3}\n\n{sec4}"
    html = HtmlReportExporter.build_full_html(
        combined, profile=ReportExportProfile.PROFESSIONAL_PRINT, language="en"
    )

    assert "<h2>1. Executive Summary</h2>" in html
    assert "<h2>2. Scope &amp; Limitations</h2>" in html
    assert "<h2>3. Technical Findings</h2>" in html
    assert "<h2>4. Remediation Plan</h2>" in html


def test_professional_unstructured_metadata_cover_projection_and_pruning():
    raw_md = """# Penetration Test Report: Acquirer Core

| Parameter | Value |
|---|---|
| **Client** | CyberDyne Systems |
| **Target** | 10.10.10.5 |
| **Date** | 2026-09-15 |
| **Lead Tester** | Agent Smith |

## Executive Summary

This is the summary of testing conducted without explicit section markers.
"""
    html = HtmlReportExporter.build_full_html(
        raw_md, profile=ReportExportProfile.PROFESSIONAL_PRINT, language="en"
    )

    # Metadata must be on the cover page
    assert '<h1 class="report-cover-title">Penetration Test Report: Acquirer Core</h1>' in html
    assert "CyberDyne Systems" in html
    assert "10.10.10.5" in html
    assert "Agent Smith" in html

    # The raw metadata table and duplicate H1 must NOT appear in the body
    assert '<section class="report-cover"' in html
    body_part = html.split('</section>', 1)[1]
    assert "<table" not in body_part
    assert "<h1" not in body_part
    assert "<h2>Executive Summary</h2>" in body_part
    assert "This is the summary of testing conducted without explicit section markers." in body_part


def test_professional_structured_header_metadata_with_notes_pruning():
    sec_meta = wrap_section_markdown(
        """# Penetration Test Report

| | |
|---|---|
| **Client** | Wayne Enterprises |
| **Target** | 192.168.0.1 |

Note: Testing was conducted strictly during out-of-office hours.
""",
        "header_metadata",
    )
    sec_body = wrap_section_markdown("## Scope\n\nScope details.", "scope_limitations")
    combined = f"{sec_meta}\n\n{sec_body}"

    html = HtmlReportExporter.build_full_html(
        combined, profile=ReportExportProfile.PROFESSIONAL_PRINT, language="en"
    )

    # Cover should have Wayne Enterprises
    assert "Wayne Enterprises" in html

    # Body must not duplicate table or H1, but MUST preserve the manual note!
    assert '<section class="report-cover"' in html
    body_part = html.split('</section>', 1)[1]
    assert "<table" not in body_part
    assert "<h1" not in body_part
    assert "Note: Testing was conducted strictly during out-of-office hours." in body_part
    assert "<h2>1. Scope</h2>" in body_part


def test_professional_metadata_lead_tester_and_unbolded_colons():
    raw_md = """# Web Application Assessment

| Key | Value |
|---|---|
| Client: | Umbrella Corp |
| Lead Tester: | Alice Smith |
| Timeframe: | 2026-09-01 to 2026-09-05 |
| Classification: | Confidential |

## Findings

Summary of vulnerabilities found.
"""
    html = HtmlReportExporter.build_full_html(
        raw_md, profile=ReportExportProfile.PROFESSIONAL_PRINT, language="en"
    )

    assert "Umbrella Corp" in html
    assert "Alice Smith" in html
    assert "2026-09-01 to 2026-09-05" in html
    assert "Confidential" in html
    assert '<span class="report-cover-meta-label">Lead Tester</span>' in html
    assert '<span class="report-cover-meta-label">Assessment Period</span>' in html

    html_de = HtmlReportExporter.build_full_html(
        raw_md, profile=ReportExportProfile.PROFESSIONAL_PRINT, language="de"
    )
    assert '<span class="report-cover-meta-label">Testzeitraum</span>' in html_de
    assert '<span class="report-cover-meta-label">Tester</span>' in html_de


def test_manual_finding_structure_and_observed_consistency():
    """Verify newly created findings have consistent structure and metadata with imported findings."""
    finding = ReportFindingItem(
        id="finding-test-1",
        title="Manual Vulnerability",
        severity="medium",
        status="open",
        phase="recon",
        targets=["192.168.1.100"],
        timestamp="2026-09-17 16:30:00",
        description="",
        recommendation="",
    )

    md_en = finding.to_markdown(language="en", include_phase=True)
    assert "**Observed:** `2026-09-17 16:30:00`" in md_en
    assert "#### Description" in md_en
    assert "*No description provided.*" in md_en

    # Roundtrip from markdown normalizes placeholder back to empty for UI inspector
    reparsed = ReportFindingItem.from_markdown(md_en, finding.id, language="en")
    assert reparsed.description == ""
    assert reparsed.timestamp == "2026-09-17 16:30:00"

    # HTML export renders semantic finding-description section and observed badge
    html = HtmlReportExporter.build_full_html(
        f"<!-- spectre:section:start:finding_section -->\n\n## Technical Findings\n\n{md_en}\n\n<!-- spectre:section:end:finding_section -->",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        language="en",
    )
    assert '<section class="finding-description"><h4>Description</h4>' in html
    assert '<span class="finding-meta-label">Observed</span>' in html
    assert "2026-09-17 16:30" in html


def test_cover_highest_finding_severity_label_and_suppression():
    """Phase 1: Cover clearly labels highest finding severity and suppresses it if empty."""
    from core.reporting.professional import (
        ProfessionalCoverData,
        render_professional_cover,
        build_professional_cover_data,
    )

    # 1. Critical finding present
    cover_data_crit = ProfessionalCoverData(
        project_name="Security Assessment Report",
        report_label="Security Assessment",
        severity="CRITICAL",
        classification=None,
        metadata=(("Target", "192.168.1.1"), ("Date", "2026-09-18")),
        header_label="Security Assessment",
    )
    html_crit = render_professional_cover(cover_data_crit)
    assert 'class="report-cover-severity-block"' in html_crit
    assert '<span class="report-cover-severity-label">Highest Finding Severity</span>' in html_crit
    assert "CRITICAL" in html_crit

    # 2. No findings present -> severity block is suppressed, no invented severity
    cover_data_empty = ProfessionalCoverData(
        project_name="Clean Assessment",
        report_label="Security Assessment",
        severity=None,
        classification=None,
        metadata=(("Target", "10.0.0.1"), ("Date", "2026-09-18")),
        header_label="Security Assessment",
    )
    html_empty = render_professional_cover(cover_data_empty)
    assert 'class="report-cover-severity-block"' not in html_empty
    assert "CRITICAL" not in html_empty
    assert "HIGH" not in html_empty

    # Verify build_professional_cover_data computes highest severity from markdown
    md_with_findings = (
        "| # | Finding | Severity | Phase | Status |\n"
        "|---|---------|----------|-------|--------|\n"
        "| 1 | Low Issue | LOW | Recon | Open |\n"
        "| 2 | High Vulnerability | HIGH | Access | Open |\n"
    )
    data_from_md = build_professional_cover_data(
        md_with_findings,
        project_name="Test Assessment",
        target_ip="192.168.1.1",
        category="pentest",
        body_html='<span class="report-severity-badge severity-high">HIGH</span>',
        language="en",
    )
    assert data_from_md.severity == "HIGH"


def test_empty_state_rendering_highlights_and_findings():
    """Phase 2: Suppress empty and meaningless sections/placeholders."""
    from core.reporting.report_executive_summary import ReportExecutiveSummary

    # All dashes/empty highlights -> entire Key Highlights section omitted
    summary_empty_hl = ReportExecutiveSummary(
        initial_access="-",
        privilege_escalation="–",
        business_impact="none",
        remediation_summary="",
    )
    md_out = summary_empty_hl.to_markdown(findings=[], language="en")
    assert "### Key Highlights" not in md_out
    assert "- **Initial Access Vector:**" not in md_out

    # Partially filled highlights -> only filled items appear
    summary_partial = ReportExecutiveSummary(
        initial_access="SQL Injection in login",
        privilege_escalation="-",
        business_impact="Full DB compromise",
        remediation_summary="–",
    )
    md_partial = summary_partial.to_markdown(findings=[], language="en")
    assert "### Key Highlights" in md_partial
    assert "- **Initial Access Vector:** SQL Injection in login" in md_partial
    assert "- **Business Impact & Risk:** Full DB compromise" in md_partial
    assert "Privilege Escalation" not in md_partial
    assert "Recommended Remediation" not in md_partial

    # Finding with recommendation "-" -> recommendation block omitted
    f_dash = ReportFindingItem(
        id="f-dash",
        title="Dash Finding",
        severity="medium",
        recommendation="-",
    )
    f_dash_md = f_dash.to_markdown(language="en")
    assert "#### Recommendation" not in f_dash_md

    # Finding with real recommendation -> block present
    f_real = ReportFindingItem(
        id="f-real",
        title="Real Finding",
        severity="high",
        recommendation="Apply security patch 1.2.3 immediately.",
    )
    f_real_md = f_real.to_markdown(language="en")
    assert "#### Recommendation" in f_real_md
    assert "Apply security patch 1.2.3 immediately." in f_real_md

    # HTML export prunes "-" recommendation
    html_f_dash = HtmlReportExporter.build_full_html(
        f"<!-- spectre:section:start:finding_section -->\n\n## Technical Findings\n\n{f_dash_md}\n\n<!-- spectre:section:end:finding_section -->",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )
    assert 'class="finding-recommendation"' not in html_f_dash


def test_markdown_stripping_in_structured_scope():
    """Phase 3: Markdown markers and section headers do not leak into structured scope/methodology."""
    from core.reporting.report_scope import ReportScopeMethodology, clean_scope_text

    raw_dirty_scope_md = (
        "## Scope & Methodology\n\n"
        "### In-Scope Targets & Networks\n\n"
        "| Target / Host / Subnet | Type | Environment | Description |\n"
        "|---|---|---|---|\n"
        "| - **Out of Scope: | network | production | |\n"
        "| **Methodology:** | network | production | |\n"
        "| ## Scope | network | production | |\n"
        "| - **10.10.10.50**: | host | production | Internal Gateway |\n"
        "| `api.corp.local` | webapp | staging | REST API |\n"
    )

    scope = ReportScopeMethodology.from_markdown(raw_dirty_scope_md, language="en")
    # Section header artifacts should NOT be parsed as target items
    target_names = [t.target for t in scope.in_scope_targets]
    assert "- **Out of Scope:" not in target_names
    assert "Out of Scope" not in target_names
    assert "Methodology" not in target_names
    assert "Scope" not in target_names

    # Real target should be cleaned of leading - ** and trailing :
    assert "10.10.10.50" in target_names
    assert "api.corp.local" in target_names

    # Clean function unit tests
    assert clean_scope_text("- **Out of Scope:") == "Out of Scope"
    assert clean_scope_text("## Scope") == "Scope"
    assert clean_scope_text("- **192.168.1.1**:") == "192.168.1.1"

    # Serialized markdown table output is clean
    serialized = scope.to_markdown(language="en")
    assert "| `10.10.10.50` |" in serialized
    assert "- **Out of Scope:" not in serialized


def test_appendix_hierarchy_and_single_empty_state():
    """Phase 4: Clean Appendix hierarchy A/B/C without duplicate Appendix A or duplicate empty notices."""
    from core.reporting.report_appendix import ReportAppendix

    # Title normalization
    raw_md = (
        "## 6. Appendix A: Terminal Command History\n\n"
        "### A. Executed Commands\n\n"
        "```bash\nid\n```\n\n"
        "### B. Screenshots & Evidence\n\n"
        "*No screenshots or evidence recorded.*\n\n"
        "### C. Supplementary Raw Data & Notes\n\n"
        "Raw nmap notes here\n"
    )
    app = ReportAppendix.from_markdown(raw_md, language="en")
    assert app.title == "6. Appendix"
    assert len(app.command_snippets) == 1
    assert len(app.screenshots) == 0
    assert "Raw nmap notes here" in app.custom_notes

    # Verify to_markdown output
    md_out = app.to_markdown(language="en")
    assert "## 6. Appendix" in md_out
    assert "6. Appendix A:" not in md_out
    assert "### A. Executed Commands" in md_out
    assert "### B. Screenshots & Evidence" in md_out
    assert "*No screenshots or evidence recorded.*" in md_out
    # No duplicate empty screenshots text
    assert md_out.count("screenshots or evidence recorded") == 1
    assert "No screenshots captured in this project." not in md_out


def test_deterministic_finding_ids_synchronized():
    """Phase 5: Stable F-001, F-002, F-010 deterministic IDs across Matrix, Finding, and Remediation."""
    from core.reporting.report_executive_summary import ReportExecutiveSummary
    from core.reporting.report_remediation import ReportRemediationPlan
    from core.reporting.report_finding import ReportFindingItem
    from core.reporting.findings import convert_markdown_with_findings

    findings = [
        ReportFindingItem(id=f"item-{i}", title=f"Vulnerability {i}", severity="high" if i % 2 == 0 else "medium")
        for i in range(1, 12)
    ]

    # 1. Findings Matrix format
    summary = ReportExecutiveSummary()
    summary_md = summary.to_markdown(findings, language="en")
    assert "| F-001 | Vulnerability 1 |" in summary_md
    assert "| F-010 | Vulnerability 10 |" in summary_md
    assert "| F-011 | Vulnerability 11 |" in summary_md

    # 2. Remediation Table format
    plan = ReportRemediationPlan()
    remed_md = plan.to_markdown(findings, language="en")
    assert "F-001 · Vulnerability 1" in remed_md
    assert "F-010 · Vulnerability 10" in remed_md

    # 3. Technical Finding Heading in HTML
    finding_md = findings[0].to_markdown(language="en")
    html = convert_markdown_with_findings(finding_md, start_index=1)
    assert '<span class="finding-id">F-001</span> · Vulnerability 1' in html

    finding10_md = findings[9].to_markdown(language="en")
    html10 = convert_markdown_with_findings(finding10_md, start_index=10)
    assert '<span class="finding-id">F-010</span> · Vulnerability 10' in html10


def test_finding_metadata_code_color_neutralized():
    """Phase 6: Code in finding metadata does not use accent color in professional print."""
    from core.reporting.styles import get_report_css

    css = get_report_css(profile="professional_print")
    assert 'body[data-report-profile="professional_print"] .finding-meta-value code' in css
    assert "color: inherit;" in css



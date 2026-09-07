"""Contract tests for persistent report sections and semantic HTML export."""

from core.reporting.exporter import HtmlReportExporter
from core.reporting.profiles import ReportExportProfile
from core.reporting.template_repository import TemplateRepository
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
        assert '<article class="report-finding severity-high">' in rendered
        assert '<article class="report-finding severity-medium">' in rendered
        assert '<div class="finding-meta">' in rendered
        assert '<section class="finding-description"><h4>Description</h4>' in rendered
        assert '<section class="finding-recommendation"><h4>Recommendation</h4>' in rendered
        assert "Reject invalid tokens and rotate signing keys." in rendered
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
        wrap_section_markdown(
            "## Appendix\n\nManual supporting material.", "appendix"
        ),
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
            wrap_section_markdown(
                "## 3. Attack Path\n\n1. Initial access", "attack_path"
            ),
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
            wrap_section_markdown(
                "## 2. Scope\n\n- **In Scope:**", "scope_limitations"
            ),
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
    template = TemplateRepository(
        user_templates_dir=tmp_path / "templates"
    ).get_template("pentest_executive_en")
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
    action_plan = professional.split(
        '<section class="report-section report-remediation">', 1
    )[1].split("</section>", 1)[0]

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
        "\n\n---\n\n_Generated with SpectreHUD Pentest & CTF Companion "
        "on 2026-09-07 at 16:44:00_"
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

    assert (
        '<span class="finding-meta-value"><code>2026-09-07 16:44</code></span>'
        in professional
    )
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

    assert '<table class="findings-matrix">' in professional
    assert '<table class="action-plan">' in professional
    assert ".findings-matrix th:nth-child(2)" in professional
    assert ".action-plan th:nth-child(2)" in professional
    assert ".action-plan td:nth-child(2) { width: 72%; }" in professional
    assert "display: table-header-group;" in professional
    assert "table-layout: fixed;" in professional


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
    assert 'body[data-report-profile="professional_print"] .finding-recommendation h4 {' in professional
    assert 'body[data-report-profile="professional_print"] .report-appendix {' in professional
    assert 'body[data-report-profile="professional_print"] .report-appendix::before {' in professional
    assert 'content: "APPENDIX";' in professional
    assert 'font: 7.25pt "Segoe UI", sans-serif;' in professional
    assert 'body[data-report-profile="professional_print"] .report-finding {' not in interactive

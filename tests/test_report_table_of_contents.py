"""Contracts for the optional Professional Print table of contents."""

from core.reporting import HtmlReportExporter, ReportExportProfile, wrap_section_markdown


def _report_with_finding() -> str:
    return (
        wrap_section_markdown(
            "## 1. Executive Summary\n\nManagement overview.",
            "executive_summary",
        )
        + "\n\n"
        + wrap_section_markdown(
            """## 2. Technical Findings

<!-- spectre:finding:start:demo -->
### Authentication Bypass

**Severity:** HIGH
**Target:** portal.example.test

#### Description

The endpoint accepted an invalid token.
<!-- spectre:finding:end:demo -->
""",
            "finding_section",
        )
    )


def test_professional_toc_links_sections_and_nested_findings_after_cover():
    rendered = HtmlReportExporter.build_full_html(
        _report_with_finding(),
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        include_toc=True,
    )

    cover_index = rendered.index('class="report-cover"')
    toc_index = rendered.index('class="report-toc"')
    executive_index = rendered.index('class="report-section report-executive"')
    assert cover_index < toc_index < executive_index
    assert '<h2 id="report-toc-title">Contents</h2>' in rendered
    assert 'href="#executive-summary"' in rendered
    assert 'id="executive-summary"' in rendered
    assert "Authentication Bypass" in rendered
    assert 'class="report-toc-findings"' in rendered
    assert 'href="#finding-f-001"' in rendered
    assert 'id="finding-f-001"' in rendered
    assert '<span class="severity-pill severity-high">HIGH</span>' in rendered


def test_professional_toc_is_localized_and_optional():
    markdown = _report_with_finding()
    localized = HtmlReportExporter.build_full_html(
        markdown,
        language="de",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        include_toc=True,
    )
    disabled = HtmlReportExporter.build_full_html(
        markdown,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        include_toc=False,
    )
    interactive = HtmlReportExporter.build_full_html(
        markdown,
        profile=ReportExportProfile.INTERACTIVE,
        include_toc=True,
    )

    assert '<h2 id="report-toc-title">Inhaltsverzeichnis</h2>' in localized
    assert 'class="report-toc"' not in disabled
    assert 'class="report-toc"' not in interactive
    assert 'id="executive-summary"' in disabled
    assert 'id="finding-f-001"' in disabled
    assert 'id="executive-summary"' not in interactive


def test_professional_navigation_links_matrix_attack_path_and_remediation():
    markdown = (
        wrap_section_markdown(
            """## 1. Executive Summary

### Findings Matrix

| ID | Finding | Severity | Phase | Status |
|---|---|---|---|---|
| 1 | Authentication Bypass | HIGH | access | Open |
""",
            "executive_summary",
        )
        + "\n\n"
        + wrap_section_markdown(
            """## 2. Attack Path

### Attack Chain

1. **Initial Access**: Token replay
   - *Finding:* Authentication Bypass <!-- finding:demo -->
""",
            "attack_path",
        )
        + "\n\n"
        + wrap_section_markdown(
            """## 3. Technical Findings

<!-- spectre:finding:start:demo -->
### Authentication Bypass

**Severity:** HIGH

#### Description

The endpoint accepted an invalid token.
<!-- spectre:finding:end:demo -->
""",
            "finding_section",
        )
        + "\n\n"
        + wrap_section_markdown(
            """## 4. Remediation & Action Plan

| Priority | Vulnerability | Recommended Action | Status |
|---|---|---|---|
| HIGH | F-001 · Authentication Bypass | Reject invalid tokens. | Open |
""",
            "remediation_table",
        )
    )

    rendered = HtmlReportExporter.build_full_html(
        markdown,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        include_toc=True,
    )

    assert rendered.count('id="finding-f-001"') == 1
    assert '| F-001 |' not in rendered
    assert '<a class="finding-reference" href="#finding-f-001">F-001</a>' in rendered
    assert (
        '<a class="finding-reference" href="#finding-f-001">'
        '<span class="finding-id">F-001</span> · Authentication Bypass</a>'
    ) in rendered
    assert rendered.count('href="#finding-f-001"') >= 4
    assert 'a.finding-reference {' in rendered
    assert "color: inherit;" in rendered
    assert "text-decoration: none;" in rendered


def test_professional_navigation_omits_empty_sections_and_broken_finding_links():
    markdown = (
        wrap_section_markdown(
            "## 1. Executive Summary\n\nManagement overview.",
            "executive_summary",
        )
        + "\n\n"
        + wrap_section_markdown(
            "## 2. Attack Path\n\n*No documented attack path is available.*",
            "attack_path",
        )
        + "\n\n"
        + wrap_section_markdown(
            "## 3. Remediation & Action Plan\n\n| | | | |\n|---|---|---|---|",
            "remediation_table",
        )
    )

    rendered = HtmlReportExporter.build_full_html(
        markdown,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        include_toc=True,
    )

    assert 'href="#executive-summary"' in rendered
    assert 'href="#attack-path"' not in rendered
    assert 'href="#remediation"' not in rendered
    assert 'href="#finding-' not in rendered


def test_professional_navigation_uses_unique_title_independent_finding_ids_through_ten():
    findings = []
    for index in range(1, 11):
        findings.append(
            f"""<!-- spectre:finding:start:item-{index} -->
### Repeated title

**Severity:** MEDIUM

#### Description

Finding {index}.
<!-- spectre:finding:end:item-{index} -->"""
        )
    markdown = wrap_section_markdown(
        "## 1. Technical Findings\n\n" + "\n\n".join(findings),
        "finding_section",
    )

    rendered = HtmlReportExporter.build_full_html(
        markdown,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        include_toc=True,
    )

    for index in range(1, 11):
        anchor = f'finding-f-{index:03d}'
        assert rendered.count(f'id="{anchor}"') == 1
        assert f'href="#{anchor}"' in rendered


def test_professional_toc_css_uses_a_dedicated_page_without_page_numbers():
    rendered = HtmlReportExporter.build_full_html(
        _report_with_finding(),
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        include_toc=True,
    )

    assert 'data-print-layout="page-start" class="report-toc"' in rendered
    assert '.report-toc {' in rendered
    assert "break-after: page;" in rendered
    assert "report-toc-page" not in rendered

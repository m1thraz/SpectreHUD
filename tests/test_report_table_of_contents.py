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
    assert 'href="#report-section-1-1-executive-summary"' in rendered
    assert 'id="report-section-1-1-executive-summary"' in rendered
    assert "Authentication Bypass" in rendered
    assert 'class="report-toc-findings"' in rendered
    assert 'href="#report-finding-2-1-f-001-authentication-bypass"' in rendered
    assert 'id="report-finding-2-1-f-001-authentication-bypass"' in rendered
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
    assert "report-section-1-1-executive-summary" not in interactive


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

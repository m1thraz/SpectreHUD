"""Contracts for semantic Professional Print layout directives."""

from core.reporting import (
    PRINT_KEEP_TOGETHER,
    PRINT_KEEP_WITH_NEXT,
    PRINT_PAGE_START,
    HtmlReportExporter,
    ReportExportProfile,
    PrintLayoutPolicy,
    wrap_section_markdown,
)


def test_print_layout_policy_serializes_composable_directives():
    policy = PrintLayoutPolicy(
        page_start=True,
        keep_together=True,
        keep_with_next=True,
    )

    assert policy.html_attribute() == (
        'data-print-layout="page-start keep-together keep-with-next"'
    )
    assert PRINT_PAGE_START.html_attribute() == 'data-print-layout="page-start"'
    assert PRINT_KEEP_TOGETHER.html_attribute() == 'data-print-layout="keep-together"'
    assert PRINT_KEEP_WITH_NEXT.html_attribute() == 'data-print-layout="keep-with-next"'


def test_professional_sections_and_components_emit_semantic_print_directives():
    markdown = (
        wrap_section_markdown(
            """## 1. Attack Path

### Attack Chain

1. **Initial Access & Exploitation**: Demonstration step
   - *Description:* Demonstration step.
   - *Finding:* Example finding.
""",
            "attack_path",
        )
        + "\n\n"
        + wrap_section_markdown(
            """## 2. Findings

<!-- spectre:finding:start:demo -->
### Example Finding

**Severity:** HIGH
**Target:** portal.example.test

#### Description

Demonstration finding.
<!-- spectre:finding:end:demo -->
""",
            "finding_section",
        )
        + "\n\n"
        + wrap_section_markdown("## 3. Appendix\n\nEvidence.", "appendix")
    )

    html = HtmlReportExporter.build_full_html(
        markdown,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )

    assert '<article data-print-layout="keep-together" class="attack-path-step">' in html
    assert '<div data-print-layout="keep-with-next" class="finding-lead">' in html
    assert '<header class="finding-header">' in html
    assert '<div class="finding-meta">' in html
    assert (
        '<section data-print-layout="page-start" '
        'class="report-section report-appendix">'
    ) in html


def test_print_directive_css_is_scoped_to_professional_profile():
    html = HtmlReportExporter.build_full_html(
        "# Report",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )

    assert (
        'body[data-report-profile="professional_print"] '
        '[data-print-layout~="page-start"]' in html
    )
    assert (
        'body[data-report-profile="professional_print"] '
        '[data-print-layout~="keep-together"]' in html
    )
    assert (
        'body[data-report-profile="professional_print"] '
        '[data-print-layout~="keep-with-next"]' in html
    )

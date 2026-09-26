"""Contracts for semantic Professional Print layout directives."""

from core.reporting import (
    PRINT_BREAKABLE,
    PRINT_KEEP_TOGETHER,
    PRINT_KEEP_WITH_NEXT,
    PRINT_PAGE_END,
    PRINT_PAGE_START,
    HtmlReportExporter,
    ReportExportProfile,
    PrintLayoutPolicy,
    wrap_section_markdown,
)


def test_print_layout_policy_serializes_composable_directives():
    policy = PrintLayoutPolicy(
        page_start=True,
        page_end=True,
        keep_together=True,
        keep_with_next=True,
    )

    assert policy.html_attribute() == (
        'data-print-layout="page-start page-end keep-together keep-with-next"'
    )
    assert PRINT_PAGE_START.html_attribute() == 'data-print-layout="page-start"'
    assert PRINT_PAGE_END.html_attribute() == 'data-print-layout="page-end"'
    assert PRINT_KEEP_TOGETHER.html_attribute() == 'data-print-layout="keep-together"'
    assert PRINT_KEEP_WITH_NEXT.html_attribute() == 'data-print-layout="keep-with-next"'
    assert PRINT_BREAKABLE.html_attribute() == 'data-print-layout="breakable"'


def test_print_layout_policy_rejects_conflicting_fragmentation_rules():
    import pytest

    with pytest.raises(ValueError, match="keep-together and breakable"):
        PrintLayoutPolicy(keep_together=True, breakable=True)


def test_markdown_blocks_emit_semantic_print_directives():
    markdown = """## Evidence

| Item | Value |
|---|---|
| Target | portal.example.test |

> Important evidence note.

```text
short evidence
```

![Evidence](evidence.png)
"""

    html = HtmlReportExporter.build_full_html(markdown)

    assert '<table data-print-layout="breakable">' in html
    assert '<tr data-print-layout="keep-together">' in html
    assert '<blockquote data-print-layout="keep-together">' in html
    assert '<pre data-print-layout="keep-together"><code class="language-text">' in html
    assert (
        '<figure data-print-layout="keep-together" class="screenshot-container">' in html
    )
    assert '<figcaption class="screenshot-caption">' in html
    assert '[data-print-layout~="breakable"]' in html


def test_professional_sections_and_components_emit_semantic_print_directives():
    markdown = (
        wrap_section_markdown(
            "## 1. Executive Summary\n\nManagement overview.",
            "executive_summary",
        )
        + "\n\n"
        + wrap_section_markdown(
            """## 2. Attack Path

### Attack Chain

1. **Initial Access & Exploitation**: Demonstration step
   - *Description:* Demonstration step.
   - *Finding:* Example finding.
""",
            "attack_path",
        )
        + "\n\n"
        + wrap_section_markdown(
            """## 3. Findings

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
        + wrap_section_markdown(
            "## 4. Remediation\n\n| Priority | Action |\n|---|---|\n| P1 | Fix it |",
            "remediation_table",
        )
        + "\n\n"
        + wrap_section_markdown("## 5. Appendix\n\nEvidence.", "appendix")
    )

    html = HtmlReportExporter.build_full_html(
        markdown,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )

    assert '<article data-print-layout="keep-together" class="attack-path-step">' in html
    assert (
        '<section data-print-layout="page-end" '
        'class="report-section report-executive" id="executive-summary">'
    ) in html
    assert (
        '<section data-print-layout="page-start" '
        'class="report-section report-findings" id="technical-findings">'
    ) in html
    assert '<div data-print-layout="keep-with-next" class="finding-lead">' in html
    assert '<header class="finding-header">' in html
    assert '<div class="finding-meta">' in html
    assert (
        '<section data-print-layout="page-start" '
        'class="report-section report-appendix" id="appendix">'
    ) in html
    assert (
        '<section class="report-section report-attack-path" id="attack-path">'
    ) in html
    assert (
        '<section class="report-section report-remediation" id="remediation">'
    ) in html


def test_only_professional_print_groups_following_image_note_into_figure():
    markdown = "![Evidence](evidence.png)\n\nSupporting explanation."

    professional = HtmlReportExporter.build_full_html(
        markdown,
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )
    interactive = HtmlReportExporter.build_full_html(markdown)

    assert '<span class="screenshot-note">Supporting explanation.</span>' in professional
    assert '<span class="screenshot-note">' not in interactive
    assert "</figure>\n<p>Supporting explanation.</p>" in interactive


def test_print_directive_css_is_shared_by_print_profiles():
    html = HtmlReportExporter.build_full_html(
        "# Report",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
    )

    assert (
        '[data-print-layout~="page-start"]' in html
    )
    assert '[data-print-layout~="page-end"]' in html
    assert (
        '[data-print-layout~="keep-together"]' in html
    )
    assert (
        '[data-print-layout~="keep-with-next"]' in html
    )

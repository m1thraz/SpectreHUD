from core.reporting import build_report_navigation
from core.reporting import wrap_section_markdown


def test_navigation_preserves_section_order_titles_and_marker_identity():
    markdown = "\n\n".join(
        (
            wrap_section_markdown("## Custom Overview\n\nText", "executive_summary:1"),
            wrap_section_markdown("## Another Overview\n\nText", "executive_summary:2"),
            wrap_section_markdown("## Custom Recon\n\nText", "phase_section:recon"),
        )
    )

    navigation = build_report_navigation(markdown)

    assert [entry.identity for entry in navigation.sections] == [
        "executive_summary:1",
        "executive_summary:2",
        "phase_section:recon",
    ]
    assert [entry.title for entry in navigation.sections] == [
        "Custom Overview",
        "Another Overview",
        "Custom Recon",
    ]
    assert [markdown.splitlines()[entry.line_number - 1] for entry in navigation.sections] == [
        "## Custom Overview",
        "## Another Overview",
        "## Custom Recon",
    ]


def test_navigation_lists_only_valid_findings_in_report_order():
    markdown = """<!-- spectre:finding:start:first -->
<!-- spectre:loot:first:abcd -->
### First Finding

Body
<!-- spectre:finding:end:first -->

<!-- spectre:finding:start:broken -->
### Broken Finding
<!-- spectre:finding:start:second -->
### Second Finding
<!-- spectre:finding:end:second -->
"""

    navigation = build_report_navigation(markdown)

    assert [(entry.identity, entry.title) for entry in navigation.findings] == [
        ("first", "First Finding"),
    ]
    assert markdown.splitlines()[navigation.findings[0].line_number - 1] == "### First Finding"


def test_navigation_is_empty_for_legacy_and_malformed_sections():
    legacy = "# Legacy Report\n\nManual content"
    malformed = "<!-- spectre:section:start:executive_summary -->\n## Summary"

    assert build_report_navigation(legacy).sections == ()
    assert build_report_navigation(legacy).findings == ()
    assert build_report_navigation(malformed).sections == ()

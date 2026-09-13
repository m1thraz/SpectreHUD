"""Headless tests for Report Workspace preview-only Markdown transforms."""

from core.reporting import PAGEBREAK_MARKER, wrap_section_markdown
from ui.report.preview_transforms import (
    PREVIEW_NAV_TOKEN_PREFIX,
    PREVIEW_PAGEBREAK_LABEL,
    PREVIEW_PAGEBREAK_TOKEN,
    PREVIEW_SPACER_LABELS,
    prepare_preview_markdown,
    strip_preview_surrogates,
)


def test_prepare_preview_indexes_valid_sections_and_exposes_layout_markers():
    markdown = wrap_section_markdown(
        f"## Summary\n\nBefore\n\n{PAGEBREAK_MARKER}\n\nAfter",
        "executive_summary",
    )

    prepared = prepare_preview_markdown(markdown)

    assert prepared.landmarks == (
        (f"{PREVIEW_NAV_TOKEN_PREFIX}0000", "section", "executive_summary"),
    )
    assert f"## Summary {PREVIEW_NAV_TOKEN_PREFIX}0000" in prepared.markdown
    assert PREVIEW_PAGEBREAK_TOKEN in prepared.markdown
    assert PAGEBREAK_MARKER not in prepared.markdown


def test_prepare_preview_leaves_marker_examples_inside_code_fences_untouched():
    fenced_marker = "<!-- spectre:pagebreak -->"
    markdown = f"```markdown\n{fenced_marker}\n```"

    prepared = prepare_preview_markdown(markdown)

    assert prepared.markdown == markdown
    assert prepared.landmarks == ()


def test_strip_preview_surrogates_removes_visual_layout_and_navigation_lines():
    converted_markdown = (
        "Before\n"
        f"{PREVIEW_PAGEBREAK_LABEL}\n"
        f"{PREVIEW_SPACER_LABELS['large']}\n"
        f"Heading {PREVIEW_NAV_TOKEN_PREFIX}0000\n"
        "After\n"
    )

    assert strip_preview_surrogates(converted_markdown) == "Before\nAfter\n"

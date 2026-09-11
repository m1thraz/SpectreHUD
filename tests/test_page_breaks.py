"""
Tests for PDF/Print Layout, intelligent page breaks, CSS rules,
preview roundtrip reconciliation, template integration, and editor actions.
"""

import unittest
from PyQt6.QtWidgets import QPlainTextEdit

from core.reporting import REPORT_PRINT_CSS, REPORT_BASE_CSS, REPORT_LIGHT_CSS
from core.reporting import (
    PAGEBREAK_MARKER,
    PAGEBREAK_HTML,
    SPACER_REGEX,
    format_spacer_marker,
    preserve_markers_in_preview_roundtrip,
)
from core.reporting import convert_markdown_to_html
from core.reporting import (
    TemplateSection,
    ReportTemplate,
    ReportContext,
    TemplateRenderer,
)
from core.reporting import template_to_dict, dict_to_template
from ui.markdown_toolbar_actions import insert_page_break, insert_spacer
from ui.report_editor_tab import (
    PREVIEW_PAGEBREAK_LABEL,
    _markdown_with_preview_pagebreaks,
    _strip_preview_pagebreaks,
)

class TestPageBreakConversion(unittest.TestCase):
    """Test markdown conversion of pagebreak markers."""

    def test_pagebreak_marker_renders_to_html(self):
        md = "# Heading\n\n<!-- spectre:pagebreak -->\n\nParagraph after break."
        html = convert_markdown_to_html(md)
        self.assertIn(PAGEBREAK_HTML, html)
        self.assertIn('class="spectre-page-break"', html)
        self.assertIn('contenteditable="false"', html)

    def test_pagebreak_with_whitespace_and_casing(self):
        variations = [
            "<!-- spectre:pagebreak -->",
            "<!--spectre:pagebreak-->",
            "<!--   spectre:pagebreak   -->",
            "<!-- SPECTRE:PAGEBREAK -->",
            "<!-- Spectre:PageBreak -->",
        ]
        for v in variations:
            md = f"Intro\n\n{v}\n\nOutro"
            html = convert_markdown_to_html(md)
            self.assertIn(PAGEBREAK_HTML, html, f"Failed for variation: {v!r}")

    def test_pagebreak_flushes_pending_blocks(self):
        # List flushing
        md_list = "- Item 1\n- Item 2\n<!-- spectre:pagebreak -->\n- Item 3"
        html_list = convert_markdown_to_html(md_list)
        self.assertIn("</ul>\n" + PAGEBREAK_HTML, html_list)

        # Blockquote flushing
        md_quote = "> Quote text\n<!-- spectre:pagebreak -->\nNormal text"
        html_quote = convert_markdown_to_html(md_quote)
        self.assertIn("</blockquote>\n" + PAGEBREAK_HTML, html_quote)

        # Table flushing
        md_table = "| Col 1 | Col 2 |\n|---|---|\n| A | B |\n<!-- spectre:pagebreak -->\nNext"
        html_table = convert_markdown_to_html(md_table)
        self.assertIn("</table></div>\n" + PAGEBREAK_HTML, html_table)

    def test_pagebreak_inside_codeblock_not_converted(self):
        md = "```\n<!-- spectre:pagebreak -->\n```"
        html = convert_markdown_to_html(md)
        self.assertNotIn(PAGEBREAK_HTML, html)
        self.assertIn("&lt;!-- spectre:pagebreak --&gt;", html)

    def test_spacer_markers_render_with_bounded_sizes(self):
        for size in ("small", "medium", "large"):
            marker = format_spacer_marker(size)
            self.assertIsNotNone(SPACER_REGEX.fullmatch(marker))
            self.assertIn(f'class="spectre-spacer spacer-{size}"', convert_markdown_to_html(marker))


class TestPrintCssRules(unittest.TestCase):
    """Test print CSS rules preventing micro-breaks and handling page breaks."""

    def test_headings_avoid_page_break(self):
        self.assertIn("h1, h2, h3, h4, h5, h6", REPORT_PRINT_CSS)
        self.assertIn("page-break-after: avoid;", REPORT_PRINT_CSS)
        self.assertIn("break-after: avoid;", REPORT_PRINT_CSS)
        self.assertIn("page-break-inside: avoid;", REPORT_PRINT_CSS)
        self.assertIn("break-inside: avoid;", REPORT_PRINT_CSS)

    def test_tables_intelligent_pagination(self):
        self.assertIn("table {", REPORT_PRINT_CSS)
        self.assertIn("break-inside: auto;", REPORT_PRINT_CSS)
        self.assertIn("thead {", REPORT_PRINT_CSS)
        self.assertIn("display: table-header-group;", REPORT_PRINT_CSS)
        self.assertIn("tfoot {", REPORT_PRINT_CSS)
        self.assertIn("display: table-footer-group;", REPORT_PRINT_CSS)
        self.assertIn("tr, tbody tr {", REPORT_PRINT_CSS)
        self.assertIn("break-inside: avoid;", REPORT_PRINT_CSS)

    def test_figures_and_screenshots(self):
        self.assertIn("figure, .screenshot-container {", REPORT_PRINT_CSS)
        self.assertIn(".screenshot-caption, .screenshot-container p {", REPORT_PRINT_CSS)
        self.assertIn("page-break-before: avoid;", REPORT_PRINT_CSS)

    def test_finding_header_avoid_break(self):
        self.assertIn(".finding-header, .finding-meta {", REPORT_PRINT_CSS)
        self.assertIn("break-inside: avoid;", REPORT_PRINT_CSS)

    def test_spectre_page_break_print_styling(self):
        self.assertIn(".spectre-page-break {", REPORT_PRINT_CSS)
        self.assertIn("break-before: page !important;", REPORT_PRINT_CSS)
        self.assertIn("page-break-before: always !important;", REPORT_PRINT_CSS)
        self.assertIn("visibility: hidden !important;", REPORT_PRINT_CSS)

    def test_spectre_page_break_screen_styling(self):
        self.assertIn(".spectre-page-break {", REPORT_BASE_CSS)
        self.assertIn('content: "PAGE BREAK";', REPORT_BASE_CSS)
        self.assertIn('content: "SEITENUMBRUCH";', REPORT_BASE_CSS)

    def test_light_theme_styling(self):
        self.assertIn(".spectre-page-break { border-top-color: #d0d7de; }", REPORT_LIGHT_CSS)
        self.assertIn(".spectre-spacer.spacer-medium { height: 1rem; }", REPORT_BASE_CSS)


class TestPreviewRoundtrip(unittest.TestCase):
    """Test preview roundtrip marker preservation for pagebreaks."""

    def test_preserves_pagebreak_dropped_by_preview(self):
        original_md = """# Title

Some introductory text.

<!-- spectre:pagebreak -->

## Second Section

More content.
"""
        # Simulated Qt toMarkdown() output where HTML comment is stripped
        stripped_md = """# Title

Some introductory text.

## Second Section

More content.
"""
        reconciled = preserve_markers_in_preview_roundtrip(original_md, stripped_md)
        self.assertIn(PAGEBREAK_MARKER, reconciled)
        # Verify pagebreak comes before the second section
        pb_pos = reconciled.find(PAGEBREAK_MARKER)
        sec2_pos = reconciled.find("## Second Section")
        self.assertNotEqual(pb_pos, -1)
        self.assertNotEqual(sec2_pos, -1)
        self.assertLess(pb_pos, sec2_pos)

    def test_preserves_multiple_pagebreaks(self):
        original_md = """# Sec 1
Text 1

<!-- spectre:pagebreak -->

# Sec 2
Text 2

<!-- spectre:pagebreak -->

# Sec 3
Text 3
"""
        stripped_md = """# Sec 1

Text 1

# Sec 2

Text 2

# Sec 3

Text 3
"""
        reconciled = preserve_markers_in_preview_roundtrip(original_md, stripped_md)
        self.assertEqual(reconciled.count(PAGEBREAK_MARKER), 2)

    def test_preserves_pagebreaks_alongside_loot_markers(self):
        original_md = """<!-- spectre:loot:entry_123:abcdef123456 -->
### Findings

<!-- spectre:pagebreak -->

## Appendix
"""
        stripped_md = """### Findings

## Appendix
"""
        reconciled = preserve_markers_in_preview_roundtrip(original_md, stripped_md)
        self.assertIn("<!-- spectre:loot:entry_123:abcdef123456 -->", reconciled)
        self.assertIn(PAGEBREAK_MARKER, reconciled)

    def test_preview_surrogate_skips_fenced_code_and_is_removed_before_commit(self):
        markdown = (
            "Intro\n\n<!-- spectre:pagebreak -->\n\nOutro\n\n"
            "```html\n<!-- spectre:pagebreak -->\n```"
        )

        preview_markdown = _markdown_with_preview_pagebreaks(markdown)

        self.assertEqual(preview_markdown.count("SPECTRE_PAGEBREAK_PREVIEW_TOKEN"), 1)
        self.assertIn("```html\n<!-- spectre:pagebreak -->\n```", preview_markdown)
        self.assertNotIn(PREVIEW_PAGEBREAK_LABEL, _strip_preview_pagebreaks(PREVIEW_PAGEBREAK_LABEL))

    def test_preserves_spacer_dropped_by_preview(self):
        original = "Before\n\n<!-- spectre:spacer:large -->\n\n## After"
        reconciled = preserve_markers_in_preview_roundtrip(original, "Before\n\n## After")
        self.assertIn("<!-- spectre:spacer:large -->", reconciled)


class TestTemplateIntegration(unittest.TestCase):
    """Test template engine page_break_before integration and serialization."""

    def test_template_section_default_and_custom(self):
        sec_default = TemplateSection(type="executive_summary")
        self.assertFalse(sec_default.page_break_before)

        sec_pb = TemplateSection(type="remediation_table", page_break_before=True)
        self.assertTrue(sec_pb.page_break_before)

    def test_template_renderer_emits_pagebreak(self):
        template = ReportTemplate(
            id="test_pb",
            name="Test PB",
            language="de",
            category="pentest",
            complexity="simple",
            sections=[
                TemplateSection(type="header_metadata"),
                TemplateSection(type="executive_summary", page_break_before=True),
            ],
        )
        renderer = TemplateRenderer()
        output = renderer.render(template, ReportContext())
        self.assertIn(PAGEBREAK_MARKER, output)
        pb_pos = output.find(PAGEBREAK_MARKER)
        exec_pos = output.find("Executive Summary")
        self.assertLess(pb_pos, exec_pos)

    def test_template_serialization_roundtrip(self):
        template = ReportTemplate(
            id="custom_template",
            name="Custom Template",
            language="en",
            category="pentest",
            complexity="complex",
            sections=[
                TemplateSection(type="header_metadata"),
                TemplateSection(type="phase_section", category_id="recon", page_break_before=True),
                TemplateSection(type="appendix", page_break_before=False),
            ],
        )
        d = template_to_dict(template)
        self.assertTrue(d["sections"][1]["page_break_before"])
        self.assertNotIn("page_break_before", d["sections"][0])
        self.assertNotIn("page_break_before", d["sections"][2])

        loaded = dict_to_template(d)
        self.assertIsNotNone(loaded)
        self.assertFalse(loaded.sections[0].page_break_before)
        self.assertTrue(loaded.sections[1].page_break_before)
        self.assertFalse(loaded.sections[2].page_break_before)

    def test_legacy_template_backward_compatibility(self):
        legacy_data = {
            "id": "old_template",
            "name": "Old Template",
            "sections": [
                {"type": "header_metadata"},
                {"type": "executive_summary"},
            ],
        }
        loaded = dict_to_template(legacy_data)
        self.assertIsNotNone(loaded)
        self.assertFalse(loaded.sections[0].page_break_before)
        self.assertFalse(loaded.sections[1].page_break_before)


class TestToolbarPageBreak(unittest.TestCase):
    """Test toolbar insert_page_break action."""

    def test_insert_page_break_empty_editor(self):
        editor = QPlainTextEdit()
        insert_page_break(editor)
        self.assertIn(PAGEBREAK_MARKER, editor.toPlainText())

    def test_insert_page_break_at_cursor(self):
        editor = QPlainTextEdit()
        editor.setPlainText("Line 1\n\nLine 2")
        # Place cursor at start of Line 2
        cursor = editor.textCursor()
        cursor.setPosition(8)
        editor.setTextCursor(cursor)

        insert_page_break(editor)
        text = editor.toPlainText()
        self.assertIn(PAGEBREAK_MARKER, text)
        self.assertIn("Line 1", text)
        self.assertIn("Line 2", text)
        self.assertLess(text.find("Line 1"), text.find(PAGEBREAK_MARKER))
        self.assertLess(text.find(PAGEBREAK_MARKER), text.find("Line 2"))

    def test_insert_page_break_undo_redo(self):
        editor = QPlainTextEdit()
        editor.setPlainText("Initial Text")
        insert_page_break(editor)
        self.assertIn(PAGEBREAK_MARKER, editor.toPlainText())

        editor.undo()
        self.assertEqual(editor.toPlainText(), "Initial Text")

        editor.redo()
        self.assertIn(PAGEBREAK_MARKER, editor.toPlainText())

    def test_insert_spacer_uses_selected_bounded_size(self):
        editor = QPlainTextEdit()
        editor.setPlainText("Before")

        insert_spacer(editor, "medium")

        self.assertIn("<!-- spectre:spacer:medium -->", editor.toPlainText())
        editor.undo()
        self.assertEqual(editor.toPlainText(), "Before")


if __name__ == "__main__":
    unittest.main()

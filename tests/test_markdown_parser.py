"""
Pure headless tests for _MarkdownHtmlParser and markdown-to-HTML conversion.
Ensures parser state machine transitions, flushing invariants, and security escaping work properly.
"""

import unittest
from core.reporting.markdown import _MarkdownHtmlParser, convert_markdown_to_html


class TestMarkdownHtmlParser(unittest.TestCase):
    """Direct headless unit tests for _MarkdownHtmlParser."""

    def setUp(self) -> None:
        self.parser = _MarkdownHtmlParser()

    def test_empty_parse(self) -> None:
        result = self.parser.parse("")
        self.assertEqual(result, "")

    def test_headings_h1_to_h4(self) -> None:
        md = "# Heading 1\n## Heading 2\n### Heading 3\n#### Heading 4"
        html = self.parser.parse(md)
        self.assertIn("<h1>Heading 1</h1>", html)
        self.assertIn("<h2>Heading 2</h2>", html)
        self.assertIn("<h3>Heading 3</h3>", html)
        self.assertIn("<h4>Heading 4</h4>", html)

    def test_fenced_code_block_with_language_and_escaping(self) -> None:
        md = "```python\ndef test():\n    print('<script>alert(1)</script>')\n```"
        html = self.parser.parse(md)
        self.assertIn('<pre><code class="language-python">', html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_unclosed_code_block_flushes_at_eof(self) -> None:
        md = "```bash\necho 'hello world'"
        html = self.parser.parse(md)
        self.assertIn('<pre><code class="language-bash">echo &#x27;hello world&#x27;</code></pre>', html)

    def test_unordered_list_flushing(self) -> None:
        md = "- Alpha\n* Beta\n- Gamma\n\nParagraph after list."
        html = self.parser.parse(md)
        self.assertIn("<ul>", html)
        self.assertIn("<li>Alpha</li>", html)
        self.assertIn("<li>Beta</li>", html)
        self.assertIn("<li>Gamma</li>", html)
        self.assertIn("</ul>", html)
        self.assertIn("<p>Paragraph after list.</p>", html)

    def test_ordered_list_flushing(self) -> None:
        md = "1. First\n2. Second\n3. Third"
        html = self.parser.parse(md)
        self.assertIn("<ol>", html)
        self.assertIn("<li>First</li>", html)
        self.assertIn("<li>Second</li>", html)
        self.assertIn("<li>Third</li>", html)
        self.assertIn("</ol>", html)

    def test_list_type_transition(self) -> None:
        md = "- Bullet\n1. Numbered"
        html = self.parser.parse(md)
        self.assertIn("<ul>\n<li>Bullet</li>\n</ul>", html)
        self.assertIn("<ol>\n<li>Numbered</li>\n</ol>", html)

    def test_table_parsing_and_rendering(self) -> None:
        md = "| Header 1 | Header 2 |\n| --- | --- |\n| Cell 1 | Cell 2 |"
        html = self.parser.parse(md)
        self.assertIn('<div class="table-container"><table>', html)
        self.assertIn("<th>Header 1</th>", html)
        self.assertIn("<th>Header 2</th>", html)
        self.assertIn("<td>Cell 1</td>", html)
        self.assertIn("<td>Cell 2</td>", html)
        self.assertIn("</table></div>", html)

    def test_blockquote_flushing(self) -> None:
        md = "> Note: Check permissions.\n> Important context.\n\nRegular text."
        html = self.parser.parse(md)
        self.assertIn("<blockquote>", html)
        self.assertIn("Note: Check permissions.<br>Important context.", html)
        self.assertIn("</blockquote>", html)
        self.assertIn("<p>Regular text.</p>", html)

    def test_horizontal_rules(self) -> None:
        for hr in ["---", "***", "___"]:
            md = f"Top\n\n{hr}\n\nBottom"
            html = self.parser.parse(md)
            self.assertIn("<hr>", html)

    def test_pagebreak_and_spacer_markers(self) -> None:
        md = "Before\n<!-- spectre:pagebreak -->\n<!-- spectre:spacer:medium -->\nAfter"
        html = self.parser.parse(md)
        self.assertIn('class="spectre-page-break"', html)
        self.assertIn('class="spectre-spacer spacer-medium"', html)

    def test_convert_markdown_to_html_convenience_function(self) -> None:
        md = "# Test\nParagraph with **bold** and `code`."
        html = convert_markdown_to_html(md)
        self.assertIn("<h1>Test</h1>", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<code>code</code>", html)


if __name__ == "__main__":
    unittest.main()

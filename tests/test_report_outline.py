"""Tests for core/reporting/outline.py (Tier 0 pure logic)."""

import unittest
from core.reporting.outline import HeadingItem, extract_headings


class TestReportOutline(unittest.TestCase):
    def test_extract_headings_empty_text(self):
        self.assertEqual(extract_headings(""), [])
        self.assertEqual(extract_headings("   \n\n  "), [])

    def test_extract_headings_simple_hierarchy(self):
        doc = (
            "# Report Title\n"
            "Introduction text.\n"
            "## 1. Executive Summary\n"
            "Summary text.\n"
            "### 1.1 Scope\n"
            "Scope text.\n"
            "## 2. Technical Findings\n"
            "#### Deep Finding\n"
        )
        items = extract_headings(doc)
        expected = [
            HeadingItem(level=1, title="Report Title", line_number=1),
            HeadingItem(level=2, title="1. Executive Summary", line_number=3),
            HeadingItem(level=3, title="1.1 Scope", line_number=5),
            HeadingItem(level=2, title="2. Technical Findings", line_number=7),
            HeadingItem(level=4, title="Deep Finding", line_number=8),
        ]
        self.assertEqual(items, expected)

    def test_extract_headings_ignores_code_blocks(self):
        doc = (
            "# Top Heading\n"
            "```bash\n"
            "# This is a bash comment, not a markdown heading\n"
            "## Another comment\n"
            "cat /etc/passwd\n"
            "```\n"
            "## Real Heading\n"
            "```python\n"
            "# Python comment\n"
            "```\n"
            "### Final Subsection\n"
        )
        items = extract_headings(doc)
        expected = [
            HeadingItem(level=1, title="Top Heading", line_number=1),
            HeadingItem(level=2, title="Real Heading", line_number=7),
            HeadingItem(level=3, title="Final Subsection", line_number=11),
        ]
        self.assertEqual(items, expected)

    def test_extract_headings_strips_trailing_hashes(self):
        doc = "## Section with closing hashes ##\n### Level 3 ###"
        items = extract_headings(doc)
        self.assertEqual(items[0].title, "Section with closing hashes")
        self.assertEqual(items[1].title, "Level 3")

    def test_extract_headings_strips_html_badges(self):
        doc = (
            "### <span class=\"severity-pill severity-high\">🟠 HIGH</span> SQL Injection\n"
            "#### <span class=\"severity-pill severity-critical\">🔴 CRITICAL</span> RCE Exploit\n"
        )
        items = extract_headings(doc)
        self.assertEqual(items[0].title, "🟠 HIGH SQL Injection")
        self.assertEqual(items[1].title, "🔴 CRITICAL RCE Exploit")


if __name__ == "__main__":
    unittest.main()

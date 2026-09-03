"""Extracts hierarchical headings from Markdown documents for outline navigation."""

from dataclasses import dataclass
import re

_FENCE_PATTERN = re.compile(r"^```")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class HeadingItem:
    """Represents a Markdown heading with its hierarchy level, title, and line number."""

    level: int  # 1 to 6
    title: str  # cleaned title text
    line_number: int  # 1-based line number


def extract_headings(markdown_text: str) -> list[HeadingItem]:
    """
    Extracts all headings (H1-H6) from markdown text.
    Correctly ignores any headings or # comments found inside code blocks (```).
    Returns a list of HeadingItem instances in document order.
    """
    headings: list[HeadingItem] = []
    in_code_block = False

    for line_idx, line in enumerate(markdown_text.splitlines(), start=1):
        stripped = line.strip()
        if _FENCE_PATTERN.match(stripped):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        match = _HEADING_PATTERN.match(stripped)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            # Remove trailing closing hashes if present, e.g. "## Title ##"
            title = re.sub(r"\s+#+$", "", title).strip()
            # Strip inline HTML tags (e.g. <span class="severity-pill...">...</span>) for clean navigation labels
            title = re.sub(r"<[^>]+>", "", title).strip()
            if title:
                headings.append(HeadingItem(level=level, title=title, line_number=line_idx))

    return headings

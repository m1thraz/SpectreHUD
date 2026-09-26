"""Semantic print-layout policies shared by report renderers and CSS."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class PrintLayoutPolicy:
    page_start: bool = False
    page_end: bool = False
    keep_together: bool = False
    keep_with_next: bool = False
    breakable: bool = False

    def __post_init__(self) -> None:
        if self.keep_together and self.breakable:
            raise ValueError("A print block cannot be both keep-together and breakable")

    def html_attribute(self) -> str:
        directives = []
        if self.page_start:
            directives.append("page-start")
        if self.page_end:
            directives.append("page-end")
        if self.keep_together:
            directives.append("keep-together")
        if self.keep_with_next:
            directives.append("keep-with-next")
        if self.breakable:
            directives.append("breakable")
        if not directives:
            return ""
        return f'data-print-layout="{" ".join(directives)}"'


PRINT_PAGE_START = PrintLayoutPolicy(page_start=True)
PRINT_PAGE_END = PrintLayoutPolicy(page_end=True)
PRINT_KEEP_TOGETHER = PrintLayoutPolicy(keep_together=True)
PRINT_KEEP_WITH_NEXT = PrintLayoutPolicy(keep_with_next=True)
PRINT_BREAKABLE = PrintLayoutPolicy(breakable=True)

SECTION_PRINT_LAYOUT_POLICIES = {
    "executive_summary": PRINT_PAGE_END,
    "finding_section": PRINT_PAGE_START,
    "appendix": PRINT_PAGE_START,
}


def section_print_layout_attribute(section_type: str) -> str:
    policy = SECTION_PRINT_LAYOUT_POLICIES.get(section_type, PrintLayoutPolicy())
    return policy.html_attribute()


def annotate_table_print_layout(html: str) -> str:
    """Add table policies after semantic table projection and pruning are complete."""
    if not html:
        return html

    def annotate(match: re.Match[str], policy: PrintLayoutPolicy) -> str:
        attributes = match.group("attributes")
        if "data-print-layout=" in attributes:
            return match.group(0)
        return f"<{match.group('tag')}{attributes} {policy.html_attribute()}>"

    html = re.sub(
        r"<(?P<tag>table)(?P<attributes>[^>]*)>",
        lambda match: annotate(match, PRINT_BREAKABLE),
        html,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r"<(?P<tag>tr)(?P<attributes>[^>]*)>",
        lambda match: annotate(match, PRINT_KEEP_TOGETHER),
        html,
        flags=re.IGNORECASE,
    )

"""Semantic print-layout policies shared by report renderers and CSS."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrintLayoutPolicy:
    page_start: bool = False
    keep_together: bool = False
    keep_with_next: bool = False

    def html_attribute(self) -> str:
        directives = []
        if self.page_start:
            directives.append("page-start")
        if self.keep_together:
            directives.append("keep-together")
        if self.keep_with_next:
            directives.append("keep-with-next")
        if not directives:
            return ""
        return f'data-print-layout="{" ".join(directives)}"'


PRINT_PAGE_START = PrintLayoutPolicy(page_start=True)
PRINT_KEEP_TOGETHER = PrintLayoutPolicy(keep_together=True)
PRINT_KEEP_WITH_NEXT = PrintLayoutPolicy(keep_with_next=True)

SECTION_PRINT_LAYOUT_POLICIES = {
    "appendix": PRINT_PAGE_START,
}


def section_print_layout_attribute(section_type: str) -> str:
    policy = SECTION_PRINT_LAYOUT_POLICIES.get(section_type, PrintLayoutPolicy())
    return policy.html_attribute()

"""Deterministic pagination planning for semantic report HTML."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
import math
import re
from typing import Iterable

from core.reporting.print_layout import PrintLayoutPolicy


DEFAULT_PRINTABLE_HEIGHT_MM = 255.0
PLANNED_PAGE_START_ATTRIBUTE = 'data-print-plan="page-start"'
FINDING_OPENING_RESERVE_MM = 56.0


@dataclass(frozen=True)
class PaginationBlock:
    """One measured flow block consumed by the pagination planner."""

    block_id: str
    height_mm: float
    policy: PrintLayoutPolicy = PrintLayoutPolicy()
    following_height_mm: float = 0.0
    explicit_page_start: bool = False

    def __post_init__(self) -> None:
        if self.height_mm < 0 or self.following_height_mm < 0:
            raise ValueError("Pagination block heights cannot be negative")


@dataclass(frozen=True)
class PaginationPlacement:
    """Resolved position and optional soft break for one flow block."""

    block_id: str
    page_number: int
    offset_mm: float
    break_before: bool = False


@dataclass(frozen=True)
class PaginationPlan:
    placements: tuple[PaginationPlacement, ...]

    @property
    def break_before_ids(self) -> tuple[str, ...]:
        return tuple(
            placement.block_id for placement in self.placements if placement.break_before
        )


class PaginationPlanner:
    """Plan conservative soft breaks without replacing the browser paginator."""

    def __init__(self, printable_height_mm: float = DEFAULT_PRINTABLE_HEIGHT_MM) -> None:
        if printable_height_mm <= 0:
            raise ValueError("Printable page height must be positive")
        self.printable_height_mm = printable_height_mm

    def plan(self, blocks: Iterable[PaginationBlock]) -> PaginationPlan:
        page_number = 1
        used_mm = 0.0
        placements: list[PaginationPlacement] = []
        seen_ids: set[str] = set()

        for block in blocks:
            if block.block_id in seen_ids:
                raise ValueError(f"Duplicate pagination block id: {block.block_id}")
            seen_ids.add(block.block_id)

            break_before = False
            if block.explicit_page_start:
                if used_mm > 0:
                    page_number += 1
                used_mm = 0.0
            else:
                guarded_height = block.height_mm
                if block.policy.keep_with_next:
                    guarded_height += block.following_height_mm
                can_fit_one_page = guarded_height <= self.printable_height_mm
                would_overflow = used_mm > 0 and used_mm + guarded_height > self.printable_height_mm
                if (
                    can_fit_one_page
                    and would_overflow
                    and (block.policy.keep_together or block.policy.keep_with_next)
                ):
                    page_number += 1
                    used_mm = 0.0
                    break_before = True

            placements.append(
                PaginationPlacement(
                    block_id=block.block_id,
                    page_number=page_number,
                    offset_mm=used_mm,
                    break_before=break_before,
                )
            )
            page_number, used_mm = self._advance(page_number, used_mm, block.height_mm)

        return PaginationPlan(tuple(placements))

    def _advance(self, page_number: int, used_mm: float, height_mm: float) -> tuple[int, float]:
        total = used_mm + height_mm
        if total <= self.printable_height_mm:
            return page_number, total
        completed_pages = math.floor(total / self.printable_height_mm)
        remainder = total % self.printable_height_mm
        if math.isclose(remainder, 0.0, abs_tol=1e-9):
            return page_number + max(0, completed_pages - 1), self.printable_height_mm
        return page_number + completed_pages, remainder


@dataclass
class _HtmlNode:
    tag: str
    attrs: dict[str, str]
    start: int
    start_end: int
    end_start: int | None = None
    children: list["_HtmlNode"] = field(default_factory=list)

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    @property
    def layout_directives(self) -> set[str]:
        return set(self.attrs.get("data-print-layout", "").split())


class _LayoutHtmlParser(HTMLParser):
    _VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta"}

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.roots: list[_HtmlNode] = []
        self.stack: list[_HtmlNode] = []
        self._line_offsets = [0]
        for match in re.finditer(r"\n", source):
            self._line_offsets.append(match.end())

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_offsets[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        start = self._offset()
        raw = self.get_starttag_text() or ""
        node = _HtmlNode(
            tag=tag.lower(),
            attrs={name.lower(): value or "" for name, value in attrs},
            start=start,
            start_end=start + len(raw),
        )
        if self.stack:
            self.stack[-1].children.append(node)
        else:
            self.roots.append(node)
        if node.tag not in self._VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1].tag == tag.lower():
            self.stack[-1].end_start = self.stack[-1].start_end
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].tag != lowered:
                continue
            end_start = self._offset()
            for node in self.stack[index:]:
                if node.end_start is None:
                    node.end_start = end_start
            del self.stack[index:]
            return


@dataclass(frozen=True)
class _HtmlFlowBlock:
    block: PaginationBlock
    insertion_offset: int | None = None


def plan_professional_pagination(
    html: str,
    *,
    printable_height_mm: float = DEFAULT_PRINTABLE_HEIGHT_MM,
) -> str:
    """Insert conservative soft page starts into Professional Print body HTML."""
    if not html:
        return html
    clean_html = re.sub(r'\sdata-print-plan="page-start"', "", html, flags=re.IGNORECASE)
    parser = _LayoutHtmlParser(clean_html)
    parser.feed(clean_html)
    flow = _build_flow(parser.roots, clean_html)
    if not flow:
        return clean_html

    plan = PaginationPlanner(printable_height_mm).plan(item.block for item in flow)
    offsets_by_id = {
        item.block.block_id: item.insertion_offset
        for item in flow
        if item.insertion_offset is not None
    }
    offsets = {
        offsets_by_id[block_id]
        for block_id in plan.break_before_ids
        if offsets_by_id.get(block_id) is not None
    }
    for offset in sorted(offsets, reverse=True):
        insert_at = offset - 1
        if clean_html[insert_at - 1 : insert_at] == "/":
            insert_at -= 1
        clean_html = (
            clean_html[:insert_at]
            + f" {PLANNED_PAGE_START_ATTRIBUTE}"
            + clean_html[insert_at:]
        )
    return clean_html


def _build_flow(nodes: Iterable[_HtmlNode], source: str) -> list[_HtmlFlowBlock]:
    flow: list[_HtmlFlowBlock] = []
    serial = 0

    def add(
        node: _HtmlNode,
        height_mm: float,
        policy: PrintLayoutPolicy = PrintLayoutPolicy(),
        *,
        following_height_mm: float = 0.0,
        explicit_page_start: bool = False,
        eligible: bool = False,
    ) -> None:
        nonlocal serial
        serial += 1
        flow.append(
            _HtmlFlowBlock(
                PaginationBlock(
                    block_id=f"block-{serial}",
                    height_mm=height_mm,
                    policy=policy,
                    following_height_mm=following_height_mm,
                    explicit_page_start=explicit_page_start,
                ),
                insertion_offset=node.start_end if eligible else None,
            )
        )

    def visit(node: _HtmlNode) -> None:
        classes = node.classes
        directives = node.layout_directives
        if "spectre-page-break" in classes:
            add(node, 0.0, explicit_page_start=True)
            return
        if "report-cover" in classes:
            add(node, DEFAULT_PRINTABLE_HEIGHT_MM, explicit_page_start=True)
            return
        if "report-section" in classes:
            is_page_start = "page-start" in directives
            add(
                node,
                13.8,
                PrintLayoutPolicy(keep_with_next=True),
                following_height_mm=18.0,
                explicit_page_start=is_page_start,
                eligible=not is_page_start,
            )
            for child in node.children:
                visit(child)
            return
        if "report-finding" in classes:
            add(
                node,
                4.0,
                PrintLayoutPolicy(keep_with_next=True),
                # The browser may split a finding body, but never strand its
                # lead. Reserving the lead plus opening paragraph is enough;
                # the previous 75 mm guard forced medium findings onto mostly
                # empty individual pages.
                following_height_mm=FINDING_OPENING_RESERVE_MM,
                eligible=True,
            )
            for child in node.children:
                visit(child)
            return
        if "attack-path-step" in classes:
            add(
                node,
                _estimate_atomic_height(node, source, minimum=31.0, chars_per_line=78),
                PrintLayoutPolicy(keep_together=True),
            )
            return
        if "finding-lead" in classes:
            add(node, _estimate_finding_lead(node, source))
            return
        if "screenshot-container" in classes or node.tag == "figure":
            add(node, 105.0, PrintLayoutPolicy(keep_together=True))
            return
        if "spectre-spacer" in classes:
            spacer_height = 5.0 if "spacer-small" in classes else 10.0
            if "spacer-large" in classes:
                spacer_height = 18.0
            add(node, spacer_height)
            return
        if node.tag == "pre":
            height = _estimate_pre_height(node, source)
            keep_together = "breakable" not in directives
            add(
                node,
                height,
                PrintLayoutPolicy(keep_together=keep_together, breakable=not keep_together),
            )
            return
        if node.tag == "blockquote":
            add(
                node,
                _estimate_atomic_height(node, source, minimum=16.0, chars_per_line=82),
                PrintLayoutPolicy(keep_together=True),
            )
            return
        if node.tag == "tr":
            add(
                node,
                _estimate_table_row_height(node, source),
                PrintLayoutPolicy(keep_together=True),
            )
            return
        if node.tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li"}:
            add(node, _estimate_text_block_height(node, source))
            return
        for child in node.children:
            visit(child)

    for root in nodes:
        visit(root)
    return flow


def _inner_html(node: _HtmlNode, source: str) -> str:
    end = node.end_start if node.end_start is not None else node.start_end
    return source[node.start_end:end]


def _plain_text(node: _HtmlNode, source: str) -> str:
    raw = re.sub(r"<[^>]+>", " ", _inner_html(node, source))
    return re.sub(r"\s+", " ", unescape(raw)).strip()


def _estimated_lines(text: str, chars_per_line: int) -> int:
    return max(1, math.ceil(len(text) / chars_per_line))


def _estimate_text_block_height(node: _HtmlNode, source: str) -> float:
    text = _plain_text(node, source)
    widths = {"h1": 44, "h2": 48, "h3": 58, "h4": 66, "h5": 72, "h6": 72}
    if node.tag in widths:
        line_height = {"h1": 10.0, "h2": 8.5, "h3": 7.0, "h4": 6.2}.get(node.tag, 5.8)
        margin = {"h1": 12.0, "h2": 12.0, "h3": 9.0, "h4": 7.0}.get(node.tag, 6.0)
        return margin + _estimated_lines(text, widths[node.tag]) * line_height
    chars_per_line = 88 if node.tag == "p" else 78
    line_height = 6.8 if node.tag == "p" else 6.4
    margin = 3.8 if node.tag == "p" else 2.8
    return margin + _estimated_lines(text, chars_per_line) * line_height


def _estimate_atomic_height(
    node: _HtmlNode,
    source: str,
    *,
    minimum: float,
    chars_per_line: int,
) -> float:
    text = _plain_text(node, source)
    return max(minimum, 10.0 + _estimated_lines(text, chars_per_line) * 6.5)


def _estimate_finding_lead(node: _HtmlNode, source: str) -> float:
    metadata_items = _inner_html(node, source).count("finding-meta-item")
    text_lines = _estimated_lines(_plain_text(node, source), 76)
    return max(34.0, 18.0 + metadata_items * 4.0 + text_lines * 3.0)


def _estimate_pre_height(node: _HtmlNode, source: str) -> float:
    raw = unescape(re.sub(r"<[^>]+>", "", _inner_html(node, source)))
    visual_lines = sum(max(1, math.ceil(len(line) / 92)) for line in raw.splitlines() or [""])
    return 9.0 + visual_lines * 4.7


def _estimate_table_row_height(node: _HtmlNode, source: str) -> float:
    cells = re.findall(r"<(?:th|td)\b[^>]*>(.*?)</(?:th|td)>", _inner_html(node, source), re.I | re.S)
    longest = max((_plain_cell_text(cell) for cell in cells), key=len, default="")
    return 7.0 + _estimated_lines(longest, 32) * 5.2


def _plain_cell_text(raw: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", raw))).strip()

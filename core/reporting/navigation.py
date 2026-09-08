"""Read-only semantic navigation index for the current report Markdown."""

from dataclasses import dataclass
import re

from core.reporting.findings import FINDING_END_RE, FINDING_START_RE
from core.reporting.outline import extract_headings
from core.reporting.section_markers import (
    SECTION_END_RE,
    SECTION_START_RE,
    segment_report_markdown,
)


@dataclass(frozen=True)
class ReportNavigationEntry:
    kind: str
    identity: str
    title: str
    line_number: int


@dataclass(frozen=True)
class ReportNavigationIndex:
    sections: tuple[ReportNavigationEntry, ...]
    findings: tuple[ReportNavigationEntry, ...]


def _display_identity(identity: str) -> str:
    parts = identity.split(":")
    meaningful = parts[1] if parts[0] == "phase_section" and len(parts) > 1 else parts[0]
    return meaningful.replace("_", " ").replace("-", " ").title()


def _first_visible_line(markdown: str, start: int, end: int) -> int:
    position = start
    for line in markdown[start:end].splitlines(keepends=True):
        stripped = line.strip()
        if stripped and not (stripped.startswith("<!--") and stripped.endswith("-->")):
            return markdown.count("\n", 0, position) + 1
        position += len(line)
    return markdown.count("\n", 0, start) + 1


def _title_from_markdown(markdown: str, fallback: str) -> str:
    headings = extract_headings(markdown)
    return headings[0].title if headings else fallback


def _matching_end(
    markdown: str,
    start: re.Match[str],
    end_pattern: re.Pattern[str],
    next_start: re.Match[str] | None,
) -> re.Match[str] | None:
    identity = start.group(1).lower()
    end = next(
        (
            candidate
            for candidate in end_pattern.finditer(markdown, start.end())
            if candidate.group(1).lower() == identity
        ),
        None,
    )
    if end is None or (next_start is not None and next_start.start() < end.start()):
        return None
    return end


def _section_entries(markdown: str) -> tuple[ReportNavigationEntry, ...]:
    entries: list[ReportNavigationEntry] = []
    cursor = 0
    for segment in segment_report_markdown(markdown):
        if not segment.is_structured or not segment.identity:
            continue
        start = next(
            (
                candidate
                for candidate in SECTION_START_RE.finditer(markdown, cursor)
                if candidate.group(1).lower() == segment.identity
            ),
            None,
        )
        if start is None:
            continue
        end = _matching_end(
            markdown,
            start,
            SECTION_END_RE,
            SECTION_START_RE.search(markdown, start.end()),
        )
        if end is None:
            continue
        entries.append(
            ReportNavigationEntry(
                kind="section",
                identity=segment.identity,
                title=_title_from_markdown(
                    segment.markdown, _display_identity(segment.identity)
                ),
                line_number=_first_visible_line(markdown, start.end(), end.start()),
            )
        )
        cursor = end.end()
    return tuple(entries)


def _finding_entries(markdown: str) -> tuple[ReportNavigationEntry, ...]:
    entries: list[ReportNavigationEntry] = []
    cursor = 0
    while start := FINDING_START_RE.search(markdown, cursor):
        next_start = FINDING_START_RE.search(markdown, start.end())
        end = _matching_end(markdown, start, FINDING_END_RE, next_start)
        if end is None:
            break
        identity = start.group(1)
        body = markdown[start.end():end.start()]
        entries.append(
            ReportNavigationEntry(
                kind="finding",
                identity=identity,
                title=_title_from_markdown(body, _display_identity(identity)),
                line_number=_first_visible_line(markdown, start.end(), end.start()),
            )
        )
        cursor = end.end()
    return tuple(entries)


def build_report_navigation(markdown: str) -> ReportNavigationIndex:
    """Index only marker pairs that are valid in the current in-memory document."""
    return ReportNavigationIndex(
        sections=_section_entries(markdown),
        findings=_finding_entries(markdown),
    )

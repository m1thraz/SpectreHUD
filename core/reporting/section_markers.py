"""Persistent semantic section markers and defensive report segmentation."""

from dataclasses import dataclass
import re
from typing import Optional


KNOWN_SECTION_TYPES = frozenset(
    {
        "header_metadata",
        "executive_summary",
        "scope_limitations",
        "phase_section",
        "attack_path",
        "finding_section",
        "remediation_table",
        "appendix",
    }
)
SECTION_START_RE = re.compile(
    r"^<!--\s*spectre:section:start:([a-z0-9_-]+(?:[:][a-z0-9_-]+)*)\s*-->\s*$",
    re.IGNORECASE | re.MULTILINE,
)
SECTION_END_RE = re.compile(
    r"^<!--\s*spectre:section:end:([a-z0-9_-]+(?:[:][a-z0-9_-]+)*)\s*-->\s*$",
    re.IGNORECASE | re.MULTILINE,
)
SECTION_MARKER_RE = re.compile(
    r"^<!--\s*spectre:section:(?:start|end):[a-z0-9_-]+(?:[:][a-z0-9_-]+)*\s*-->\s*\r?\n?",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class RenderedSection:
    section_type: str
    markdown: str
    category_id: Optional[str] = None
    identity: Optional[str] = None

    @property
    def is_structured(self) -> bool:
        return self.section_type in KNOWN_SECTION_TYPES


def section_base_identity(section_type: str, category_id: Optional[str] = None) -> str:
    identity = re.sub(r"[^a-z0-9_-]+", "-", str(section_type).strip().lower()).strip("-")
    if identity == "phase_section" and category_id:
        category = re.sub(
            r"[^a-z0-9_-]+", "-", str(category_id).strip().lower()
        ).strip("-")
        if category:
            identity += f":{category}"
    return identity


def section_identity(
    section_type: str,
    category_id: Optional[str] = None,
    *,
    ordinal: Optional[int] = None,
) -> str:
    identity = section_base_identity(section_type, category_id)
    return f"{identity}:{ordinal}" if ordinal is not None else identity


def wrap_section_markdown(markdown: str, identity: str) -> str:
    return (
        f"<!-- spectre:section:start:{identity} -->\n\n"
        f"{markdown}\n\n"
        f"<!-- spectre:section:end:{identity} -->"
    )


def strip_section_markers(markdown: str) -> str:
    return SECTION_MARKER_RE.sub("", markdown)


def _next_content_line(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped and not SECTION_MARKER_RE.fullmatch(stripped):
            return stripped
    return ""


def _insert_marker_before_line(markdown: str, marker: str, anchor: str, start: int) -> tuple[str, int]:
    index = markdown.find(anchor, start)
    if index < 0:
        return markdown, start
    line_start = markdown.rfind("\n", 0, index) + 1
    prefix = markdown[:line_start]
    separator = "" if not prefix or prefix.endswith("\n\n") else "\n"
    insertion = f"{separator}{marker}\n\n"
    return markdown[:line_start] + insertion + markdown[line_start:], line_start + len(insertion)


def reconcile_section_markers(original_markdown: str, converted_markdown: str) -> str:
    """Restore valid section pairs that Qt drops while retaining their edited content."""
    if not original_markdown or not converted_markdown or "spectre:section:start:" not in original_markdown:
        return converted_markdown

    pairs: list[tuple[str, str, str]] = []
    cursor = 0
    while start_match := SECTION_START_RE.search(original_markdown, cursor):
        identity = start_match.group(1).lower()
        end_match = next(
            (
                match
                for match in SECTION_END_RE.finditer(original_markdown, start_match.end())
                if match.group(1).lower() == identity
            ),
            None,
        )
        next_start = SECTION_START_RE.search(original_markdown, start_match.end())
        if end_match is None or (next_start and next_start.start() < end_match.start()):
            break
        start_anchor = _next_content_line(
            original_markdown[start_match.end():end_match.start()]
        )
        end_anchor = _next_content_line(original_markdown[end_match.end():])
        if start_anchor:
            pairs.append((identity, start_anchor, end_anchor))
        cursor = end_match.end()

    result = converted_markdown
    search_start = 0
    for identity, start_anchor, end_anchor in pairs:
        start_marker = f"<!-- spectre:section:start:{identity} -->"
        end_marker = f"<!-- spectre:section:end:{identity} -->"
        if start_marker not in result:
            result, search_start = _insert_marker_before_line(
                result, start_marker, start_anchor, search_start
            )
        section_start = result.find(start_anchor, search_start)
        if section_start < 0:
            continue
        if end_marker not in result:
            if end_anchor:
                result, end_position = _insert_marker_before_line(
                    result, end_marker, end_anchor, section_start + len(start_anchor)
                )
                search_start = end_position
            else:
                result = result.rstrip() + f"\n\n{end_marker}\n"
                search_start = len(result)
        else:
            search_start = result.find(end_marker, section_start) + len(end_marker)
    return result


def _identity_parts(identity: str) -> tuple[str, Optional[str]]:
    parts = identity.lower().split(":")
    section_type = parts[0]
    category_id = parts[1] if section_type == "phase_section" and len(parts) > 1 else None
    return section_type, category_id


def segment_report_markdown(markdown: str) -> list[RenderedSection]:
    """Split valid marker pairs while preserving malformed or unknown input verbatim."""
    if not markdown:
        return []

    segments: list[RenderedSection] = []
    cursor = 0
    while start := SECTION_START_RE.search(markdown, cursor):
        if start.start() > cursor:
            segments.append(RenderedSection("unstructured", markdown[cursor:start.start()]))

        identity = start.group(1).lower()
        next_start = SECTION_START_RE.search(markdown, start.end())
        matching_end = next(
            (
                match
                for match in SECTION_END_RE.finditer(markdown, start.end())
                if match.group(1).lower() == identity
            ),
            None,
        )
        if matching_end is None or (next_start and next_start.start() < matching_end.start()):
            segments.append(RenderedSection("unstructured", markdown[start.start():]))
            cursor = len(markdown)
            break

        section_type, category_id = _identity_parts(identity)
        block_end = matching_end.end()
        if section_type not in KNOWN_SECTION_TYPES:
            segments.append(RenderedSection("unstructured", markdown[start.start():block_end]))
        else:
            content = markdown[start.end():matching_end.start()]
            content = re.sub(r"^(?:\r?\n){1,2}", "", content, count=1)
            content = re.sub(r"(?:\r?\n){1,2}$", "", content, count=1)
            segments.append(RenderedSection(section_type, content, category_id, identity))
        cursor = block_end

    if cursor < len(markdown):
        segments.append(RenderedSection("unstructured", markdown[cursor:]))
    return segments

"""Persistent finding boundaries and report-specific HTML presentation."""

import re
from pathlib import Path
from typing import Optional

from core.reporting.markdown import convert_markdown_to_html, resolve_and_embed_images


FINDING_START_RE = re.compile(
    r"^<!--\s*spectre:finding:start:([A-Za-z0-9_-]+)\s*-->\s*$",
    re.MULTILINE,
)
FINDING_END_RE = re.compile(
    r"^<!--\s*spectre:finding:end:([A-Za-z0-9_-]+)\s*-->\s*$",
    re.MULTILINE,
)
FINDING_MARKER_RE = re.compile(
    r"^<!--\s*spectre:finding:(?:start|end):[A-Za-z0-9_-]+\s*-->\s*\r?\n?",
    re.MULTILINE,
)
_LOOT_MARKER_LINE_RE = re.compile(
    r"^<!--\s*spectre:loot:[A-Za-z0-9_-]+:[a-fA-F0-9]+\s*-->\s*$"
)


def finding_start_marker(entry_id: str) -> str:
    return f"<!-- spectre:finding:start:{entry_id} -->"


def finding_end_marker(entry_id: str) -> str:
    return f"<!-- spectre:finding:end:{entry_id} -->"


def strip_finding_markers(markdown: str) -> str:
    return FINDING_MARKER_RE.sub("", markdown)


def _semantic_finding_html(body_html: str) -> str:
    heading = re.search(r"<h3>(.*?)</h3>", body_html, re.DOTALL)
    description = re.search(r"<h4>(Description|Beschreibung)</h4>", body_html)
    recommendation = re.search(r"<h4>(Recommendation|Empfehlung)</h4>", body_html)
    if heading is None:
        return body_html

    severity_match = re.search(
        r"<p><strong>Severity:</strong>\s*(.*?)</p>", body_html, re.DOTALL
    )
    severity_html = severity_match.group(1) if severity_match else ""
    severity_class_match = re.search(r"severity-(critical|high|medium|low|info)", severity_html)
    severity_class = (
        f" severity-{severity_class_match.group(1)}" if severity_class_match else ""
    )

    meta_items = []
    for label in ("Target", "Phase", "Observed", "Beobachtet"):
        match = re.search(
            rf"<p><strong>{label}:</strong>\s*(.*?)</p>", body_html, re.DOTALL
        )
        if match:
            meta_items.append(
                '<div class="finding-meta-item">'
                f'<span class="finding-meta-label">{label}</span>'
                f'<span class="finding-meta-value">{match.group(1)}</span>'
                "</div>"
            )
            body_html = body_html.replace(match.group(0), "", 1)

    if severity_match:
        body_html = body_html.replace(severity_match.group(0), "", 1)
    body_html = body_html.replace(heading.group(0), "", 1)
    if description:
        body_html = body_html.replace(
            description.group(0),
            f'<section class="finding-description"><h4>{description.group(1)}</h4>',
            1,
        )
    if recommendation:
        recommendation_open = (
            "</section>" if description else ""
        ) + f'<section class="finding-recommendation"><h4>{recommendation.group(1)}</h4>'
        body_html = body_html.replace(recommendation.group(0), recommendation_open, 1)
    header_severity = (
        f'<div class="finding-severity">{severity_html}</div>' if severity_html else ""
    )
    metadata = (
        f'<div class="finding-meta">{"".join(meta_items)}</div>' if meta_items else ""
    )
    return (
        f'<article class="report-finding{severity_class}">'
        '<header class="finding-header">'
        f"{heading.group(0)}{header_severity}</header>"
        f"{metadata}{body_html}{'</section>' if description or recommendation else ''}</article>"
    )


def convert_markdown_with_findings(
    markdown: str, project_dir: Optional[Path] = None
) -> str:
    """Convert only explicitly marked v1 findings into semantic report articles."""
    if not FINDING_START_RE.search(markdown):
        return convert_markdown_to_html(markdown, project_dir=project_dir)

    embedded = resolve_and_embed_images(markdown, project_dir)
    html_parts = []
    cursor = 0
    while start := FINDING_START_RE.search(embedded, cursor):
        if start.start() > cursor:
            html_parts.append(convert_markdown_to_html(embedded[cursor:start.start()]))
        entry_id = start.group(1)
        end = next(
            (
                match
                for match in FINDING_END_RE.finditer(embedded, start.end())
                if match.group(1) == entry_id
            ),
            None,
        )
        next_start = FINDING_START_RE.search(embedded, start.end())
        if end is None or (next_start and next_start.start() < end.start()):
            html_parts.append(convert_markdown_to_html(embedded[start.start():]))
            cursor = len(embedded)
            break
        finding_markdown = embedded[start.end():end.start()]
        finding_html = convert_markdown_to_html(finding_markdown)
        html_parts.append(_semantic_finding_html(finding_html))
        cursor = end.end()
    if cursor < len(embedded):
        html_parts.append(convert_markdown_to_html(embedded[cursor:]))
    return "\n".join(part for part in html_parts if part)


def phase_section_has_meaningful_content(markdown: str) -> bool:
    if FINDING_START_RE.search(markdown):
        return True

    from core.reporting.loot_sync import strip_report_markers

    cleaned = strip_report_markers(markdown)
    ignored = {
        "*Keine Einträge in dieser Phase.*",
        "*No entries captured for this phase.*",
        "*Keine technischen Findings dokumentiert.*",
        "*No technical findings are documented.*",
        "_Eigene Anmerkungen zu dieser Phase:_",
        "_Notes & observations for this phase:_",
        ">",
    }
    for index, line in enumerate(cleaned.splitlines()):
        stripped = line.strip()
        if stripped.startswith(("<!-- spectre:pagebreak", "<!-- spectre:spacer:")):
            continue
        if index == 0 and stripped.startswith("## "):
            continue
        if stripped and stripped not in ignored:
            return True
    return False


def _next_visible_line(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("<!-- spectre:"):
            continue
        return stripped
    return ""


def _line_start_with_loot_marker(markdown: str, anchor_index: int) -> int:
    line_start = markdown.rfind("\n", 0, anchor_index) + 1
    previous_end = line_start - 1
    if previous_end < 0:
        return line_start
    previous_start = markdown.rfind("\n", 0, previous_end) + 1
    if _LOOT_MARKER_LINE_RE.fullmatch(markdown[previous_start:previous_end].strip()):
        return previous_start
    return line_start


def _insert_before_anchor(
    markdown: str, marker: str, anchor: str, search_start: int
) -> tuple[str, int]:
    index = markdown.find(anchor, search_start)
    if index < 0:
        return markdown, search_start
    line_start = _line_start_with_loot_marker(markdown, index)
    prefix = markdown[:line_start]
    separator = "" if not prefix or prefix.endswith("\n\n") else "\n"
    insertion = f"{separator}{marker}\n"
    return markdown[:line_start] + insertion + markdown[line_start:], line_start + len(insertion)


def reconcile_finding_markers(original: str, converted: str) -> str:
    """Restore valid finding boundaries discarded by the Qt rich-text roundtrip."""
    if not original or not converted:
        return converted
    result = converted
    search_start = 0
    for start in FINDING_START_RE.finditer(original):
        entry_id = start.group(1)
        end = next(
            (
                match
                for match in FINDING_END_RE.finditer(original, start.end())
                if match.group(1) == entry_id
            ),
            None,
        )
        if end is None:
            continue
        heading_anchor = _next_visible_line(original[start.end():end.start()])
        after_anchor = _next_visible_line(original[end.end():])
        if not heading_anchor:
            continue
        start_marker = finding_start_marker(entry_id)
        end_marker = finding_end_marker(entry_id)
        if start_marker not in result:
            result, search_start = _insert_before_anchor(
                result, start_marker, heading_anchor, search_start
            )
        heading_index = result.find(heading_anchor, search_start)
        if heading_index < 0:
            continue
        if end_marker not in result:
            if after_anchor:
                result, search_start = _insert_before_anchor(
                    result, end_marker, after_anchor, heading_index + len(heading_anchor)
                )
            else:
                result = result.rstrip() + f"\n\n{end_marker}\n"
                search_start = len(result)
    return result

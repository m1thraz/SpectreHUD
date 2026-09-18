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
_LOOT_MARKER_LINE_RE = re.compile(r"^<!--\s*spectre:loot:[A-Za-z0-9_-]+:[a-fA-F0-9]+\s*-->\s*$")


def finding_start_marker(entry_id: str) -> str:
    return f"<!-- spectre:finding:start:{entry_id} -->"


def finding_end_marker(entry_id: str) -> str:
    return f"<!-- spectre:finding:end:{entry_id} -->"


def strip_finding_markers(markdown: str) -> str:
    return FINDING_MARKER_RE.sub("", markdown)


def is_meaningful_finding_value(val: Optional[str]) -> bool:
    """Return True if the text represents real content rather than a placeholder dash or empty value."""
    if val is None:
        return False
    v = val.strip()
    if not v:
        return False
    clean = re.sub(r"[*_`#]+", "", v).strip()
    return clean.lower() not in {"", "-", "–", "—", "none", "n/a", "null", "keine", "nicht angegeben"}


def _semantic_finding_html(body_html: str, finding_id: Optional[str] = None) -> str:
    heading = re.search(r"<h3>(.*?)</h3>", body_html, re.DOTALL)
    if heading is None:
        return body_html

    severity_match = re.search(r"<p><strong>Severity:</strong>\s*(.*?)</p>", body_html, re.DOTALL)
    severity_html = severity_match.group(1) if severity_match else ""
    severity_class_match = re.search(r"severity-(critical|high|medium|low|info)", severity_html)
    severity_class = f" severity-{severity_class_match.group(1)}" if severity_class_match else ""

    meta_items = []
    for label in (
        "Target",
        "Phase",
        "Observed",
        "Beobachtet",
        "CVSS Score",
        "CVSS Vector",
        "Status",
    ):
        match = re.search(rf"<p><strong>{label}:</strong>\s*(.*?)</p>", body_html, re.DOTALL)
        if match:
            raw_val = match.group(1).strip()
            plain_val = re.sub(r"<[^>]+>", "", raw_val).strip()
            if not is_meaningful_finding_value(plain_val):
                body_html = body_html.replace(match.group(0), "", 1)
                continue
            meta_items.append(
                '<div class="finding-meta-item'
                + (" finding-meta-cvss-vector" if label == "CVSS Vector" else "")
                + '">'
                f'<span class="finding-meta-label">{label}</span>'
                f'<span class="finding-meta-value">{raw_val}</span>'
                "</div>"
            )
            body_html = body_html.replace(match.group(0), "", 1)

    if severity_match:
        body_html = body_html.replace(severity_match.group(0), "", 1)
    body_html = body_html.replace(heading.group(0), "", 1)

    description = re.search(r"<h4>(Description|Beschreibung)</h4>", body_html)
    recommendation = re.search(r"<h4>(Recommendation|Empfehlung)</h4>", body_html)
    references = re.search(r"<h4>(References|Referenzen)</h4>", body_html)

    # Check and prune empty recommendation block if meaningless
    if recommendation:
        rec_tail = body_html[recommendation.end() :]
        next_h = re.search(r"<h4>", rec_tail)
        rec_content = rec_tail[: next_h.start()] if next_h else rec_tail
        rec_plain = re.sub(r"<[^>]+>", "", rec_content).strip()
        if not is_meaningful_finding_value(rec_plain):
            block_to_remove = body_html[
                recommendation.start() : (recommendation.end() + len(rec_content))
            ]
            body_html = body_html.replace(block_to_remove, "", 1)
            recommendation = None

    # Check and prune empty references block if meaningless
    if references:
        ref_tail = body_html[references.end() :]
        next_h = re.search(r"<h4>", ref_tail)
        ref_content = ref_tail[: next_h.start()] if next_h else ref_tail
        ref_plain = re.sub(r"<[^>]+>", "", ref_content).strip()
        if not is_meaningful_finding_value(ref_plain):
            block_to_remove = body_html[
                references.start() : (references.end() + len(ref_content))
            ]
            body_html = body_html.replace(block_to_remove, "", 1)
            references = None

    if description:
        description_match = re.search(r"<h4>(Description|Beschreibung)</h4>", body_html)
        if description_match:
            body_html = body_html.replace(
                description_match.group(0),
                f'<section class="finding-description"><h4>{description_match.group(1)}</h4>',
                1,
            )
    if recommendation:
        recommendation_match = re.search(r"<h4>(Recommendation|Empfehlung)</h4>", body_html)
        if recommendation_match:
            recommendation_open = (
                "</section>" if description else ""
            ) + f'<section class="finding-recommendation"><h4>{recommendation_match.group(1)}</h4>'
            body_html = body_html.replace(recommendation_match.group(0), recommendation_open, 1)
    if references:
        references_match = re.search(r"<h4>(References|Referenzen)</h4>", body_html)
        if references_match:
            references_open = (
                "</section>" if description or recommendation else ""
            ) + f'<section class="finding-references"><h4>{references_match.group(1)}</h4>'
            body_html = body_html.replace(references_match.group(0), references_open, 1)

    header_severity = (
        f'<div class="finding-severity">{severity_html}</div>' if severity_html else ""
    )
    metadata = f'<div class="finding-meta">{"".join(meta_items)}</div>' if meta_items else ""

    orig_title = heading.group(1).strip()
    m_id = re.match(r"^(F-\d{3})\s*[·\-\:]\s*(.*)$", orig_title)
    if m_id:
        f_id, f_text = m_id.group(1), m_id.group(2).strip()
        styled_heading = f'<h3><span class="finding-id">{f_id}</span> · {f_text}</h3>'
    elif finding_id:
        styled_heading = f'<h3><span class="finding-id">{finding_id}</span> · {orig_title}</h3>'
    else:
        styled_heading = heading.group(0)

    return (
        f'<article class="report-finding{severity_class}">'
        '<header class="finding-header">'
        f"{styled_heading}{header_severity}</header>"
        f"{metadata}{body_html}{'</section>' if description or recommendation or references else ''}</article>"
    )


def convert_markdown_with_findings(
    markdown: str, project_dir: Optional[Path] = None, start_index: int = 1
) -> str:
    """Convert only explicitly marked v1 findings into semantic report articles."""
    if not FINDING_START_RE.search(markdown):
        return convert_markdown_to_html(markdown, project_dir=project_dir)

    embedded = resolve_and_embed_images(markdown, project_dir)
    html_parts = []
    cursor = 0
    finding_index = start_index - 1
    while start := FINDING_START_RE.search(embedded, cursor):
        finding_index += 1
        finding_id = f"F-{finding_index:03d}"
        if start.start() > cursor:
            html_parts.append(convert_markdown_to_html(embedded[cursor : start.start()]))
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
            html_parts.append(convert_markdown_to_html(embedded[start.start() :]))
            cursor = len(embedded)
            break
        finding_markdown = embedded[start.end() : end.start()]
        finding_html = convert_markdown_to_html(finding_markdown)
        html_parts.append(_semantic_finding_html(finding_html, finding_id=finding_id))
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
        heading_anchor = _next_visible_line(original[start.end() : end.start()])
        after_anchor = _next_visible_line(original[end.end() :])
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

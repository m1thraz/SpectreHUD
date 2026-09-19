"""Professional-print projection for attack-path Markdown."""

from __future__ import annotations

import html
import re

from core.reporting.markdown import convert_markdown_to_html, format_inline
from core.reporting.print_layout import PRINT_KEEP_TOGETHER


_STEP_RE = re.compile(
    r"^[ \t]*(\d+)\.\s+(.*?)(?=(?:\n[ \t]*\d+\.\s+|\n[ \t]*##|\n(?=\S)|\Z))",
    re.DOTALL | re.MULTILINE,
)
_PHASE_RE = re.compile(r"^\*\*(.*?)\*\*[:—\-]?\s*(.*)$")
_DESCRIPTION_RE = re.compile(
    r"[-*]\s*[*_]*(?:Beschreibung|Description)[:*_ \t]*\s*(.*)$",
    re.IGNORECASE,
)
_FINDING_RE = re.compile(
    r"[-*]\s*[*_]*(?:Finding|Schwachstelle)[:*_ \t]*\s*(.*)$",
    re.IGNORECASE,
)
_FINDING_MARKER_RE = re.compile(r"\s*<!--\s*finding:.*?\s*-->\s*$", re.IGNORECASE)


def _step_html(number: int, body: str, language: str) -> str:
    lines = body.strip().splitlines()
    first_line = lines[0].strip()
    phase_match = _PHASE_RE.match(first_line)
    if phase_match:
        label = phase_match.group(1).strip()
        title = phase_match.group(2).strip()
    else:
        label = ("Schritt" if language.lower().startswith("de") else "Step") + f" {number:02d}"
        title = first_line

    description = ""
    finding = ""
    for line in lines[1:]:
        stripped = line.strip()
        description_match = _DESCRIPTION_RE.search(stripped)
        if description_match:
            description = description_match.group(1).strip().strip("*_").strip()
        finding_match = _FINDING_RE.search(stripped)
        if finding_match:
            finding = _FINDING_MARKER_RE.sub("", finding_match.group(1)).strip().strip("*_")

    details = ""
    if description:
        details += f'<p class="attack-path-description">{format_inline(description)}</p>'
    if finding:
        finding_label = "Schwachstelle" if language.lower().startswith("de") else "Finding"
        details += (
            '<p class="attack-path-finding">'
            f'<span class="attack-path-finding-label">{finding_label}</span>'
            f"{format_inline(finding)}</p>"
        )

    return (
        f"<article {PRINT_KEEP_TOGETHER.html_attribute()} "
        'class="attack-path-step">'
        f'<div class="attack-path-node">{number:02d}</div>'
        '<div class="attack-path-content">'
        f'<div class="attack-path-phase">{html.escape(label)}</div>'
        f'<div class="attack-path-title">{format_inline(title)}</div>'
        f"{details}</div></article>"
    )


def render_professional_attack_path(markdown: str, language: str) -> str:
    """Render numbered attack steps as a print-safe vertical timeline."""
    matches = list(_STEP_RE.finditer(markdown))
    if not matches:
        return convert_markdown_to_html(markdown)

    prefix = markdown[: matches[0].start()].rstrip()
    parts = [convert_markdown_to_html(prefix)] if prefix else []
    pending_steps: list[str] = []
    cursor = matches[0].start()

    def flush_timeline() -> None:
        if pending_steps:
            parts.append(f'<div class="attack-path-timeline">{"".join(pending_steps)}</div>')
            pending_steps.clear()

    for position, match in enumerate(matches, start=1):
        # Unstructured Markdown between generated steps is user-authored content,
        # so it must remain visible instead of being absorbed by a timeline item.
        gap = markdown[cursor : match.start()].strip()
        if gap:
            flush_timeline()
            parts.append(convert_markdown_to_html(gap))
        pending_steps.append(_step_html(position, match.group(2), language))
        cursor = match.end()

    flush_timeline()
    suffix = markdown[cursor:].strip()
    if suffix:
        parts.append(convert_markdown_to_html(suffix))
    return "\n".join(part for part in parts if part)

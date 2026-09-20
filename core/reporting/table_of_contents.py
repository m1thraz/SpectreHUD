"""Semantic table-of-contents projection for Professional Print exports."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from core.reporting.print_layout import PRINT_PAGE_START


_REPORT_SECTION_OPEN_RE = re.compile(
    r'<section (?P<attrs>[^>]*class="report-section\s+[^\"]+"[^>]*)>',
    re.IGNORECASE,
)
_FINDING_OPEN_RE = re.compile(
    r'<article (?P<attrs>[^>]*class="report-finding(?P<classes>[^\"]*)"[^>]*)>',
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"<h[23][^>]*>(?P<label>.*?)</h[23]>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_SEVERITY_CLASS_RE = re.compile(r"\bseverity-(critical|high|medium|low|info)\b", re.IGNORECASE)
_FINDING_SEVERITY_RE = re.compile(
    r'<div class="finding-severity">(?P<severity>.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class ProfessionalTocResult:
    body_html: str
    toc_html: str


def _plain_label(value: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub("", value)).split())


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def _with_id(opening_tag: str, element_id: str) -> str:
    if re.search(r"\sid=", opening_tag, re.IGNORECASE):
        return opening_tag
    return opening_tag[:-1] + f' id="{element_id}">'


def _annotate_findings(section_html: str, section_index: int) -> tuple[str, list[str]]:
    matches = list(_FINDING_OPEN_RE.finditer(section_html))
    if not matches:
        return section_html, []

    rendered: list[str] = []
    entries: list[str] = []
    cursor = 0
    for finding_index, match in enumerate(matches, start=1):
        end = matches[finding_index].start() if finding_index < len(matches) else len(section_html)
        finding_html = section_html[match.start() : end]
        heading = _HEADING_RE.search(finding_html)
        if heading is None:
            rendered.append(section_html[cursor:end])
            cursor = end
            continue
        label = _plain_label(heading.group("label"))
        if not label:
            rendered.append(section_html[cursor:end])
            cursor = end
            continue
        element_id = (
            f"report-finding-{section_index}-{finding_index}-"
            f"{_slug(label, 'finding')}"
        )
        severity_match = _SEVERITY_CLASS_RE.search(match.group("classes"))
        severity = severity_match.group(1).lower() if severity_match else ""
        if not severity:
            rendered_severity = _FINDING_SEVERITY_RE.search(finding_html)
            severity_label = (
                _plain_label(rendered_severity.group("severity")).lower()
                if rendered_severity
                else ""
            )
            if severity_label in {"critical", "high", "medium", "low", "info"}:
                severity = severity_label
        badge = (
            f'<span class="severity-pill severity-{severity}">{severity.upper()}</span>'
            if severity
            else ""
        )
        entries.append(
            '<li class="report-toc-finding">'
            f'<a href="#{element_id}"><span>{html.escape(label)}</span>{badge}</a>'
            "</li>"
        )
        annotated = _with_id(match.group(0), element_id) + finding_html[match.end() - match.start() :]
        rendered.append(section_html[cursor : match.start()])
        rendered.append(annotated)
        cursor = end
    rendered.append(section_html[cursor:])
    return "".join(rendered), entries


def build_professional_table_of_contents(body_html: str, language: str) -> ProfessionalTocResult:
    """Add link targets and build a localized TOC from rendered report sections."""
    section_matches = list(_REPORT_SECTION_OPEN_RE.finditer(body_html))
    if not section_matches:
        return ProfessionalTocResult(body_html=body_html, toc_html="")

    rendered: list[str] = []
    toc_entries: list[str] = []
    cursor = 0
    for section_index, match in enumerate(section_matches, start=1):
        end = (
            section_matches[section_index].start()
            if section_index < len(section_matches)
            else len(body_html)
        )
        section_html = body_html[match.start() : end]
        heading = _HEADING_RE.search(section_html)
        if heading is None:
            rendered.append(body_html[cursor:end])
            cursor = end
            continue
        label = _plain_label(heading.group("label"))
        if not label:
            rendered.append(body_html[cursor:end])
            cursor = end
            continue

        element_id = f"report-section-{section_index}-{_slug(label, 'section')}"
        annotated_section = _with_id(match.group(0), element_id) + section_html[
            match.end() - match.start() :
        ]
        annotated_section, finding_entries = _annotate_findings(
            annotated_section, section_index
        )
        nested_findings = (
            '<ol class="report-toc-findings">' + "".join(finding_entries) + "</ol>"
            if finding_entries
            else ""
        )
        toc_entries.append(
            '<li class="report-toc-section">'
            f'<a href="#{element_id}">{html.escape(label)}</a>'
            f"{nested_findings}</li>"
        )
        rendered.append(body_html[cursor : match.start()])
        rendered.append(annotated_section)
        cursor = end
    rendered.append(body_html[cursor:])

    if not toc_entries:
        return ProfessionalTocResult(body_html=body_html, toc_html="")

    is_de = language.lower().startswith("de")
    title = "Inhaltsverzeichnis" if is_de else "Contents"
    toc_html = (
        f'<section {PRINT_PAGE_START.html_attribute()} class="report-toc" '
        'aria-labelledby="report-toc-title">'
        f'<h2 id="report-toc-title">{title}</h2>'
        f'<ol class="report-toc-sections">{"".join(toc_entries)}</ol>'
        "</section>"
    )
    return ProfessionalTocResult(body_html="".join(rendered), toc_html=toc_html)

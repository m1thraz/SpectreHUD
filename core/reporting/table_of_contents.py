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
_FINDING_ID_RE = re.compile(r"\bF-(?P<number>\d{3})\b", re.IGNORECASE)
_TABLE_RE = re.compile(
    r'<table(?P<attrs>[^>]*class="(?P<classes>[^"]*)"[^>]*)>(?P<body>.*?)</table>',
    re.IGNORECASE | re.DOTALL,
)
_CELL_RE = re.compile(
    r'<td(?P<attrs>[^>]*)>(?P<body>.*?)</td>',
    re.IGNORECASE | re.DOTALL,
)
_FINDING_LINK_RE = re.compile(
    r'<a class="finding-reference" href="#finding-(?P<finding_id>f-\d{3})">'
    r"(?P<body>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)

_SECTION_IDS = (
    ("report-header-metadata", "report-metadata"),
    ("report-executive", "executive-summary"),
    ("report-scope", "scope-methodology"),
    ("report-attack-path", "attack-path"),
    ("report-findings", "technical-findings"),
    ("report-remediation", "remediation"),
    ("report-appendix", "appendix"),
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


def _attribute(attrs: str, name: str) -> str:
    match = re.search(rf'\b{re.escape(name)}="([^"]*)"', attrs, re.IGNORECASE)
    return match.group(1) if match else ""


def _section_id(attrs: str, section_index: int) -> str:
    classes = set(_attribute(attrs, "class").split())
    for class_name, element_id in _SECTION_IDS:
        if class_name in classes:
            return element_id
    if "report-phase" in classes:
        phase = _attribute(attrs, "data-phase")
        if phase:
            return f"phase-{_slug(phase, str(section_index))}"
    return f"report-section-{section_index}"


def _unique_id(element_id: str, used_ids: set[str]) -> str:
    if element_id not in used_ids:
        used_ids.add(element_id)
        return element_id
    suffix = 2
    while f"{element_id}-{suffix}" in used_ids:
        suffix += 1
    unique = f"{element_id}-{suffix}"
    used_ids.add(unique)
    return unique


def _annotate_findings(
    section_html: str, used_ids: set[str]
) -> tuple[str, list[str], set[str]]:
    matches = list(_FINDING_OPEN_RE.finditer(section_html))
    if not matches:
        return section_html, [], set()

    rendered: list[str] = []
    entries: list[str] = []
    finding_targets: set[str] = set()
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
        finding_id_match = _FINDING_ID_RE.search(label)
        if finding_id_match is None:
            rendered.append(section_html[cursor:end])
            cursor = end
            continue
        finding_id = f"F-{finding_id_match.group('number')}"
        element_id = _unique_id(f"finding-{finding_id.lower()}", used_ids)
        finding_targets.add(finding_id)
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
    return "".join(rendered), entries, finding_targets


def _link_table_finding_references(body_html: str, finding_targets: set[str]) -> str:
    if not finding_targets:
        return body_html

    def link_table(match: re.Match[str]) -> str:
        classes = set(match.group("classes").split())
        if not classes.intersection({"findings-matrix", "action-plan"}):
            return match.group(0)

        def link_cell(cell: re.Match[str]) -> str:
            cell_body = cell.group("body")
            if "finding-reference" in cell_body:
                return cell.group(0)
            plain = _plain_label(cell_body)
            finding_match = _FINDING_ID_RE.search(plain)
            if finding_match is None:
                return cell.group(0)
            finding_id = f"F-{finding_match.group('number')}"
            if finding_id not in finding_targets:
                return cell.group(0)
            return (
                f'<td{cell.group("attrs")}><a class="finding-reference" '
                f'href="#finding-{finding_id.lower()}">{cell_body}</a></td>'
            )

        linked_body = _CELL_RE.sub(link_cell, match.group("body"))
        return f'<table{match.group("attrs")}>{linked_body}</table>'

    return _TABLE_RE.sub(link_table, body_html)


def _remove_broken_finding_links(body_html: str, finding_targets: set[str]) -> str:
    def keep_or_unwrap(match: re.Match[str]) -> str:
        finding_id = match.group("finding_id").upper()
        return match.group(0) if finding_id in finding_targets else match.group("body")

    return _FINDING_LINK_RE.sub(keep_or_unwrap, body_html)


def build_professional_table_of_contents(
    body_html: str, language: str, *, include_toc: bool = True
) -> ProfessionalTocResult:
    """Add stable navigation targets and optionally build a localized TOC."""
    section_matches = list(_REPORT_SECTION_OPEN_RE.finditer(body_html))
    if not section_matches:
        return ProfessionalTocResult(body_html=body_html, toc_html="")

    rendered: list[str] = []
    toc_entries: list[str] = []
    finding_targets: set[str] = set()
    used_ids: set[str] = {"report-toc-title"}
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

        element_id = _unique_id(_section_id(match.group("attrs"), section_index), used_ids)
        annotated_section = _with_id(match.group(0), element_id) + section_html[
            match.end() - match.start() :
        ]
        annotated_section, finding_entries, section_targets = _annotate_findings(
            annotated_section, used_ids
        )
        finding_targets.update(section_targets)
        nested_findings = (
            '<ol class="report-toc-findings">' + "".join(finding_entries) + "</ol>"
            if finding_entries
            else ""
        )
        if include_toc:
            toc_entries.append(
                '<li class="report-toc-section">'
                f'<a href="#{element_id}">{html.escape(label)}</a>'
                f"{nested_findings}</li>"
            )
        rendered.append(body_html[cursor : match.start()])
        rendered.append(annotated_section)
        cursor = end
    rendered.append(body_html[cursor:])

    annotated_body = _link_table_finding_references("".join(rendered), finding_targets)
    annotated_body = _remove_broken_finding_links(annotated_body, finding_targets)
    if not include_toc or not toc_entries:
        return ProfessionalTocResult(body_html=annotated_body, toc_html="")

    is_de = language.lower().startswith("de")
    title = "Inhaltsverzeichnis" if is_de else "Contents"
    toc_html = (
        f'<section {PRINT_PAGE_START.html_attribute()} class="report-toc" '
        'aria-labelledby="report-toc-title">'
        f'<h2 id="report-toc-title">{title}</h2>'
        f'<ol class="report-toc-sections">{"".join(toc_entries)}</ol>'
        "</section>"
    )
    return ProfessionalTocResult(body_html=annotated_body, toc_html=toc_html)

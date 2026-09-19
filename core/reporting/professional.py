"""Presentation helpers for the Professional Print report profile."""

from dataclasses import dataclass
import html
import re
from typing import Callable, Dict, List, Optional

from core.reporting.section_markers import segment_report_markdown
from core.reporting.findings import FINDING_END_RE, FINDING_START_RE
from core.reporting.report_finding import ReportFindingItem
from core.reporting.report_executive_summary import phase_display_name
from core.reporting.report_remediation import STATUS_LABELS_DE, STATUS_LABELS_EN


_METADATA_ROW_RE = re.compile(r"^\|\s*(?:\*\*)?([^|*]+?)(?:\*\*)?\s*\|\s*([^|]*?)\s*\|$")
_SEVERITY_EMOJI_RE = re.compile("[🔴🟠🟡🟢🔵]\ufe0f?\\s*")
_GENERATED_FOOTER_RE = re.compile(
    r"\n*---\s*\n+_(?:Generated with|Erstellt mit) "
    r"SpectreHUD Pentest & CTF Companion\b[^_\n]*_\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProfessionalCoverData:
    project_name: str
    report_label: str
    severity: Optional[str]
    classification: Optional[str]
    metadata: tuple[tuple[str, str], ...]
    header_label: str = ""


from core.reporting.report_metadata import (
    ALL_METADATA_ALIASES,
    CLASSIFICATION_ALIASES,
    CLIENT_ALIASES,
    DATE_ALIASES,
    TARGET_ALIASES,
    TESTER_ALIASES,
    TIMEFRAME_ALIASES,
    VERSION_ALIASES,
    clean_metadata_value,
)

_plain_markdown_value = clean_metadata_value
_CLIENT_ALIASES = CLIENT_ALIASES
_TARGET_ALIASES = TARGET_ALIASES
_TESTER_ALIASES = TESTER_ALIASES
_TIMEFRAME_ALIASES = TIMEFRAME_ALIASES
_DATE_ALIASES = DATE_ALIASES
_CLASSIFICATION_ALIASES = CLASSIFICATION_ALIASES
_VERSION_ALIASES = VERSION_ALIASES
_ALL_METADATA_ALIASES = ALL_METADATA_ALIASES


def _parse_metadata_rows(lines: List[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        match = _METADATA_ROW_RE.match(line.strip())
        if match:
            raw_key = match.group(1).strip().rstrip(":").strip()
            if not raw_key or re.match(r"^:?-+:?$", raw_key):
                continue
            lower_k = raw_key.lower()
            if lower_k in ("eigenschaft", "property", "key", "attribute"):
                continue
            clean_val = _plain_markdown_value(match.group(2))
            values[lower_k] = clean_val
            normalized_key = re.sub(r"[\s/()_-]+", " ", lower_k).strip()
            values[normalized_key] = clean_val
    return values


def _header_metadata(markdown: str) -> dict[str, str]:
    for segment in segment_report_markdown(markdown):
        if segment.section_type == "header_metadata":
            vals = _parse_metadata_rows(segment.markdown.splitlines())
            if vals:
                return vals
    # Fallback for reports without section markers: inspect leading lines before any H2
    head = markdown.split("\n## ", 1)[0]
    vals = _parse_metadata_rows(head.splitlines())
    if any(k in _ALL_METADATA_ALIASES for k in vals):
        return vals
    return {}


def _header_title(markdown: str) -> str:
    for segment in segment_report_markdown(markdown):
        if segment.section_type == "header_metadata":
            for line in segment.markdown.splitlines():
                line_str = line.strip()
                if line_str.startswith("# "):
                    return line_str[2:].strip()
    head = markdown.split("\n## ", 1)[0]
    for line in head.splitlines():
        line_str = line.strip()
        if line_str.startswith("# "):
            return line_str[2:].strip()
    return ""


def _first_metadata_value(values: dict[str, str], *labels: str | tuple[str, ...]) -> str:
    aliases: list[str] = []
    for item in labels:
        if isinstance(item, (tuple, list)):
            aliases.extend(item)
        else:
            aliases.append(item)
    for alias in aliases:
        norm = alias.strip().lower()
        if norm in values and values[norm]:
            return values[norm]
        clean_alias = re.sub(r"[\s/()_-]+", " ", norm).strip()
        if clean_alias in values and values[clean_alias]:
            return values[clean_alias]
    return ""


def _highest_severity(body_html: str) -> Optional[str]:
    for severity in ("critical", "high", "medium", "low"):
        if f"severity-{severity}" in body_html:
            return severity.upper()
    return None


def _determine_report_labels(
    category: Optional[str],
    title: str,
    is_de: bool,
) -> tuple[str, str]:
    """Returns (cover_kicker, page_header_label) based on category and title."""
    norm_cat = (category or "").strip().lower()
    norm_title = title.lower()

    is_ctf = norm_cat == "ctf" or "ctf" in norm_title or "writeup" in norm_title
    is_audit = norm_cat == "audit" or "audit" in norm_title or "prüfung" in norm_title

    if is_ctf:
        is_walkthrough = "walkthrough" in norm_title
        if is_de:
            kicker = "CTF WALKTHROUGH" if is_walkthrough else "CTF-BERICHT"
            header = "CTF Walkthrough" if is_walkthrough else "CTF-Bericht"
        else:
            kicker = "CTF WALKTHROUGH" if is_walkthrough else "CTF WRITEUP"
            header = "CTF Walkthrough" if is_walkthrough else "CTF Writeup"
        return kicker, header

    if is_audit:
        kicker = "SICHERHEITSAUDIT-BERICHT" if is_de else "SECURITY AUDIT REPORT"
        header = "Sicherheitsaudit-Bericht" if is_de else "Security Audit Report"
        return kicker, header

    kicker = "PENETRATIONSTEST-BERICHT" if is_de else "PENETRATION TEST REPORT"
    header = "Penetrationstest-Bericht" if is_de else "Penetration Test Report"
    return kicker, header


def build_professional_cover_data(
    markdown: str,
    *,
    project_name: str,
    target_ip: Optional[str],
    language: str,
    body_html: str,
    category: Optional[str] = None,
) -> ProfessionalCoverData:
    values = _header_metadata(markdown)
    is_de = language.lower().startswith("de")
    labels = {
        "client": "Auftraggeber" if is_de else "Client",
        "tester": "Tester" if is_de else "Lead Tester",
        "target": "Ziel / Scope" if is_de else "Target / Scope",
        "timeframe": "Testzeitraum" if is_de else "Assessment Period",
        "date": "Berichtsdatum" if is_de else "Report Date",
        "classification": "Klassifizierung" if is_de else "Classification",
        "version": "Report-Version" if is_de else "Report Version",
    }
    classification = _first_metadata_value(values, _CLASSIFICATION_ALIASES)
    raw_fields = (
        (
            labels["client"],
            _first_metadata_value(values, _CLIENT_ALIASES),
        ),
        (
            labels["tester"],
            _first_metadata_value(values, _TESTER_ALIASES),
        ),
        (
            labels["target"],
            target_ip or _first_metadata_value(values, _TARGET_ALIASES),
        ),
        (
            labels["timeframe"],
            _first_metadata_value(values, _TIMEFRAME_ALIASES),
        ),
        (
            labels["date"],
            _first_metadata_value(values, _DATE_ALIASES),
        ),
        (
            labels["classification"],
            classification,
        ),
        (
            labels["version"],
            _first_metadata_value(values, _VERSION_ALIASES),
        ),
    )
    title = _header_title(markdown)
    kicker, header_label = _determine_report_labels(category, title, is_de)
    cover_project_name = (
        project_name
        if (project_name and project_name != "Target")
        else (title or project_name or "Target")
    )
    return ProfessionalCoverData(
        project_name=cover_project_name,
        report_label=kicker,
        severity=_highest_severity(body_html),
        classification=classification or None,
        metadata=tuple((label, value) for label, value in raw_fields if value),
        header_label=header_label,
    )


def extract_report_title(markdown: str) -> str:
    """Extract report title from header_metadata section or leading H1."""
    return _header_title(markdown)


def strip_generator_footer(markdown: str) -> str:
    """Remove only TemplateRenderer's generated signature from the markdown."""
    return _GENERATED_FOOTER_RE.sub("", markdown).rstrip()


def strip_professional_generator_footer(markdown: str) -> str:
    """Remove only TemplateRenderer's generated signature from the print projection."""
    return strip_generator_footer(markdown)


def render_professional_cover(data: ProfessionalCoverData) -> str:
    severity = (
        '<div class="report-cover-severity-block">'
        '<span class="report-cover-severity-label">Highest Finding Severity</span>'
        f'<span class="report-cover-severity severity-{data.severity.lower()}">'
        f"{html.escape(data.severity)}</span>"
        "</div>"
        if data.severity
        else ""
    )
    metadata = "".join(
        '<div class="report-cover-meta-item">'
        f'<span class="report-cover-meta-label">{html.escape(label)}</span>'
        f'<strong class="report-cover-meta-value">{html.escape(value)}</strong>'
        "</div>"
        for label, value in data.metadata
    )
    metadata_block = f'<div class="report-cover-meta">{metadata}</div>' if metadata else ""
    return (
        '<section class="report-cover" aria-label="Report cover">'
        '<div class="report-cover-topline">'
        f'<span class="report-cover-kicker">{html.escape(data.report_label)}</span>'
        f"{severity}</div>"
        '<div class="report-cover-title-block">'
        f'<h1 class="report-cover-title">{html.escape(data.project_name)}</h1>'
        '<div class="report-cover-rule"></div>'
        "</div>"
        f"{metadata_block}"
        '<div class="report-cover-brand">SpectreHUD</div>'
        "</section>"
    )


def normalize_professional_severity(body_html: str) -> str:
    def clean_badge(match: re.Match[str]) -> str:
        return match.group(1) + _SEVERITY_EMOJI_RE.sub("", match.group(2)) + match.group(3)

    normalized = re.sub(
        r'(<span class="severity-pill severity-[a-z]+">)(.*?)(</span>)',
        clean_badge,
        body_html,
        flags=re.DOTALL,
    )

    def wrap_table_severity(match: re.Match[str]) -> str:
        def wrap_cell(cell: re.Match[str]) -> str:
            severity = cell.group(2).strip().lower()
            badge = (
                f'<span class="severity-pill severity-{severity}">'
                f"{severity.upper()}</span>"
            )
            return f"{cell.group(1)}{badge}{cell.group(3)}"

        return re.sub(
            r"(<td[^>]*>)\s*(CRITICAL|HIGH|MEDIUM|LOW|INFO)\s*(</td>)",
            wrap_cell,
            match.group(0),
            flags=re.IGNORECASE,
        )

    normalized = re.sub(
        r'<table class="(?=[^"]*(?:findings-matrix|action-plan))[^"]*"[^>]*>'
        r".*?</table>",
        wrap_table_severity,
        normalized,
        flags=re.DOTALL,
    )

    def clean_total(match: re.Match[str]) -> str:
        return match.group(1) + _SEVERITY_EMOJI_RE.sub("", match.group(2)) + match.group(3)

    return re.sub(
        r"(<p><strong>(?:Total|Gesamt):</strong>)(.*?)(</p>)",
        clean_total,
        normalized,
        flags=re.DOTALL,
    )


def normalize_professional_timestamps(body_html: str) -> str:
    """Drop seconds only from rendered finding metadata in the print projection."""
    return re.sub(
        r'(<span class="finding-meta-value">(?:<code>)?'
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}):\d{2}((?:</code>)?</span>)",
        r"\1\2",
        body_html,
    )


def normalize_professional_remediation_table(body_html: str) -> str:
    """Clean empty cells in remediation action-plan tables."""
    if "action-plan" not in body_html:
        return body_html

    body_html = re.sub(
        r'(<td[^>]*>)\s*([–—-])\s*(</td>)',
        r'\1<span class="report-empty-cell">–</span>\3',
        body_html,
    )

    return body_html


_GENERATED_MATRIX_ROW_RE = re.compile(
    r"^\|\s*(\d+|F-\d{3})\s*\|\s*(.*?)\s*\|\s*(CRITICAL|HIGH|MEDIUM|LOW|INFO)"
    r"\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|$",
    re.IGNORECASE,
)


def _structured_findings(markdown: str) -> list[ReportFindingItem]:
    findings: list[ReportFindingItem] = []
    cursor = 0
    while start := FINDING_START_RE.search(markdown, cursor):
        next_start = FINDING_START_RE.search(markdown, start.end())
        end = next(
            (
                candidate
                for candidate in FINDING_END_RE.finditer(markdown, start.end())
                if candidate.group(1) == start.group(1)
            ),
            None,
        )
        if end is None or (next_start and next_start.start() < end.start()):
            cursor = start.end()
            continue
        findings.append(
            ReportFindingItem.from_markdown(markdown[start.start() : end.end()], start.group(1))
        )
        cursor = end.end()
    return findings


def synchronize_professional_findings_matrix(
    summary_markdown: str, report_markdown: str, language: str
) -> str:
    """Correct only a recognizable generated matrix in the print projection."""
    lines = summary_markdown.splitlines(keepends=True)
    matrix_start = next(
        (
            index
            for index, line in enumerate(lines)
            if line.strip().lower() in {"### findings matrix", "### findings-übersicht"}
        ),
        None,
    )
    if matrix_start is None:
        return summary_markdown

    header_index = next(
        (
            index
            for index in range(matrix_start + 1, len(lines))
            if lines[index].strip()
            in {
                "| # | Finding | Severity | Phase | Status |",
                "| ID | Finding | Severity | Phase | Status |",
                "| ID | Schwachstelle | Severity | Phase | Status |",
                "| # | Schwachstelle | Severity | Phase | Status |",
            }
        ),
        None,
    )
    if header_index is None or header_index + 1 >= len(lines):
        return summary_markdown
    if not re.fullmatch(r"\|[\s\-:|]+\|", lines[header_index + 1].strip()):
        return summary_markdown

    rows: list[tuple[int, re.Match[str]]] = []
    for index in range(header_index + 2, len(lines)):
        line = lines[index].strip()
        if not line.startswith("|"):
            break
        match = _GENERATED_MATRIX_ROW_RE.fullmatch(line)
        if match is None:
            return summary_markdown
        rows.append((index, match))
    if not rows:
        return summary_markdown

    def _matches_id(group1: str, position: int) -> bool:
        clean_g1 = group1.strip()
        if clean_g1.isdigit():
            return int(clean_g1) == position
        if clean_g1.upper().startswith("F-"):
            return clean_g1.upper() == f"F-{position:03d}"
        return False

    findings = _structured_findings(report_markdown)
    candidates = (findings, [finding for finding in findings if finding.severity != "info"])
    matching = next(
        (
            candidate
            for candidate in candidates
            if len(candidate) == len(rows)
            and all(
                _matches_id(match.group(1), position)
                and match.group(2).strip()
                == (finding.title or "Unnamed").replace("|", "\\|").replace("\n", " ")
                and match.group(3).upper() == finding.severity.upper()
                for position, ((_, match), finding) in enumerate(zip(rows, candidate), start=1)
            )
        ),
        None,
    )
    if matching is None:
        return summary_markdown

    labels = STATUS_LABELS_DE if language.lower().startswith("de") else STATUS_LABELS_EN
    for (index, match), finding in zip(rows, matching):
        status = labels.get((finding.status or "open").lower(), labels["open"])
        phase = phase_display_name(match.group(4), language).replace("|", "\\|")
        line_ending = "\r\n" if lines[index].endswith("\r\n") else "\n"
        if not lines[index].endswith(("\r\n", "\n")):
            line_ending = ""
        lines[index] = (
            f"| {match.group(1).strip()} | {match.group(2).strip()} | "
            f"{match.group(3).upper()} | {phase} | {status} |{line_ending}"
        )
    return "".join(lines)


def _content_lines(markdown: str) -> list[str]:
    return [
        line.strip()
        for line in markdown.splitlines()
        if line.strip()
        and line.strip() != "---"
        and not line.strip().startswith("<!-- spectre:pagebreak")
        and not line.strip().startswith("<!-- spectre:spacer:")
    ]


def _has_header_metadata_content(lines: List[str]) -> bool:
    return any(not (line.startswith("# ") or line.startswith("|")) for line in lines)


def _has_phase_section_content(markdown: str) -> bool:
    from core.reporting.findings import phase_section_has_meaningful_content

    return phase_section_has_meaningful_content(markdown)


def _has_attack_path_content(lines: List[str]) -> bool:
    empty_notices = {
        "*Kein dokumentierter Angriffspfad vorhanden.*",
        "*No documented attack path is available.*",
    }
    return any(not line.startswith("## ") and line not in empty_notices for line in lines)


def _has_executive_summary_content(lines: List[str]) -> bool:
    if any(re.match(r"^\|\s*\d+\s*\|", line) for line in lines):
        return True
    for line in lines:
        if line.startswith(("## ", "### ", "|")):
            continue
        if re.match(r"^- \*\*.+:\*\*$", line):
            continue
        if re.match(r"^\*\*(?:Total|Gesamt):\*\*", line):
            counts = [
                int(value)
                for value in re.findall(
                    r"(?:</span>\s*(\d+)|(\d+)\s+(?:Critical|High|Medium|Low))",
                    line,
                )
                for value in value
                if value
            ]
            if counts and not any(counts):
                continue
        return True
    return False


def _has_scope_limitations_content(lines: List[str]) -> bool:
    return any(
        not line.startswith("## ") and not re.match(r"^- \*\*.+:\*\*$", line) for line in lines
    )


def _has_remediation_table_content(lines: List[str]) -> bool:
    for line in lines:
        if line.startswith("## ") or re.match(r"^\|[\s\-:|]+\|$", line):
            continue
        if line.startswith(("| Priority |", "| Priorität |", "| |")):
            continue
        return True
    return False


def _has_appendix_content(lines: List[str]) -> bool:
    empty_notices = {
        "*Keine Clipboard-Historie aufgezeichnet.*",
        "*No clipboard history recorded.*",
        "*Keine Screenshots in diesem Projekt vorhanden.*",
        "*No screenshots captured in this project.*",
        "*Keine Befehlsprotokolle hinterlegt.*",
        "*No command logs recorded.*",
        "*Keine Screenshots oder Nachweise hinterlegt.*",
        "*Keine Screenshots oder Nachweise erfasst.*",
        "*No screenshots or evidence recorded.*",
        "*Keine Anhänge oder Nachweise erfasst.*",
        "*No appendices or evidence recorded.*",
        "*Keine Befehle für den Report ausgewählt.*",
        "*No commands selected for report.*",
    }
    return any(
        not line.startswith(("## ", "### ", "#### ", "---")) and line.strip() not in empty_notices
        for line in lines
        if line.strip()
    )


_SECTION_CONTENT_PREDICATES: Dict[str, Callable[[List[str], str], bool]] = {
    "header_metadata": lambda lines, _: _has_header_metadata_content(lines),
    "phase_section": lambda _, md: _has_phase_section_content(md),
    "finding_section": lambda _, md: _has_phase_section_content(md),
    "attack_path": lambda lines, _: _has_attack_path_content(lines),
    "executive_summary": lambda lines, _: _has_executive_summary_content(lines),
    "scope_limitations": lambda lines, _: _has_scope_limitations_content(lines),
    "remediation_table": lambda lines, _: _has_remediation_table_content(lines),
    "appendix": lambda lines, _: _has_appendix_content(lines),
}


def professional_section_has_meaningful_content(section_type: str, markdown: str) -> bool:
    """Keep a section unless only its generated editing scaffold remains."""
    lines = _content_lines(markdown)
    predicate = _SECTION_CONTENT_PREDICATES.get(section_type)
    if predicate is not None:
        return predicate(lines, markdown)
    return bool(lines)


def prune_professional_section_html(section_type: str, body_html: str) -> str:
    if section_type == "header_metadata":
        body_html = re.sub(r"<h1>[^<]*</h1>\s*", "", body_html)
        body_html = re.sub(
            r"(?:<div class=\"table-container\">\s*)?<table>.*?</table>(?:\s*</div>)?\s*",
            "",
            body_html,
            flags=re.DOTALL,
        )
        body_html = re.sub(r"<div class=\"table-container\">\s*</div>\s*", "", body_html)
        if not re.search(r"\S", re.sub(r"<[^>]+>", "", body_html)):
            return ""
        return body_html.strip()
    if section_type in {"executive_summary", "scope_limitations"}:
        body_html = re.sub(
            r"<li><strong>[^<]+:</strong>\s*(?:[-–—\s]*|none|n/a)?</li>",
            "",
            body_html,
            flags=re.IGNORECASE,
        )
        body_html = re.sub(
            r"<h3>(?:Key Highlights|Kernaussagen)</h3>\s*(?:<ul>\s*</ul>)?",
            "",
            body_html,
        )
    if section_type == "appendix":
        body_html = re.sub(
            r"(?:<hr>\s*)?<h[23]>[^<]*Screenshots[^<]*</h[23]>\s*"
            r"<p><em>(?:No screenshots captured in this project\.|Keine Screenshots in diesem Projekt vorhanden\.)</em></p>",
            "",
            body_html,
            flags=re.IGNORECASE,
        )
        body_html = re.sub(
            r"<p><em>(?:No screenshots captured in this project\.|Keine Screenshots in diesem Projekt vorhanden\.)</em></p>",
            "",
            body_html,
            flags=re.IGNORECASE,
        )
        body_html = re.sub(
            r"<p><em>(?:No clipboard history recorded\.|Keine Clipboard-Historie aufgezeichnet\.)</em></p>\s*(?:<p><em>(?:No command logs recorded\.|Keine Befehlsprotokolle hinterlegt\.)</em></p>)",
            "<p><em>No command logs recorded.</em></p>",
            body_html,
            flags=re.IGNORECASE,
        )
        body_html = re.sub(
            r"^<h2>[^<]*(?:Appendix|Anhang)[^<]*</h2>\s*$",
            "",
            body_html.strip(),
            flags=re.IGNORECASE,
        )
    return body_html


def prune_unstructured_header_metadata_html(body_html: str) -> str:
    """Removes a leading H1 title and metadata table from unstructured body HTML if present."""
    first_h2 = body_html.find("<h2")
    prefix = body_html[:first_h2] if first_h2 != -1 else body_html
    rest = body_html[first_h2:] if first_h2 != -1 else ""

    table_match = re.search(
        r"(?:<div class=\"table-container\">\s*)?<table>.*?</table>(?:\s*</div>)?",
        prefix,
        flags=re.DOTALL,
    )
    if table_match:
        table_content = table_match.group(0).lower()
        if any(alias in table_content for alias in _ALL_METADATA_ALIASES):
            prefix = prefix[: table_match.start()] + prefix[table_match.end() :]
            prefix = re.sub(r"<h1>[^<]*</h1>\s*", "", prefix, count=1)

    result = prefix.strip()
    if rest:
        result = f"{result}\n{rest}" if result else rest
    return result


def renumber_professional_heading(markdown: str, number: int) -> tuple[str, bool]:
    """Ensure a section's leading H2 is consistently numbered for the filtered print view."""
    match = re.search(r"^(##\s+)(?:\d+\.\s*)?(\S.*)$", markdown, flags=re.MULTILINE)
    if match:
        prefix, title = match.group(1), match.group(2).strip()
        renumbered = (
            markdown[: match.start()] + f"{prefix}{number}. {title}" + markdown[match.end() :]
        )
        return renumbered, True
    return markdown, False

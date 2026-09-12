"""Presentation helpers for the Professional Print report profile."""

from dataclasses import dataclass
import html
import re
from typing import Callable, Dict, List, Optional

from core.reporting.section_markers import segment_report_markdown


_METADATA_ROW_RE = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.*?)\s*\|$")
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


def _plain_markdown_value(value: str) -> str:
    cleaned = value.strip().strip("`").strip()
    cleaned = re.sub(r"[*_]", "", cleaned)
    return html.unescape(cleaned).strip()


_CLIENT_ALIASES = (
    "auftraggeber / client",
    "client / organization",
    "client",
    "auftraggeber",
    "kunde",
    "customer",
    "organisation",
    "organization",
    "company",
    "unternehmen",
)
_TARGET_ALIASES = (
    "ziel(e) / scope",
    "scope / target",
    "target",
    "scope",
    "ziel",
    "ziele",
    "ziel(e)",
    "target_ip",
    "ip",
    "domain",
    "netzwerk",
    "network",
)
_DATE_ALIASES = (
    "berichtsdatum",
    "report date",
    "datum",
    "date",
    "stand",
    "zeitraum",
    "assessment date",
    "erstellungsdatum",
)
_CLASSIFICATION_ALIASES = (
    "klassifizierung",
    "classification",
    "vertraulichkeit",
    "confidentiality",
    "tlp",
    "traffic light protocol",
)
_VERSION_ALIASES = (
    "report-version",
    "report version",
    "version",
    "revision",
)


def _header_metadata(markdown: str) -> dict[str, str]:
    for segment in segment_report_markdown(markdown):
        if segment.section_type != "header_metadata":
            continue
        values: dict[str, str] = {}
        for line in segment.markdown.splitlines():
            match = _METADATA_ROW_RE.match(line.strip())
            if match:
                raw_key = match.group(1).strip().lower()
                clean_val = _plain_markdown_value(match.group(2))
                values[raw_key] = clean_val
                normalized_key = re.sub(r"[\s/()_-]+", " ", raw_key).strip()
                values[normalized_key] = clean_val
        return values
    return {}


def _header_title(markdown: str) -> str:
    for segment in segment_report_markdown(markdown):
        if segment.section_type != "header_metadata":
            continue
        for line in segment.markdown.splitlines():
            line_str = line.strip()
            if line_str.startswith("# "):
                return line_str[2:].strip()
    return ""


def _first_metadata_value(
    values: dict[str, str], *labels: str | tuple[str, ...]
) -> str:
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
        "target": "Ziel / Scope" if is_de else "Target / Scope",
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
            labels["target"],
            target_ip
            or _first_metadata_value(values, _TARGET_ALIASES),
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
    return ProfessionalCoverData(
        project_name=project_name or "Target",
        report_label=kicker,
        severity=_highest_severity(body_html),
        classification=classification or None,
        metadata=tuple((label, value) for label, value in raw_fields if value),
        header_label=header_label,
    )


def strip_professional_generator_footer(markdown: str) -> str:
    """Remove only TemplateRenderer's generated signature from the print projection."""
    return _GENERATED_FOOTER_RE.sub("", markdown).rstrip()


def render_professional_cover(data: ProfessionalCoverData) -> str:
    severity = (
        f'<span class="report-cover-severity severity-{data.severity.lower()}">'
        f"{html.escape(data.severity)}</span>"
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
        not line.startswith("## ") and not re.match(r"^- \*\*.+:\*\*$", line)
        for line in lines
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
    }
    return any(not line.startswith("## ") and line not in empty_notices for line in lines)


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
    if section_type in {"executive_summary", "scope_limitations"}:
        body_html = re.sub(r"<li><strong>[^<]+:</strong></li>", "", body_html)
        body_html = re.sub(
            r"<h3>(?:Key Highlights|Kernaussagen)</h3>\s*<ul>\s*</ul>",
            "",
            body_html,
        )
    if section_type == "appendix":
        body_html = re.sub(
            r"<h2>[^<]*(?:Terminal Command History|Befehlsverlauf)[^<]*</h2>\s*"
            r"<p><em>(?:No clipboard history recorded\.|Keine Clipboard-Historie aufgezeichnet\.)</em></p>"
            r"\s*(?:<hr>\s*)?",
            "",
            body_html,
        )
        body_html = re.sub(
            r"(?:<hr>\s*)?<h2>[^<]*Screenshots</h2>\s*"
            r"<p><em>(?:No screenshots captured in this project\.|Keine Screenshots in diesem Projekt vorhanden\.)</em></p>",
            "",
            body_html,
        )
    return body_html


def renumber_professional_heading(markdown: str, number: int) -> tuple[str, bool]:
    """Ensure a section's leading H2 is consistently numbered for the filtered print view."""
    match = re.search(r"^(##\s+)(?:\d+\.\s*)?(\S.*)$", markdown, flags=re.MULTILINE)
    if match:
        prefix, title = match.group(1), match.group(2).strip()
        renumbered = (
            markdown[: match.start()]
            + f"{prefix}{number}. {title}"
            + markdown[match.end() :]
        )
        return renumbered, True
    return markdown, False


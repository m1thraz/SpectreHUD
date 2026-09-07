"""Presentation helpers for the Professional Print report profile."""

from dataclasses import dataclass
import html
import re
from typing import Optional

from core.reporting.section_markers import segment_report_markdown


_METADATA_ROW_RE = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.*?)\s*\|$")
_SEVERITY_EMOJI_RE = re.compile("[🔴🟠🟡🟢🔵]\ufe0f?\\s*")


@dataclass(frozen=True)
class ProfessionalCoverData:
    project_name: str
    report_label: str
    severity: Optional[str]
    metadata: tuple[tuple[str, str], ...]


def _plain_markdown_value(value: str) -> str:
    cleaned = value.strip().strip("`").strip()
    cleaned = re.sub(r"[*_]", "", cleaned)
    return html.unescape(cleaned).strip()


def _header_metadata(markdown: str) -> dict[str, str]:
    for segment in segment_report_markdown(markdown):
        if segment.section_type != "header_metadata":
            continue
        values: dict[str, str] = {}
        for line in segment.markdown.splitlines():
            match = _METADATA_ROW_RE.match(line.strip())
            if match:
                values[match.group(1).strip().lower()] = _plain_markdown_value(match.group(2))
        return values
    return {}


def _first_metadata_value(values: dict[str, str], *labels: str) -> str:
    for label in labels:
        value = values.get(label, "").strip()
        if value:
            return value
    return ""


def _highest_severity(body_html: str) -> Optional[str]:
    for severity in ("critical", "high", "medium", "low"):
        if f"severity-{severity}" in body_html:
            return severity.upper()
    return None


def build_professional_cover_data(
    markdown: str,
    *,
    project_name: str,
    target_ip: Optional[str],
    language: str,
    body_html: str,
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
    raw_fields = (
        (
            labels["client"],
            _first_metadata_value(values, "auftraggeber / client", "client / organization"),
        ),
        (
            labels["target"],
            target_ip
            or _first_metadata_value(values, "ziel(e) / scope", "scope / target"),
        ),
        (
            labels["date"],
            _first_metadata_value(values, "berichtsdatum", "report date"),
        ),
        (
            labels["classification"],
            _first_metadata_value(values, "klassifizierung", "classification"),
        ),
        (
            labels["version"],
            _first_metadata_value(values, "report-version", "report version"),
        ),
    )
    return ProfessionalCoverData(
        project_name=project_name or "Target",
        report_label="PENETRATIONSTEST-BERICHT" if is_de else "PENETRATION TEST REPORT",
        severity=_highest_severity(body_html),
        metadata=tuple((label, value) for label, value in raw_fields if value),
    )


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
        '<div class="report-cover-brand">Generated with SpectreHUD</div>'
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


def _content_lines(markdown: str) -> list[str]:
    return [
        line.strip()
        for line in markdown.splitlines()
        if line.strip()
        and line.strip() != "---"
        and not line.strip().startswith("<!-- spectre:pagebreak")
        and not line.strip().startswith("<!-- spectre:spacer:")
    ]


def professional_section_has_meaningful_content(section_type: str, markdown: str) -> bool:
    """Keep a section unless only its generated editing scaffold remains."""
    lines = _content_lines(markdown)
    if section_type == "header_metadata":
        return any(not (line.startswith("# ") or line.startswith("|")) for line in lines)
    if section_type in {"phase_section", "finding_section"}:
        from core.reporting.findings import phase_section_has_meaningful_content

        return phase_section_has_meaningful_content(markdown)
    if section_type == "attack_path":
        empty_notices = {
            "*Kein dokumentierter Angriffspfad vorhanden.*",
            "*No documented attack path is available.*",
        }
        return any(not line.startswith("## ") and line not in empty_notices for line in lines)
    if section_type == "executive_summary":
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
                        r"(\d+)\s+(?:Critical|High|Medium|Low)", line
                    )
                ]
                if counts and not any(counts):
                    continue
            return True
        return False
    if section_type == "scope_limitations":
        return any(
            not line.startswith("## ") and not re.match(r"^- \*\*.+:\*\*$", line)
            for line in lines
        )
    if section_type == "remediation_table":
        for line in lines:
            if line.startswith("## ") or re.match(r"^\|[\s\-:|]+\|$", line):
                continue
            if line.startswith(("| Priority |", "| Priorität |", "| |")):
                continue
            return True
        return False
    if section_type == "appendix":
        empty_notices = {
            "*Keine Clipboard-Historie aufgezeichnet.*",
            "*No clipboard history recorded.*",
            "*Keine Screenshots in diesem Projekt vorhanden.*",
            "*No screenshots captured in this project.*",
        }
        return any(not line.startswith("## ") and line not in empty_notices for line in lines)
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

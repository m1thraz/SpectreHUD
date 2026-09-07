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

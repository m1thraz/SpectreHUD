"""
Report Executive Summary model.

Provides the ReportExecutiveSummary dataclass with Markdown parsing
and rendering including the findings matrix and key highlights.
"""

import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List

from core.phases import get_phase, try_normalize_phase_key
from core.reporting.charts import render_severity_counts
from core.reporting.report_finding import ReportFindingItem
from core.reporting.report_remediation import STATUS_LABELS_DE, STATUS_LABELS_EN

PHASE_NAMES_DE: Dict[str, str] = {
    "recon": "Aufklärung & Enumeration",
    "access": "Initialer Zugriff & Exploitation",
    "privesc": "Rechteausweitung (PrivEsc)",
    "postex": "Post-Exploitation & Lateral Movement",
    "scripts": "Eigene Skripte & PoCs",
    "misc": "Sonstiges",
}


def phase_display_name(phase: str, language: str = "en") -> str:
    """Return the canonical, localized long name for a persisted phase value."""
    raw_phase = str(phase).strip()
    phase_key = try_normalize_phase_key(raw_phase)
    if phase_key is None:
        return raw_phase
    phase_obj = get_phase(phase_key)
    if language.lower().startswith("de"):
        return PHASE_NAMES_DE.get(phase_obj.key, phase_obj.long)
    return phase_obj.long


def is_meaningful_highlight_value(val: str | None) -> bool:
    """Returns False for empty, whitespace, dashes or placeholder values."""
    if not val:
        return False
    stripped = val.strip()
    if not stripped:
        return False
    if stripped.lower() in ("-", "–", "—", "none", "n/a", "null", "undefined", "*keine*", "keine"):
        return False
    if re.match(r"^[-–—\s]+$", stripped):
        return False
    return True


@dataclass
class ReportExecutiveSummary:
    """Structured representation of the Executive Summary narrative section."""

    title: str = "Executive Summary"
    intro_text: str = ""
    initial_access: str = ""
    privilege_escalation: str = ""
    business_impact: str = ""
    remediation_summary: str = ""

    @classmethod
    def from_markdown(cls, markdown: str, language: str = "de") -> "ReportExecutiveSummary":
        if not markdown:
            return cls(title="Executive Summary")

        title = "Executive Summary"
        h2 = re.search(r"^##\s+(.*?)$", markdown, re.MULTILINE)
        if h2:
            title = h2.group(1).strip()

        # Intro text: between H2 and first H3 (Findings Matrix / Highlights)
        intro_text = ""
        first_h3 = re.search(r"^###\s+", markdown, re.MULTILINE)
        if first_h3:
            h2_end = h2.end() if h2 else 0
            intro_raw = markdown[h2_end : first_h3.start()].strip()
            intro_text = intro_raw
        elif h2:
            intro_text = markdown[h2.end() :].strip()

        # Helper to extract bullet value
        def _extract_bullet(patterns: List[str]) -> str:
            for pat in patterns:
                m = re.search(
                    rf"^[ \t]*[-*]\s+\*\*{pat}:\*\*\s*(.*?)$",
                    markdown,
                    re.MULTILINE | re.IGNORECASE,
                )
                if m:
                    extracted = m.group(1).strip()
                    return extracted if is_meaningful_highlight_value(extracted) else ""
            return ""

        initial_access = _extract_bullet(
            [
                "Initial Access Vector",
                "Initial Access / Schwachstelle",
                "Initial Access",
                "Initialer Zugriff",
            ]
        )
        privilege_escalation = _extract_bullet(
            [
                "Privilege Escalation",
                "Rechteausweitung",
                "PrivEsc",
            ]
        )
        business_impact = _extract_bullet(
            [
                "Business Impact & Risk",
                "Business Impact / Risiko",
                "Business Impact",
                "Geschäftsauswirkung",
                "Risiko",
            ]
        )
        remediation_summary = _extract_bullet(
            [
                "Recommended Remediation",
                "Empfohlene Remediation",
                "Empfohlene Maßnahmen",
                "Remediation",
            ]
        )

        return cls(
            title=title,
            intro_text=intro_text,
            initial_access=initial_access,
            privilege_escalation=privilege_escalation,
            business_impact=business_impact,
            remediation_summary=remediation_summary,
        )

    def to_markdown(self, findings: List[ReportFindingItem], language: str = "de") -> str:
        lines: List[str] = [f"## {self.title}", ""]

        if self.intro_text.strip():
            lines.append(self.intro_text.strip())
            lines.append("")

        matrix_title = "### Findings-Übersicht" if language == "de" else "### Findings Matrix"
        lines.append(matrix_title)
        lines.append("")
        id_header = "ID"
        finding_col = "Schwachstelle" if language == "de" else "Finding"
        lines.append(f"| {id_header} | {finding_col} | Severity | Phase | Status |")
        lines.append("|---|---------|----------|-------|--------|")

        sev_counts: Counter[str] = Counter()
        for idx, f in enumerate(findings, start=1):
            sev = f.severity.lower()
            sev_counts[sev] += 1
            t = (f.title or "Unnamed").replace("|", "\\|").replace("\n", " ")
            ph_name = phase_display_name(f.phase, language)
            ph = ph_name.replace("|", "\\|").replace("\n", " ")
            status_key = (f.status or "open").strip().lower()
            status_labels = STATUS_LABELS_DE if language == "de" else STATUS_LABELS_EN
            st = status_labels.get(
                status_key, f.status.capitalize() if f.status else status_labels["open"]
            )
            finding_id = f"F-{idx:03d}"
            lines.append(f"| {finding_id} | {t} | {f.severity.upper()} | {ph} | {st} |")

        if not findings:
            lines.append("| | | | | |")

        lines.append("")
        total_str = render_severity_counts(
            sev_counts["critical"],
            sev_counts["high"],
            sev_counts["medium"],
            sev_counts["low"],
        )
        lines.append(f"**{'Gesamt' if language == 'de' else 'Total'}:** {total_str}")
        lines.append("")

        # Highlights section: render only items with meaningful content
        highlight_items: List[str] = []
        if language == "de":
            mapping = [
                ("Initial Access / Schwachstelle", self.initial_access),
                ("Privilege Escalation", self.privilege_escalation),
                ("Business Impact / Risiko", self.business_impact),
                ("Empfohlene Remediation", self.remediation_summary),
            ]
        else:
            mapping = [
                ("Initial Access Vector", self.initial_access),
                ("Privilege Escalation", self.privilege_escalation),
                ("Business Impact & Risk", self.business_impact),
                ("Recommended Remediation", self.remediation_summary),
            ]

        for label, val in mapping:
            if is_meaningful_highlight_value(val):
                highlight_items.append(f"- **{label}:** {val.strip()}")

        if highlight_items:
            hl_title = "### Kernaussagen" if language == "de" else "### Key Highlights"
            lines.append(hl_title)
            lines.append("")
            lines.extend(highlight_items)

        return "\n".join(lines).strip()

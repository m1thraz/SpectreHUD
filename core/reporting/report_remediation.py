"""
Report Remediation Plan model.

Provides the ReportRemediationPlan dataclass with Markdown parsing and
rendering of a prioritized remediation action table derived from findings.
"""

import re
from dataclasses import dataclass
from typing import Dict, List

from core.reporting.report_finding import ReportFindingItem

SEVERITY_ORDER: Dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}

STATUS_LABELS_DE: Dict[str, str] = {
    "open": "Offen",
    "in_progress": "In Arbeit",
    "resolved": "Behoben",
    "closed": "Behoben",
    "accepted_risk": "Akzeptiert",
}

STATUS_LABELS_EN: Dict[str, str] = {
    "open": "Open",
    "in_progress": "In Progress",
    "resolved": "Resolved",
    "closed": "Resolved",
    "accepted_risk": "Accepted Risk",
}


@dataclass
class ReportRemediationPlan:
    """Structured representation of the Remediation & Action Plan section."""

    title: str = "Remediation & Action Plan"
    strategic_guidance: str = ""

    @classmethod
    def from_markdown(cls, markdown: str, language: str = "de") -> "ReportRemediationPlan":
        default_title = "Remediation & Maßnahmenplan" if language == "de" else "Remediation & Action Plan"
        if not markdown:
            return cls(title=default_title)

        title = default_title
        h2 = re.search(r"^##\s+(.*?)$", markdown, re.MULTILINE)
        if h2:
            title = h2.group(1).strip()

        strategic_guidance = ""
        table_start = re.search(r"^[ \t]*\|", markdown, re.MULTILINE)
        if table_start:
            start_pos = h2.end() if h2 else 0
            strategic_guidance = markdown[start_pos:table_start.start()].strip()
        elif h2:
            strategic_guidance = markdown[h2.end():].strip()

        return cls(title=title, strategic_guidance=strategic_guidance)

    def to_markdown(self, findings: List[ReportFindingItem], language: str = "de") -> str:
        default_title = "Remediation & Maßnahmenplan" if language == "de" else "Remediation & Action Plan"
        sec_title = self.title or default_title
        lines: List[str] = [f"## {sec_title}", ""]

        if self.strategic_guidance.strip():
            lines.append(self.strategic_guidance.strip())
            lines.append("")

        if language == "de":
            lines.extend([
                "| Priorität | Schwachstelle | Empfohlene Maßnahme | Status |",
                "|-----------|---------------|----------------------|--------|",
            ])
        else:
            lines.extend([
                "| Priority | Vulnerability | Recommended Action | Status |",
                "|----------|---------------|--------------------|--------|",
            ])

        sorted_findings = sorted(
            findings,
            key=lambda f: SEVERITY_ORDER.get((f.severity or "medium").strip().lower(), 99),
        )

        for f in sorted_findings:
            sev = (f.severity or "medium").strip().upper()
            t = (f.title or "Unnamed").replace("|", "\\|").replace("\n", " ")
            rec = (f.recommendation or "–").replace("|", "\\|").replace("\n", " ")
            st_key = (f.status or "open").strip().lower()
            if language == "de":
                st = STATUS_LABELS_DE.get(st_key, f.status.capitalize() if f.status else "Offen")
            else:
                st = STATUS_LABELS_EN.get(st_key, f.status.capitalize() if f.status else "Open")
            lines.append(f"| {sev} | {t} | {rec} | {st} |")

        if not sorted_findings:
            lines.append("| | | | |")

        lines.append("")
        return "\n".join(lines)

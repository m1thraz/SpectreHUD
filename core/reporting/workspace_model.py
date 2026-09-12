"""
SpectreHUD Report Workspace Data Model.

Provides pure-Python, headless, structured representations of pentest/CTF
reports (metadata, findings, evidence, narrative sections, and appendices)
with lossless bidirectional Markdown synchronization.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
import html
import re
from typing import Any, Dict, List, Optional

from core.phases import get_phase, normalize_phase_key
from core.reporting.charts import render_severity_badge, render_severity_counts
from core.reporting.findings import (
    FINDING_END_RE,
    FINDING_START_RE,
    finding_end_marker,
    finding_start_marker,
)
from core.reporting.section_markers import (
    segment_report_markdown,
    wrap_section_markdown,
)

_METADATA_ROW_RE = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.*?)\s*\|$")
_LOOT_MARKER_RE = re.compile(
    r"^<!--\s*spectre:loot:([A-Za-z0-9_-]+):([a-fA-F0-9]+)\s*-->", re.MULTILINE
)
_SEVERITY_CLEAN_RE = re.compile(r"\[?(CRITICAL|HIGH|MEDIUM|LOW|INFO)\]?", re.IGNORECASE)
_IMAGE_MD_RE = re.compile(r"^!\[(.*?)\]\((.*?)\)$", re.MULTILINE)
_CODE_BLOCK_RE = re.compile(r"^```([a-zA-Z0-9_-]*)\r?\n(.*?)\r?\n```", re.DOTALL | re.MULTILINE)

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
_TESTER_ALIASES = (
    "tester",
    "lead tester",
    "prüfer",
    "pentester",
    "analyst",
    "author",
    "autor",
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
_TIMEFRAME_ALIASES = (
    "testzeitraum",
    "assessment period",
    "zeitraum",
    "timeframe",
    "period",
)
_DATE_ALIASES = (
    "berichtsdatum",
    "report date",
    "datum",
    "date",
    "stand",
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


def _clean_md_val(val: str) -> str:
    cleaned = val.strip().strip("`").strip()
    cleaned = re.sub(r"[*_]", "", cleaned)
    return html.unescape(cleaned).strip()


def _first_match(data: Dict[str, str], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        norm = alias.strip().lower()
        if norm in data and data[norm]:
            return data[norm]
        clean = re.sub(r"[\s/()_-]+", " ", norm).strip()
        if clean in data and data[clean]:
            return data[clean]
    return ""


@dataclass
class ReportMetadata:
    title: str = ""
    client: str = ""
    tester: str = ""
    target_scope: str = ""
    timeframe: str = ""
    date: str = ""
    classification: str = ""
    version: str = "v1.0"
    custom_fields: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_markdown_table(cls, markdown: str) -> "ReportMetadata":
        title = ""
        kv: Dict[str, str] = {}
        for line in markdown.splitlines():
            line_str = line.strip()
            if line_str.startswith("# "):
                title = line_str[2:].strip()
                continue
            match = _METADATA_ROW_RE.match(line_str)
            if match:
                raw_k = match.group(1).strip().lower()
                val = _clean_md_val(match.group(2))
                kv[raw_k] = val
                norm_k = re.sub(r"[\s/()_-]+", " ", raw_k).strip()
                kv[norm_k] = val

        client = _first_match(kv, _CLIENT_ALIASES)
        tester = _first_match(kv, _TESTER_ALIASES)
        target = _first_match(kv, _TARGET_ALIASES)
        timeframe = _first_match(kv, _TIMEFRAME_ALIASES)
        date = _first_match(kv, _DATE_ALIASES)
        classification = _first_match(kv, _CLASSIFICATION_ALIASES)
        version = _first_match(kv, _VERSION_ALIASES) or "v1.0"

        # Capture any unmapped custom keys
        standard_keys = {
            *_CLIENT_ALIASES,
            *_TESTER_ALIASES,
            *_TARGET_ALIASES,
            *_TIMEFRAME_ALIASES,
            *_DATE_ALIASES,
            *_CLASSIFICATION_ALIASES,
            *_VERSION_ALIASES,
        }
        custom = {
            k: v
            for k, v in kv.items()
            if k not in standard_keys and re.sub(r"[\s/()_-]+", " ", k).strip() not in standard_keys
        }

        return cls(
            title=title,
            client=client,
            tester=tester,
            target_scope=target,
            timeframe=timeframe,
            date=date,
            classification=classification,
            version=version,
            custom_fields=custom,
        )

    def to_markdown_table(self, language: str = "de") -> str:
        date_str = self.date or datetime.now().strftime("%Y-%m-%d")
        title = self.title or ("Security Assessment Report" if language != "de" else "Sicherheitsbericht")
        lines = [f"# {title}", ""]
        if language == "de":
            lines.extend([
                "| Eigenschaft | Wert |",
                "|---|---|",
                f"| **Auftraggeber / Client** | `{self.client}` |",
                f"| **Tester** | `{self.tester}` |",
                f"| **Ziel(e) / Scope** | `{self.target_scope}` |",
                f"| **Testzeitraum** | `{self.timeframe}` |",
                f"| **Berichtsdatum** | `{date_str}` |",
                f"| **Klassifizierung** | `{self.classification or 'Vertraulich – Nur für internen Gebrauch'}` |",
                f"| **Report-Version** | `{self.version or 'v1.0'}` |",
            ])
        else:
            lines.extend([
                "| Property | Value |",
                "|---|---|",
                f"| **Client / Organization** | `{self.client}` |",
                f"| **Lead Tester** | `{self.tester}` |",
                f"| **Scope / Target** | `{self.target_scope}` |",
                f"| **Assessment Period** | `{self.timeframe}` |",
                f"| **Report Date** | `{date_str}` |",
                f"| **Classification** | `{self.classification or 'Confidential – Internal Use Only'}` |",
                f"| **Report Version** | `{self.version or 'v1.0'}` |",
            ])
        for k, v in self.custom_fields.items():
            lines.append(f"| **{k.capitalize()}** | `{v}` |")
        lines.append("")
        return "\n".join(lines)


@dataclass
class ReportEvidenceItem:
    id: str
    type: str  # "terminal", "screenshot", "credential", "code", "text"
    caption: str = ""
    content: str = ""
    source_loot_id: Optional[str] = None

    def to_markdown(self) -> str:
        if self.type == "screenshot":
            caption = self.caption or "Screenshot"
            return f"![{caption}]({self.content})"
        if self.type in ("terminal", "credential", "code"):
            lang = "bash" if self.type == "terminal" else ("text" if self.type == "credential" else "")
            return f"```{lang}\n{self.content}\n```"
        return self.content


@dataclass
class ReportFindingItem:
    id: str
    title: str = ""
    severity: str = "medium"
    cvss_score: Optional[float] = None
    cvss_vector: Optional[str] = None
    status: str = "open"  # "open", "in_progress", "resolved", "accepted_risk"
    phase: str = "recon"
    targets: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    description: str = ""
    evidence_items: List[ReportEvidenceItem] = field(default_factory=list)
    recommendation: str = ""
    references: List[str] = field(default_factory=list)
    loot_marker: Optional[str] = None
    raw_extra: str = ""

    def __post_init__(self) -> None:
        self.phase = normalize_phase_key(self.phase)

    @classmethod
    def from_markdown(cls, markdown: str, entry_id: str, language: str = "de") -> "ReportFindingItem":
        loot_match = _LOOT_MARKER_RE.search(markdown)
        loot_marker = loot_match.group(0) if loot_match else None

        title = ""
        heading_match = re.search(r"^###\s+(.*?)$", markdown, re.MULTILINE)
        if heading_match:
            title = heading_match.group(1).strip()

        severity = "medium"
        sev_match = re.search(r"\*\*Severity:\*\*\s*(.*?)(?:  |$)", markdown, re.MULTILINE)
        if sev_match:
            clean_sev = _SEVERITY_CLEAN_RE.search(sev_match.group(1))
            if clean_sev:
                severity = clean_sev.group(1).lower()

        targets: List[str] = []
        target_match = re.search(r"\*\*Target:\*\*\s*(.*?)(?:  |$)", markdown, re.MULTILINE)
        if target_match:
            val = _clean_md_val(target_match.group(1))
            if val:
                targets = [t.strip() for t in val.split(",") if t.strip()]

        phase = "recon"
        phase_match = re.search(r"\*\*Phase:\*\*\s*(.*?)(?:  |$)", markdown, re.MULTILINE)
        if phase_match:
            phase = normalize_phase_key(_clean_md_val(phase_match.group(1)))

        timestamp = None
        time_match = re.search(r"\*\*(?:Observed|Beobachtet):\*\*\s*(.*?)(?:  |$)", markdown, re.MULTILINE)
        if time_match:
            timestamp = _clean_md_val(time_match.group(1))

        status = "open"
        status_match = re.search(r"\*\*Status:\*\*\s*(.*?)(?:  |$)", markdown, re.MULTILINE)
        if status_match:
            raw_status = _clean_md_val(status_match.group(1)).lower()
            if raw_status in ("offen", "open"):
                status = "open"
            elif raw_status in ("behoben", "resolved", "closed"):
                status = "resolved"
            elif raw_status in ("in arbeit", "in_progress", "progress"):
                status = "in_progress"
            elif raw_status in ("akzeptiert", "accepted_risk", "accepted"):
                status = "accepted_risk"

        # Split description and recommendation sections
        desc_header = re.search(r"^####\s+(?:Beschreibung|Description)\s*$", markdown, re.MULTILINE | re.IGNORECASE)
        rec_header = re.search(r"^####\s+(?:Empfehlung|Recommendation)\s*$", markdown, re.MULTILINE | re.IGNORECASE)
        ref_header = re.search(r"^####\s+(?:Referenzen|References)\s*$", markdown, re.MULTILINE | re.IGNORECASE)

        description = ""
        recommendation = ""
        references: List[str] = []

        if desc_header:
            desc_start = desc_header.end()
            desc_end = len(markdown)
            for next_h in (rec_header, ref_header):
                if next_h and next_h.start() > desc_start:
                    desc_end = min(desc_end, next_h.start())
            desc_text = markdown[desc_start:desc_end]
            end_m = FINDING_END_RE.search(desc_text)
            if end_m:
                desc_text = desc_text[:end_m.start()]
            description = desc_text.strip()

        if rec_header:
            rec_start = rec_header.end()
            rec_end = len(markdown)
            if ref_header and ref_header.start() > rec_start:
                rec_end = ref_header.start()
            rec_text = markdown[rec_start:rec_end]
            end_m = FINDING_END_RE.search(rec_text)
            if end_m:
                rec_text = rec_text[:end_m.start()]
            recommendation = rec_text.strip()

        if ref_header:
            ref_block = markdown[ref_header.end():]
            end_m = FINDING_END_RE.search(ref_block)
            if end_m:
                ref_block = ref_block[:end_m.start()]
            for line in ref_block.strip().splitlines():
                line_str = line.strip().lstrip("-* ").strip()
                if line_str and not line_str.startswith("<!--"):
                    references.append(line_str)

        # Extract embedded evidence items (screenshots, code fences)
        evidence_items: List[ReportEvidenceItem] = []
        ev_idx = 1
        for img_match in _IMAGE_MD_RE.finditer(description):
            evidence_items.append(
                ReportEvidenceItem(
                    id=f"{entry_id}-img-{ev_idx}",
                    type="screenshot",
                    caption=img_match.group(1),
                    content=img_match.group(2),
                    source_loot_id=entry_id,
                )
            )
            ev_idx += 1

        for code_match in _CODE_BLOCK_RE.finditer(description):
            lang = (code_match.group(1) or "").strip().lower()
            ev_type = (
                "terminal"
                if lang in ("bash", "sh", "terminal", "console")
                else ("credential" if lang in ("credential", "credentials", "loot", "creds") else "code")
            )
            evidence_items.append(
                ReportEvidenceItem(
                    id=f"{entry_id}-code-{ev_idx}",
                    type=ev_type,
                    content=code_match.group(2),
                    source_loot_id=entry_id,
                )
            )
            ev_idx += 1

        return cls(
            id=entry_id,
            title=title,
            severity=severity,
            status=status,
            phase=phase,
            targets=targets,
            timestamp=timestamp,
            description=description,
            evidence_items=evidence_items,
            recommendation=recommendation,
            references=references,
            loot_marker=loot_marker,
        )

    def attach_evidence(
        self,
        item: ReportEvidenceItem,
        insert_into_description: bool = True,
    ) -> None:
        """Attaches an evidence item and optionally appends its Markdown to the description."""
        existing_idx = next((i for i, ev in enumerate(self.evidence_items) if ev.id == item.id), -1)
        if existing_idx >= 0:
            self.evidence_items[existing_idx] = item
        else:
            self.evidence_items.append(item)

        if insert_into_description:
            md = item.to_markdown()
            clean_content = item.content.strip()
            if clean_content and clean_content not in self.description:
                if self.description and not self.description.endswith("\n\n"):
                    if not self.description.endswith("\n"):
                        self.description += "\n\n"
                    else:
                        self.description += "\n"
                self.description += f"{md}\n"

    def detach_evidence(
        self,
        evidence_id: str,
        remove_from_description: bool = True,
    ) -> Optional[ReportEvidenceItem]:
        """Removes an evidence item and optionally strips its Markdown from the description."""
        found_idx = next((i for i, ev in enumerate(self.evidence_items) if ev.id == evidence_id), -1)
        if found_idx == -1:
            return None
        removed = self.evidence_items.pop(found_idx)
        if remove_from_description and removed.content:
            if removed.type == "screenshot":
                pattern = rf"!\[.*?\]\({re.escape(removed.content)}\)\r?\n?"
                self.description = re.sub(pattern, "", self.description).strip()
            else:
                block_pattern = rf"```[a-zA-Z0-9_-]*\r?\n{re.escape(removed.content)}\r?\n```\r?\n?"
                self.description = re.sub(block_pattern, "", self.description).strip()
        return removed

    def update_evidence(
        self,
        evidence_id: str,
        caption: Optional[str] = None,
        content: Optional[str] = None,
    ) -> bool:
        """Updates caption or content for an evidence item, synchronizing Markdown in description."""
        found = next((ev for ev in self.evidence_items if ev.id == evidence_id), None)
        if not found:
            return False

        old_caption = found.caption
        old_content = found.content

        if caption is not None:
            found.caption = caption
        if content is not None:
            found.content = content

        if found.type == "screenshot":
            old_tag = f"![{old_caption}]({old_content})"
            new_tag = f"![{found.caption}]({found.content})"
            if old_tag in self.description:
                self.description = self.description.replace(old_tag, new_tag)
            elif old_content in self.description:
                pattern = rf"!\[.*?\]\({re.escape(old_content)}\)"
                self.description = re.sub(pattern, new_tag, self.description)
        elif old_content and old_content in self.description:
            self.description = self.description.replace(old_content, found.content)

        return True

    def to_markdown(self, language: str = "de", include_phase: bool = False) -> str:
        lines = [finding_start_marker(self.id)]
        if self.loot_marker:
            lines.append(self.loot_marker)

        title = self.title or ("Unbenannter Eintrag" if language == "de" else "Unnamed Entry")
        lines.append(f"### {title}")
        lines.append("")

        meta_parts = [f"**Severity:** {render_severity_badge(self.severity, include_emoji=False)}"]
        if self.targets:
            meta_parts.append(f"**Target:** `{', '.join(self.targets)}`")
        if include_phase and self.phase:
            phase_label = "**Phase:**"
            meta_parts.append(f"{phase_label} {self.phase.capitalize()}")
        if self.timestamp:
            time_label = "**Beobachtet:**" if language == "de" else "**Observed:**"
            meta_parts.append(f"{time_label} `{self.timestamp}`")

        status_text = "Offen" if self.status == "open" else (
            "Behoben" if self.status == "resolved" else (
                "In Arbeit" if self.status == "in_progress" else "Akzeptiert"
            )
        )
        if language != "de":
            status_text = "Open" if self.status == "open" else (
                "Resolved" if self.status == "resolved" else (
                    "In Progress" if self.status == "in_progress" else "Accepted Risk"
                )
            )
        meta_parts.append(f"**Status:** {status_text}")

        lines.append("  \n".join(meta_parts))
        lines.append("")

        if self.description:
            lines.append("#### Beschreibung" if language == "de" else "#### Description")
            lines.append("")
            lines.append(self.description)
            lines.append("")

        if self.recommendation:
            lines.append("#### Empfehlung" if language == "de" else "#### Recommendation")
            lines.append("")
            lines.append(self.recommendation)
            lines.append("")

        if self.references:
            lines.append("#### Referenzen" if language == "de" else "#### References")
            lines.append("")
            for ref in self.references:
                lines.append(f"- {ref}")
            lines.append("")

        if self.raw_extra:
            lines.append(self.raw_extra)
            lines.append("")

        lines.append(finding_end_marker(self.id))
        return "\n".join(lines)


@dataclass
class ReportNarrativeSection:
    identity: str
    section_type: str
    title: str = ""
    content: str = ""
    options: Dict[str, Any] = field(default_factory=dict)
    page_break_before: bool = False

    def to_markdown(self) -> str:
        text = self.content.strip()
        if self.page_break_before:
            text = f"<!-- spectre:pagebreak -->\n\n{text}"
        return wrap_section_markdown(text, self.identity)


@dataclass
class ReportAppendix:
    commands_markdown: str = ""
    screenshots_markdown: str = ""
    raw_content: str = ""

    def to_markdown(self, title: str = "Anhang", language: str = "de") -> str:
        if self.raw_content:
            return self.raw_content
        lines = [f"## {title}", ""]
        if self.commands_markdown:
            lines.append(
                "### Anhang A: Ausgeführte Befehle" if language == "de" else "### Appendix A: Command History"
            )
            lines.append("")
            lines.append(self.commands_markdown)
            lines.append("")
        if self.screenshots_markdown:
            lines.append(
                "### Anhang B: Screenshots & Nachweise"
                if language == "de"
                else "### Appendix B: Screenshots & Evidence"
            )
            lines.append("")
            lines.append(self.screenshots_markdown)
            lines.append("")
        return "\n".join(lines).strip()


PHASE_NAMES_DE: Dict[str, str] = {
    "recon": "Aufklärung & Enumeration",
    "access": "Initialer Zugriff & Exploitation",
    "privesc": "Rechteausweitung (PrivEsc)",
    "postex": "Post-Exploitation & Lateral Movement",
    "scripts": "Eigene Skripte & PoCs",
    "misc": "Sonstiges",
}


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
            intro_raw = markdown[h2_end:first_h3.start()].strip()
            intro_text = intro_raw
        elif h2:
            intro_text = markdown[h2.end():].strip()

        # Helper to extract bullet value
        def _extract_bullet(patterns: List[str]) -> str:
            for pat in patterns:
                m = re.search(
                    rf"^[ \t]*[-*]\s+\*\*{pat}:\*\*\s*(.*?)$",
                    markdown,
                    re.MULTILINE | re.IGNORECASE,
                )
                if m:
                    return m.group(1).strip()
            return ""

        initial_access = _extract_bullet([
            "Initial Access Vector",
            "Initial Access / Schwachstelle",
            "Initial Access",
            "Initialer Zugriff",
        ])
        privilege_escalation = _extract_bullet([
            "Privilege Escalation",
            "Rechteausweitung",
            "PrivEsc",
        ])
        business_impact = _extract_bullet([
            "Business Impact & Risk",
            "Business Impact / Risiko",
            "Business Impact",
            "Geschäftsauswirkung",
            "Risiko",
        ])
        remediation_summary = _extract_bullet([
            "Recommended Remediation",
            "Empfohlene Remediation",
            "Empfohlene Maßnahmen",
            "Remediation",
        ])

        return cls(
            title=title,
            intro_text=intro_text,
            initial_access=initial_access,
            privilege_escalation=privilege_escalation,
            business_impact=business_impact,
            remediation_summary=remediation_summary,
        )

    def to_markdown(self, findings: List[ReportFindingItem], language: str = "de") -> str:
        lines: List[str] = []
        sec_title = self.title or "Executive Summary"
        lines.append(f"## {sec_title}")
        lines.append("")

        if self.intro_text.strip():
            lines.append(self.intro_text.strip())
            lines.append("")

        matrix_title = "### Findings-Übersicht" if language == "de" else "### Findings Matrix"
        lines.append(matrix_title)
        lines.append("")
        lines.append("| # | Finding | Severity | Phase | Status |")
        lines.append("|---|---------|----------|-------|--------|")

        sev_counts: Counter[str] = Counter()
        for idx, f in enumerate(findings, start=1):
            sev = f.severity.lower()
            sev_counts[sev] += 1
            t = (f.title or "Unnamed").replace("|", "\\|").replace("\n", " ")
            p_obj = get_phase(f.phase)
            ph_name = PHASE_NAMES_DE.get(p_obj.key, p_obj.long) if language == "de" else p_obj.long
            ph = ph_name.replace("|", "\\|").replace("\n", " ")
            st = "Offen" if f.status == "open" else ("Open" if language != "de" else "Offen")
            lines.append(f"| {idx} | {t} | {f.severity.upper()} | {ph} | {st} |")

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

        # Highlights section
        hl_title = "### Kernaussagen" if language == "de" else "### Key Highlights"
        lines.append(hl_title)
        lines.append("")
        if language == "de":
            lines.append(f"- **Initial Access / Schwachstelle:** {self.initial_access}".rstrip())
            lines.append(f"- **Privilege Escalation:** {self.privilege_escalation}".rstrip())
            lines.append(f"- **Business Impact / Risiko:** {self.business_impact}".rstrip())
            lines.append(f"- **Empfohlene Remediation:** {self.remediation_summary}".rstrip())
        else:
            lines.append(f"- **Initial Access Vector:** {self.initial_access}".rstrip())
            lines.append(f"- **Privilege Escalation:** {self.privilege_escalation}".rstrip())
            lines.append(f"- **Business Impact & Risk:** {self.business_impact}".rstrip())
            lines.append(f"- **Recommended Remediation:** {self.remediation_summary}".rstrip())

        return "\n".join(lines).strip()


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


@dataclass
class AttackPathStep:
    """Individual step in the attack chain / timeline."""

    step_number: int = 1
    phase: str = "recon"
    title: str = ""
    description: str = ""
    finding_id: Optional[str] = None


@dataclass
class ReportAttackPath:
    """Structured representation of the Attack Path / Assessment Narrative section."""

    title: str = "Angriffspfad / Assessment-Verlauf"
    narrative_intro: str = ""
    steps: List[AttackPathStep] = field(default_factory=list)

    @classmethod
    def from_markdown(cls, markdown: str, language: str = "de") -> "ReportAttackPath":
        default_title = (
            "Angriffspfad / Assessment-Verlauf"
            if language == "de"
            else "Attack Path / Assessment Narrative"
        )
        if not markdown:
            return cls(title=default_title)

        title = default_title
        h2 = re.search(r"^##\s+(.*?)$", markdown, re.MULTILINE)
        if h2:
            title = h2.group(1).strip()

        # Split intro from steps
        first_step = re.search(r"^[ \t]*(\d+)\.\s+", markdown, re.MULTILINE)
        first_h3 = re.search(r"^###\s+", markdown, re.MULTILINE)
        split_pos = None
        if first_h3 and (not first_step or first_h3.start() < first_step.start()):
            split_pos = first_h3.start()
        elif first_step:
            split_pos = first_step.start()

        narrative_intro = ""
        if split_pos is not None:
            start_pos = h2.end() if h2 else 0
            narrative_intro = markdown[start_pos:split_pos].strip()
        elif h2:
            narrative_intro = markdown[h2.end():].strip()

        # Parse steps: handles both detailed bullets and one-line legacy bullets
        steps: List[AttackPathStep] = []
        step_matches = list(
            re.finditer(
                r"^[ \t]*(\d+)\.\s+(.*?)(?=(?:\n[ \t]*\d+\.|\n[ \t]*##|\Z))",
                markdown,
                re.DOTALL | re.MULTILINE,
            )
        )

        for match in step_matches:
            num_str = match.group(1)
            step_body = match.group(2).strip()
            lines = step_body.splitlines()
            if not lines:
                continue

            first_line = lines[0].strip()
            m_header = re.search(r"\*\*(.*?)\*\*[:—\-]?\s*(.*)$", first_line)
            if m_header:
                raw_phase = m_header.group(1).strip()
                step_title = m_header.group(2).strip()
            else:
                raw_phase = "recon"
                step_title = first_line

            step_num = int(num_str) if num_str.isdigit() else (len(steps) + 1)
            norm_phase = normalize_phase_key(raw_phase)
            desc = ""
            fid = None

            for line in lines[1:]:
                clean_line = line.strip()
                m_desc = re.search(
                    r"[-*]\s*[*_]*(?:Beschreibung|Description)[:*_ \t]*\s*(.*)$",
                    clean_line,
                    re.IGNORECASE,
                )
                if m_desc:
                    desc = m_desc.group(1).strip().strip("*_").strip()
                m_find = re.search(
                    r"[-*]\s*[*_]*(?:Finding|Schwachstelle)[:*_ \t]*\s*(.*)$",
                    clean_line,
                    re.IGNORECASE,
                )
                if m_find:
                    raw_val = m_find.group(1).strip().strip("*_").strip()
                    m_id = re.search(r"<!--\s*finding:(.*?)\s*-->", raw_val)
                    if m_id:
                        fid = m_id.group(1).strip()
                    else:
                        fid = raw_val

            steps.append(
                AttackPathStep(
                    step_number=step_num,
                    phase=norm_phase,
                    title=step_title,
                    description=desc,
                    finding_id=fid,
                )
            )

        return cls(title=title, narrative_intro=narrative_intro, steps=steps)

    def to_markdown(
        self,
        findings: Optional[List[ReportFindingItem]] = None,
        language: str = "de",
    ) -> str:
        default_title = (
            "Angriffspfad / Assessment-Verlauf"
            if language == "de"
            else "Attack Path / Assessment Narrative"
        )
        sec_title = self.title or default_title
        lines: List[str] = [f"## {sec_title}", ""]

        if self.narrative_intro.strip():
            lines.append(self.narrative_intro.strip())
            lines.append("")

        if not self.steps:
            empty_msg = (
                "*Kein dokumentierter Angriffspfad vorhanden.*"
                if language == "de"
                else "*No documented attack path is available.*"
            )
            lines.append(empty_msg)
            lines.append("")
            return "\n".join(lines).strip()

        chain_title = "### Angriffskette" if language == "de" else "### Attack Chain"
        lines.append(chain_title)
        lines.append("")

        findings_map = {f.id: f for f in (findings or [])}

        for idx, s in enumerate(self.steps, start=1):
            p_obj = get_phase(s.phase)
            ph_name = PHASE_NAMES_DE.get(p_obj.key, p_obj.long) if language == "de" else p_obj.long
            step_header = f"{idx}. **{ph_name}**: {s.title or p_obj.short}"
            lines.append(step_header)
            if s.description.strip():
                lbl_desc = "Beschreibung" if language == "de" else "Description"
                lines.append(f"   - *{lbl_desc}:* {s.description.strip()}")
            if s.finding_id:
                linked_f = findings_map.get(s.finding_id)
                f_title = linked_f.title if linked_f else s.finding_id
                lbl_find = "Schwachstelle" if language == "de" else "Finding"
                lines.append(f"   - *{lbl_find}:* {f_title} <!-- finding:{s.finding_id} -->")

        lines.append("")
        return "\n".join(lines).strip()


@dataclass
class ReportWorkspaceDocument:
    metadata: ReportMetadata = field(default_factory=ReportMetadata)
    narratives: List[ReportNarrativeSection] = field(default_factory=list)
    findings: List[ReportFindingItem] = field(default_factory=list)
    appendix: Optional[ReportAppendix] = None
    language: str = "de"
    footer: str = ""
    unstructured_blocks: List[str] = field(default_factory=list)

    # --- Finding Operations ---

    def add_finding(self, finding: ReportFindingItem) -> None:
        self.findings.append(finding)

    def remove_finding(self, finding_id: str) -> bool:
        initial_len = len(self.findings)
        self.findings = [f for f in self.findings if f.id != finding_id]
        return len(self.findings) < initial_len

    def get_finding(self, finding_id: str) -> Optional[ReportFindingItem]:
        for f in self.findings:
            if f.id == finding_id:
                return f
        return None

    def update_finding(self, finding: ReportFindingItem) -> bool:
        for idx, f in enumerate(self.findings):
            if f.id == finding.id:
                self.findings[idx] = finding
                return True
        return False

    def reorder_findings(self, ordered_ids: List[str]) -> None:
        id_map = {f.id: f for f in self.findings}
        reordered: List[ReportFindingItem] = []
        for fid in ordered_ids:
            if fid in id_map:
                reordered.append(id_map[fid])
        # Append any unmentioned findings
        for f in self.findings:
            if f.id not in ordered_ids:
                reordered.append(f)
        self.findings = reordered

    def get_findings_by_severity(self) -> Dict[str, List[ReportFindingItem]]:
        buckets: Dict[str, List[ReportFindingItem]] = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
            "info": [],
        }
        for f in self.findings:
            sev = f.severity.lower()
            if sev in buckets:
                buckets[sev].append(f)
            else:
                buckets.setdefault("info", []).append(f)
        return buckets

    def get_findings_by_phase(self) -> Dict[str, List[ReportFindingItem]]:
        buckets: Dict[str, List[ReportFindingItem]] = {}
        for f in self.findings:
            phase = normalize_phase_key(f.phase)
            buckets.setdefault(phase, []).append(f)
        return buckets

    # --- Bidirectional Markdown Synchronisation ---

    @classmethod
    def from_markdown(cls, markdown_text: str, default_language: str = "de") -> "ReportWorkspaceDocument":
        if not markdown_text:
            return cls(language=default_language)

        # Detect language
        is_de = "auftraggeber" in markdown_text.lower() or "beschreibung" in markdown_text.lower() or "erstellt mit" in markdown_text.lower()
        language = "de" if is_de else ("en" if "client" in markdown_text.lower() or "description" in markdown_text.lower() else default_language)

        segments = segment_report_markdown(markdown_text)
        metadata = ReportMetadata()
        narratives: List[ReportNarrativeSection] = []
        findings: List[ReportFindingItem] = []
        appendix: Optional[ReportAppendix] = None
        unstructured: List[str] = []
        footer = ""

        # Check for footer
        footer_match = re.search(
            r"\n*---\s*\n+_(?:Generated with|Erstellt mit) "
            r"SpectreHUD Pentest & CTF Companion\b[^_\n]*_\s*$",
            markdown_text,
            re.IGNORECASE,
        )
        if footer_match:
            footer = footer_match.group(0).strip()

        for seg in segments:
            if seg.section_type == "header_metadata":
                metadata = ReportMetadata.from_markdown_table(seg.markdown)
            elif seg.section_type in ("finding_section", "phase_section"):
                # Parse all finding items inside this section
                cursor = 0
                while start := FINDING_START_RE.search(seg.markdown, cursor):
                    entry_id = start.group(1)
                    end = next(
                        (
                            m
                            for m in FINDING_END_RE.finditer(seg.markdown, start.end())
                            if m.group(1) == entry_id
                        ),
                        None,
                    )
                    if end is None:
                        break
                    block = seg.markdown[start.start():end.end()]
                    finding = ReportFindingItem.from_markdown(block, entry_id, language=language)
                    if seg.category_id:
                        finding.phase = normalize_phase_key(seg.category_id)
                    findings.append(finding)
                    cursor = end.end()

                # Clean finding blocks from section to retain narrative notes/custom text
                clean_sec_md = FINDING_START_RE.sub("", seg.markdown)
                clean_sec_md = FINDING_END_RE.sub("", clean_sec_md)
                clean_sec_md = _LOOT_MARKER_RE.sub("", clean_sec_md)
                # Keep narrative section container
                sec_title = ""
                h2 = re.search(r"^##\s+(.*?)$", seg.markdown, re.MULTILINE)
                if h2:
                    sec_title = h2.group(1).strip()
                narratives.append(
                    ReportNarrativeSection(
                        identity=seg.identity or seg.section_type,
                        section_type=seg.section_type,
                        title=sec_title,
                        content=clean_sec_md.strip(),
                    )
                )
            elif seg.section_type == "appendix":
                appendix = ReportAppendix(raw_content=seg.markdown)
                narratives.append(
                    ReportNarrativeSection(
                        identity=seg.identity or "appendix",
                        section_type="appendix",
                        title="Appendix" if language != "de" else "Anhang",
                        content=seg.markdown,
                    )
                )
            elif seg.is_structured:
                sec_title = ""
                h2 = re.search(r"^##\s+(.*?)$", seg.markdown, re.MULTILINE)
                if h2:
                    sec_title = h2.group(1).strip()
                narratives.append(
                    ReportNarrativeSection(
                        identity=seg.identity or seg.section_type,
                        section_type=seg.section_type,
                        title=sec_title,
                        content=seg.markdown,
                    )
                )
            else:
                if seg.markdown.strip() and seg.markdown.strip() != footer:
                    unstructured.append(seg.markdown)

        return cls(
            metadata=metadata,
            narratives=narratives,
            findings=findings,
            appendix=appendix,
            language=language,
            footer=footer,
            unstructured_blocks=unstructured,
        )

    def get_executive_summary(self) -> ReportExecutiveSummary:
        narr = next(
            (n for n in self.narratives if n.identity == "executive_summary" or n.section_type == "executive_summary"),
            None,
        )
        content = narr.content if narr else ""
        summary = ReportExecutiveSummary.from_markdown(content, language=self.language)
        if narr and narr.title:
            summary.title = narr.title
        return summary

    def set_executive_summary(self, summary: ReportExecutiveSummary) -> None:
        md = summary.to_markdown(self.findings, language=self.language)
        for n in self.narratives:
            if n.identity == "executive_summary" or n.section_type == "executive_summary":
                n.title = summary.title
                n.content = md
                return
        self.narratives.insert(
            0,
            ReportNarrativeSection(
                identity="executive_summary",
                section_type="executive_summary",
                title=summary.title,
                content=md,
            ),
        )

    def get_remediation_plan(self) -> ReportRemediationPlan:
        narrative = next(
            (n for n in self.narratives if n.identity == "remediation_table" or n.section_type == "remediation_table"),
            None,
        )
        content = narrative.content if narrative else ""
        return ReportRemediationPlan.from_markdown(content, language=self.language)

    def set_remediation_plan(self, plan: ReportRemediationPlan) -> None:
        md = plan.to_markdown(self.findings, language=self.language)
        for n in self.narratives:
            if n.identity == "remediation_table" or n.section_type == "remediation_table":
                n.title = plan.title
                n.content = md
                return
        self.narratives.append(
            ReportNarrativeSection(
                identity="remediation_table",
                section_type="remediation_table",
                title=plan.title,
                content=md,
            ),
        )

    def get_attack_path(self) -> ReportAttackPath:
        narrative = next(
            (n for n in self.narratives if n.identity == "attack_path" or n.section_type in ("attack_path", "attack_narrative")),
            None,
        )
        content = narrative.content if narrative else ""
        return ReportAttackPath.from_markdown(content, language=self.language)

    def set_attack_path(self, path: ReportAttackPath) -> None:
        md = path.to_markdown(self.findings, language=self.language)
        for n in self.narratives:
            if n.identity == "attack_path" or n.section_type in ("attack_path", "attack_narrative"):
                n.title = path.title
                n.content = md
                return
        self.narratives.append(
            ReportNarrativeSection(
                identity="attack_path",
                section_type="attack_path",
                title=path.title,
                content=md,
            ),
        )

    def _render_executive_summary_content(self, narrative: ReportNarrativeSection) -> str:
        """Regenerates findings matrix inside executive summary while preserving highlights and intro."""
        summary = ReportExecutiveSummary.from_markdown(narrative.content, language=self.language)
        if narrative.title:
            summary.title = narrative.title
        return summary.to_markdown(self.findings, language=self.language)

    def _render_remediation_table_content(self, narrative: ReportNarrativeSection) -> str:
        """Regenerates remediation table rows from current findings."""
        plan = ReportRemediationPlan.from_markdown(narrative.content, language=self.language)
        if narrative.title:
            plan.title = narrative.title
        return plan.to_markdown(self.findings, language=self.language)

    def _render_attack_path_content(self, narrative: ReportNarrativeSection) -> str:
        """Regenerates attack path content."""
        path = ReportAttackPath.from_markdown(narrative.content, language=self.language)
        if narrative.title:
            path.title = narrative.title
        return path.to_markdown(self.findings, language=self.language)

    def to_markdown(self, regenerate_matrices: bool = True) -> str:
        parts: List[str] = []

        # 1. Header Metadata
        header_text = self.metadata.to_markdown_table(language=self.language)
        parts.append(wrap_section_markdown(header_text.strip(), "header_metadata"))

        # Group findings by phase
        findings_by_phase = self.get_findings_by_phase()
        phase_findings_emitted: set[str] = set()

        # 2. Iterate narratives in defined order
        for narr in self.narratives:
            if narr.section_type == "header_metadata":
                continue  # already handled

            if narr.section_type == "executive_summary":
                content = (
                    self._render_executive_summary_content(narr)
                    if regenerate_matrices
                    else narr.content
                )
                parts.append(wrap_section_markdown(content.strip(), narr.identity))

            elif narr.section_type == "remediation_table":
                content = (
                    self._render_remediation_table_content(narr)
                    if regenerate_matrices
                    else narr.content
                )
                parts.append(wrap_section_markdown(content.strip(), narr.identity))

            elif narr.section_type in ("attack_path", "attack_narrative"):
                content = (
                    self._render_attack_path_content(narr)
                    if regenerate_matrices
                    else narr.content
                )
                parts.append(wrap_section_markdown(content.strip(), narr.identity))

            elif narr.section_type == "finding_section":
                # Unified findings section: render all findings
                sec_lines = [f"## {narr.title or 'Technische Findings'}", ""]
                for f in self.findings:
                    sec_lines.append(f.to_markdown(language=self.language, include_phase=True))
                    sec_lines.append("")
                phase_findings_emitted.update(f.id for f in self.findings)
                parts.append(wrap_section_markdown("\n".join(sec_lines).strip(), narr.identity))

            elif narr.section_type == "phase_section":
                cat_id = narr.identity.split(":")[-1] if ":" in narr.identity else "misc"
                phase_findings = findings_by_phase.get(cat_id, [])
                sec_lines = [f"## {narr.title or cat_id.capitalize()}", ""]
                if not phase_findings:
                    no_entries = (
                        "*Keine Einträge in dieser Phase.*"
                        if self.language == "de"
                        else "*No entries captured for this phase.*"
                    )
                    sec_lines.append(no_entries)
                    sec_lines.append("")
                else:
                    for f in phase_findings:
                        sec_lines.append(f.to_markdown(language=self.language, include_phase=False))
                        sec_lines.append("")
                        phase_findings_emitted.add(f.id)

                # Keep any user notes from narrative
                notes_lines = [
                    line for line in narr.content.splitlines()
                    if not line.strip().startswith("## ") and not line.strip().startswith("*Keine Einträge")
                ]
                if notes_lines:
                    sec_lines.append("\n".join(notes_lines).strip())
                    sec_lines.append("")

                parts.append(wrap_section_markdown("\n".join(sec_lines).strip(), narr.identity))

            elif narr.section_type == "appendix":
                app_content = (
                    self.appendix.to_markdown(title=narr.title, language=self.language)
                    if self.appendix
                    else narr.content
                )
                parts.append(wrap_section_markdown(app_content.strip(), narr.identity))

            else:
                # Custom / Scope / Attack path narrative
                parts.append(wrap_section_markdown(narr.content.strip(), narr.identity))

        # Check if there are unassigned findings not yet emitted
        remaining_findings = [f for f in self.findings if f.id not in phase_findings_emitted]
        if remaining_findings and not any(n.section_type == "finding_section" for n in self.narratives):
            extra_lines = ["## Technische Findings", ""]
            for f in remaining_findings:
                extra_lines.append(f.to_markdown(language=self.language, include_phase=True))
                extra_lines.append("")
            parts.append(wrap_section_markdown("\n".join(extra_lines).strip(), "finding_section"))

        # Append unstructured preamble/extra blocks if any
        for unstr in self.unstructured_blocks:
            if unstr.strip():
                parts.append(unstr.strip())

        body = "\n\n---\n\n".join(p for p in parts if p)

        # Footer
        footer = self.footer
        if not footer:
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M:%S")
            footer = (
                f"\n\n---\n\n_Erstellt mit SpectreHUD Pentest & CTF Companion am {date_str} um {time_str} Uhr_"
                if self.language == "de"
                else f"\n\n---\n\n_Generated with SpectreHUD Pentest & CTF Companion on {date_str} at {time_str}_"
            )
        elif not footer.startswith("\n"):
            footer = f"\n\n---\n\n{footer}"

        return body + footer

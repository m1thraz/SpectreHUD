"""
Template-based Reporting Engine for SpectreHUD.

Provides modular, structured, and extensible ReportTemplate definitions,
section renderers, and rendering context to generate professional Markdown pentest/CTF reports.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
import re

from core.loot_manager import CATEGORIES
from core.reporting.charts import render_severity_badge
from core.logger import get_logger

logger = get_logger("template_engine")

SECTION_NOTES_PLACEHOLDER_DE = "_Eigene Anmerkungen zu dieser Phase:_\n\n> "
SECTION_NOTES_PLACEHOLDER_EN = "_Notes & observations for this phase:_\n\n> "


def _wrap_code_fence(text: str, lang: str = "") -> List[str]:
    """Wraps text in a markdown code fence with adaptive backtick length."""
    backtick_runs = re.findall(r"`+", text)
    max_backticks = max([len(r) for r in backtick_runs], default=0)
    fence_len = max(3, max_backticks + 1)
    fence = "`" * fence_len
    return [f"{fence}{lang}", text, fence]


def _wrap_inline_code(text: str) -> str:
    """Wraps text in markdown inline code backticks with adaptive length."""
    if not text:
        return "``"
    backtick_runs = re.findall(r"`+", text)
    max_backticks = max([len(r) for r in backtick_runs], default=0)
    fence_len = max_backticks + 1
    fence = "`" * fence_len
    if text.startswith("`") or text.endswith("`"):
        return f"{fence} {text} {fence}"
    return f"{fence}{text}{fence}"


@dataclass(frozen=True)
class TemplateSection:
    type: str  # "header_metadata" | "executive_summary" | "scope_limitations" | "phase_section" | "remediation_table" | "appendix"
    title: Optional[str] = None
    category_id: Optional[str] = None  # for "phase_section"
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReportTemplate:
    id: str
    name: str
    language: str  # "de" | "en"
    category: str  # "ctf" | "pentest"
    complexity: str  # "simple" | "complex"
    sections: List[TemplateSection]
    is_builtin: bool = False


@dataclass
class ReportContext:
    loot_entries: List[Dict[str, Any]] = field(default_factory=list)
    clipboard_history: List[Dict[str, Any]] = field(default_factory=list)
    project_name: str = "Default"
    target_ip: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


def _render_header_metadata(section: TemplateSection, context: ReportContext, lang: str) -> str:
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    pname = context.project_name or "Default"
    target_ip = context.target_ip or (context.metadata.get("target_ip") if context.metadata else "")
    target_display = target_ip if target_ip and target_ip != "all" else "Alle Targets"

    default_title = (
        f"Pentest Report: {pname}" if lang == "de" else f"Security Assessment Report: {pname}"
    )
    title = section.title or default_title

    if lang == "de":
        lines = [
            f"# {title}",
            "",
            "| | |",
            "|---|---|",
            f"| **Auftraggeber / Client** | `{context.metadata.get('client', '')}` |",
            f"| **Tester** | `{context.metadata.get('tester', '')}` |",
            f"| **Ziel(e) / Scope** | `{target_display}` |",
            f"| **Testzeitraum** | `{context.metadata.get('timeframe', '')}` |",
            f"| **Berichtsdatum** | `{date_str}` |",
            f"| **Klassifizierung** | `{context.metadata.get('classification', 'Vertraulich – Nur für internen Gebrauch')}` |",
            f"| **Report-Version** | `{context.metadata.get('version', 'v1.0')}` |",
            "",
        ]
    else:
        lines = [
            f"# {title}",
            "",
            "| | |",
            "|---|---|",
            f"| **Client / Organization** | `{context.metadata.get('client', '')}` |",
            f"| **Lead Tester** | `{context.metadata.get('tester', '')}` |",
            f"| **Scope / Target** | `{target_display}` |",
            f"| **Assessment Period** | `{context.metadata.get('timeframe', '')}` |",
            f"| **Report Date** | `{date_str}` |",
            f"| **Classification** | `{context.metadata.get('classification', 'Confidential – Internal Use Only')}` |",
            f"| **Report Version** | `{context.metadata.get('version', 'v1.0')}` |",
            "",
        ]
    return "\n".join(lines)


def _render_executive_summary(section: TemplateSection, context: ReportContext, lang: str) -> str:
    all_entries = context.loot_entries
    critical = sum(1 for e in all_entries if str(e.get("severity", "")).lower() == "critical")
    high = sum(1 for e in all_entries if str(e.get("severity", "")).lower() == "high")
    medium = sum(1 for e in all_entries if str(e.get("severity", "")).lower() == "medium")
    low = sum(1 for e in all_entries if str(e.get("severity", "")).lower() == "low")

    finding_rows = []
    findings_count = 0
    for entry in all_entries:
        sev = str(entry.get("severity", "info")).lower()
        if sev != "info":
            findings_count += 1
            t = str(entry.get("title", "Unbenannt")).replace("|", "\\|").replace("\n", " ")
            cat = str(entry.get("category", "misc")).replace("|", "\\|").replace("\n", " ")
            finding_rows.append(f"| {findings_count} | {t} | {sev.upper()} | {cat} | Offen |")

    if not finding_rows:
        finding_rows = ["| | | | | |"]

    sec_title = section.title or ("Executive Summary" if lang == "de" else "Executive Summary")

    if lang == "de":
        lines = [
            f"## {sec_title}",
            "",
            "### Findings-Übersicht",
            "",
            "| # | Finding | Severity | Phase | Status |",
            "|---|---------|----------|-------|--------|",
            *finding_rows,
            "",
            f"**Gesamt:** 🔴 {critical} Critical · 🟠 {high} High · 🟡 {medium} Medium · 🟢 {low} Low",
            "",
            "### Kernaussagen",
            "",
            "- **Initial Access / Schwachstelle:**",
            "- **Privilege Escalation:**",
            "- **Business Impact / Risiko:**",
            "- **Empfohlene Remediation:**",
            "",
        ]
    else:
        lines = [
            f"## {sec_title}",
            "",
            "### Findings Matrix",
            "",
            "| # | Finding | Severity | Phase | Status |",
            "|---|---------|----------|-------|--------|",
            *finding_rows,
            "",
            f"**Total:** 🔴 {critical} Critical · 🟠 {high} High · 🟡 {medium} Medium · 🟢 {low} Low",
            "",
            "### Key Highlights",
            "",
            "- **Initial Access Vector:**",
            "- **Privilege Escalation:**",
            "- **Business Impact & Risk:**",
            "- **Recommended Remediation:**",
            "",
        ]
    return "\n".join(lines)


def _render_scope_limitations(section: TemplateSection, context: ReportContext, lang: str) -> str:
    sec_title = section.title or ("Scope & Limitations" if lang == "de" else "Scope & Limitations")

    if lang == "de":
        lines = [
            f"## {sec_title}",
            "",
            "- **In Scope:**",
            "- **Out of Scope:**",
            "- **Testmethodik:**",
            "- **Einschränkungen:**",
            "",
        ]
    else:
        lines = [
            f"## {sec_title}",
            "",
            "- **In Scope:**",
            "- **Out of Scope:**",
            "- **Methodology:**",
            "- **Limitations & Constraints:**",
            "",
        ]
    return "\n".join(lines)


def _render_loot_entry_block(entry: Dict[str, Any]) -> List[str]:
    entry_type = entry.get("type", "note")
    severity = str(entry.get("severity", "info")).lower()
    title = entry.get("title", "Unbenannter Eintrag")
    content = (entry.get("content") or "").strip()

    sev_badge = ""
    if severity and severity != "info":
        sev_badge = f"{render_severity_badge(severity)} "

    lines = [f"### {sev_badge}{title}"]
    meta = []
    if entry.get("target_ip"):
        meta.append(f"**Target:** {_wrap_inline_code(str(entry.get('target_ip')))}")
    if entry.get("timestamp"):
        meta.append(f"**Zeit:** {_wrap_inline_code(str(entry.get('timestamp')))}")
    if meta:
        lines.append(" | ".join(meta))
    lines.append("")

    if entry_type == "screenshot":
        if content.startswith("![") and content.endswith(")"):
            lines.append(content)
        else:
            lines.append(f"![{title}]({content})")
    elif entry_type in ("credentials", "hash", "flag"):
        lines.extend(_wrap_code_fence(content))
    elif entry_type == "directory":
        lines.append(_wrap_inline_code(content))
    else:
        lines.append(content)

    lines.append("")
    return lines


def _render_phase_section(section: TemplateSection, context: ReportContext, lang: str) -> str:
    category_id = section.category_id or "misc"
    cat_obj = next((c for c in CATEGORIES if c["id"] == category_id), None)
    cat_name = cat_obj["name"] if cat_obj else category_id.capitalize()
    sec_title = section.title or cat_name

    entries = [e for e in context.loot_entries if e.get("category") == category_id]

    lines = [f"## {sec_title}", ""]
    if not entries:
        no_entries = (
            "*Keine Einträge in dieser Phase.*"
            if lang == "de"
            else "*No entries captured for this phase.*"
        )
        lines.append(no_entries)
        lines.append("")
    else:
        for entry in reversed(entries):
            lines.extend(_render_loot_entry_block(entry))

    placeholder = SECTION_NOTES_PLACEHOLDER_DE if lang == "de" else SECTION_NOTES_PLACEHOLDER_EN
    lines.append(placeholder)
    lines.append("")
    return "\n".join(lines)


def _render_remediation_table(section: TemplateSection, context: ReportContext, lang: str) -> str:
    sec_title = section.title or (
        "Empfehlungen (Remediation-Plan)" if lang == "de" else "Remediation & Action Plan"
    )

    all_entries = context.loot_entries
    remed_rows = []
    num = 0
    for entry in all_entries:
        sev = str(entry.get("severity", "info")).lower()
        if sev in ("critical", "high", "medium", "low"):
            num += 1
            t = str(entry.get("title", "Finding")).replace("|", "\\|").replace("\n", " ")
            priority = {"critical": "P1", "high": "P2", "medium": "P3", "low": "P4"}.get(sev, "P3")
            remed_rows.append(f"| {priority} | {t} | Finding #{num} |")

    if not remed_rows:
        remed_rows = ["| | | |"]

    if lang == "de":
        lines = [
            f"## {sec_title}",
            "",
            "| Priorität | Empfehlung | Betrifft Finding # |",
            "|---|---|---|",
            *remed_rows,
            "",
        ]
    else:
        lines = [
            f"## {sec_title}",
            "",
            "| Priority | Recommendation | Affects Finding # |",
            "|---|---|---|",
            *remed_rows,
            "",
        ]
    return "\n".join(lines)


def _render_appendix(section: TemplateSection, context: ReportContext, lang: str) -> str:
    clip_history = context.clipboard_history
    target_ip = context.target_ip
    filtered_clips = (
        [
            c
            for c in clip_history
            if not target_ip or target_ip == "all" or c.get("target_ip") == target_ip
        ]
        if clip_history
        else []
    )
    screenshot_entries = [
        e
        for e in context.loot_entries
        if e.get("type") == "screenshot"
        and (not target_ip or target_ip == "all" or e.get("target_ip") == target_ip)
    ]

    lines = [
        "## Anhang A: Chronologischer Befehlsverlauf (Terminal History)"
        if lang == "de"
        else "## Appendix A: Terminal Command History",
        "",
    ]

    if not filtered_clips:
        no_cmds = (
            "*Keine Clipboard-Historie aufgezeichnet.*"
            if lang == "de"
            else "*No clipboard history recorded.*"
        )
        lines.append(no_cmds)
        lines.append("")
    else:
        chronological = list(reversed(filtered_clips))
        for i, item in enumerate(chronological, start=1):
            ts = item.get("timestamp", "").split(" ")[-1]
            target_tag = (
                f" {_wrap_inline_code('[' + str(item.get('target_ip')) + ']')}"
                if item.get("target_ip")
                else ""
            )
            lines.append(f"#### {i}. {_wrap_inline_code(ts)}{target_tag}")
            lines.extend(_wrap_code_fence(item.get("text", ""), lang="bash"))
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Anhang B: Screenshots" if lang == "de" else "## Appendix B: Screenshots")
    lines.append("")

    if not screenshot_entries:
        no_screens = (
            "*Keine Screenshots in diesem Projekt vorhanden.*"
            if lang == "de"
            else "*No screenshots captured in this project.*"
        )
        lines.append(no_screens)
        lines.append("")
    else:
        for entry in screenshot_entries:
            stitle = entry.get("title", "Screenshot")
            scontent = (entry.get("content") or "").strip()
            if scontent.startswith("![") and scontent.endswith(")"):
                lines.append(scontent)
            else:
                lines.append(f"![{stitle}]({scontent})")
            lines.append("")

    return "\n".join(lines)


class TemplateRenderer:
    """Renders a ReportTemplate with a ReportContext into structured Markdown."""

    SECTION_RENDERERS: Dict[str, Callable[[TemplateSection, ReportContext, str], str]] = {
        "header_metadata": _render_header_metadata,
        "executive_summary": _render_executive_summary,
        "scope_limitations": _render_scope_limitations,
        "phase_section": _render_phase_section,
        "remediation_table": _render_remediation_table,
        "appendix": _render_appendix,
    }

    def render(self, template: ReportTemplate, context: ReportContext) -> str:
        lang = template.language if template.language in ("de", "en") else "de"
        parts: List[str] = []

        for section in template.sections:
            renderer = self.SECTION_RENDERERS.get(section.type)
            if renderer:
                rendered_sec = renderer(section, context, lang)
                if rendered_sec.strip():
                    parts.append(rendered_sec.strip())

        body = "\n\n---\n\n".join(parts)

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        footer = (
            f"\n\n---\n\n_Erstellt mit SpectreHUD Pentest & CTF Companion am {date_str} um {time_str} Uhr_"
            if lang == "de"
            else f"\n\n---\n\n_Generated with SpectreHUD Pentest & CTF Companion on {date_str} at {time_str}_"
        )
        return body + footer


# Built-in Default / Legacy Pentest Template
LEGACY_DEFAULT_TEMPLATE = ReportTemplate(
    id="legacy_default",
    name="Standard Pentest Report (DE)",
    language="de",
    category="pentest",
    complexity="complex",
    is_builtin=True,
    sections=[
        TemplateSection(type="header_metadata"),
        TemplateSection(type="executive_summary"),
        TemplateSection(type="scope_limitations"),
        TemplateSection(type="phase_section", category_id="recon"),
        TemplateSection(type="phase_section", category_id="access"),
        TemplateSection(type="phase_section", category_id="privesc"),
        TemplateSection(type="phase_section", category_id="postex"),
        TemplateSection(type="phase_section", category_id="scripts"),
        TemplateSection(type="phase_section", category_id="misc"),
        TemplateSection(type="remediation_table"),
        TemplateSection(type="appendix"),
    ],
)

"""
Zentraler Report-Generator für SpectreHUD.

Erstellt strukturierte, professionelle Pentest- & CTF-Berichte im Markdown-Format.
Baut Metadaten-Tabellen, Executive Summary mit Findings-Matrix, Scope-Definitionen,
phänomenologische Kategorien (1. Recon bis 6. Misc), Remediation-Pläne,
sowie Anhänge für Terminal-History und Screenshot-Evidenzen.
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.loot_manager import CATEGORIES, LOOT_TYPES
from core.logger import get_logger

logger = get_logger("report_builder")

# Freitext-Platzhalter, der an das Ende jeder Kategorie-Sektion gehängt wird.
SECTION_NOTES_PLACEHOLDER = "_Eigene Anmerkungen zu dieser Phase:_\n\n> "


def _wrap_code_fence(text: str, lang: str = "") -> List[str]:
    """
    Wraps text in a markdown code fence with adaptive backtick length to prevent
    code-fence breakout and injection when content contains triple or consecutive backticks.
    """
    backtick_runs = re.findall(r"`+", text)
    max_backticks = max([len(r) for r in backtick_runs], default=0)
    fence_len = max(3, max_backticks + 1)
    fence = "`" * fence_len
    return [f"{fence}{lang}", text, fence]


def _wrap_inline_code(text: str) -> str:
    """
    Wraps text in markdown inline code backticks with adaptive length to prevent
    inline code breakage when content contains backticks.
    """
    if not text:
        return "``"
    backtick_runs = re.findall(r"`+", text)
    max_backticks = max([len(r) for r in backtick_runs], default=0)
    fence_len = max_backticks + 1
    fence = "`" * fence_len
    if text.startswith("`") or text.endswith("`"):
        return f"{fence} {text} {fence}"
    return f"{fence}{text}{fence}"


class ReportBuilder:
    """Baut den vollständigen, professionellen Markdown-Report aus Loot + Clipboard-History."""

    def __init__(self, loot_manager=None, clipboard_watcher=None, project_manager=None):
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher
        self.project_manager = project_manager

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def build(self, target_ip: Optional[str] = None, project_name: Optional[str] = None, template: Optional[Any] = None) -> str:
        """Baut den kompletten Report-String unter Verwendung der Template-Engine."""
        from core.reporting.template_engine import TemplateRenderer, LEGACY_DEFAULT_TEMPLATE, ReportContext
        
        all_loot = self.loot_manager.get_entries(target_ip=target_ip) if self.loot_manager else []
        all_clips = self.clipboard_watcher.get_history(target_ip=target_ip) if self.clipboard_watcher else []
        pname = project_name or (self.project_manager.get_active_project() if self.project_manager else "Default")
        tip = target_ip or ""

        context = ReportContext(
            loot_entries=all_loot,
            clipboard_history=all_clips,
            project_name=pname,
            target_ip=tip
        )

        active_template = template or LEGACY_DEFAULT_TEMPLATE
        return TemplateRenderer().render(active_template, context)

    def export(self, output_path: Path, target_ip: Optional[str] = None, project_name: Optional[str] = None) -> str:
        """Baut den Report und schreibt ihn atomar nach output_path (.md erzwungen)."""
        from core.atomic_write import atomic_write_text
        output_path = Path(output_path)
        if output_path.suffix.lower() != ".md":
            output_path = output_path.with_suffix(".md")

        content = self.build(target_ip=target_ip, project_name=project_name)
        try:
            if atomic_write_text(output_path, content):
                return f"Report erfolgreich generiert: {output_path.name}"
            else:
                logger.error(f"Failed to atomically export report to {output_path}")
                return f"Fehler beim Generieren des Reports: {output_path.name}"
        except OSError as e:
            logger.error(f"Failed to export report to {output_path}: {e}", exc_info=True)
            return f"Fehler beim Generieren des Reports: {e}"

    # ------------------------------------------------------------------ #
    # Header & Metadaten
    # ------------------------------------------------------------------ #

    def _render_header(self, target_ip: Optional[str], project_name: Optional[str], date_str: str) -> List[str]:
        target_display = target_ip if target_ip and target_ip != "all" else "Alle Targets"
        title = project_name if project_name else "Pentest / CTF Session"
        return [
            f"# Pentest Report: {title}",
            "",
            "| | |",
            "|---|---|",
            "| **Auftraggeber / Client** | `` |",
            "| **Tester** | `` |",
            f"| **Ziel(e) / Scope** | `{target_display}` |",
            "| **Testzeitraum** | `` – `` |",
            f"| **Berichtsdatum** | `{date_str}` |",
            "| **Klassifizierung** | `Vertraulich – Nur für internen Gebrauch` |",
            "| **Report-Version** | `v1.0` |",
            "",
            "---",
            "",
        ]

    def _render_executive_summary(self) -> List[str]:
        all_entries = self.loot_manager.get_entries() if self.loot_manager else []
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
                title = entry.get("title", "Unbenannt")
                cat = entry.get("category", "misc")
                finding_rows.append(f"| {findings_count} | {title} | {sev.upper()} | {cat} | Offen |")

        if not finding_rows:
            finding_rows = ["| | | | | |"]

        return [
            "## Executive Summary",
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
            "---",
            "",
        ]

    def _render_scope_limitations(self) -> List[str]:
        return [
            "## Scope & Limitations",
            "",
            "- **In Scope:**",
            "- **Out of Scope:**",
            "- **Testmethodik:**",
            "- **Einschränkungen:**",
            "",
            "---",
            "",
        ]

    # ------------------------------------------------------------------ #
    # Kategorien (1. Recon bis 6. Misc)
    # ------------------------------------------------------------------ #

    def _render_loot_sections(self, target_ip: Optional[str]) -> List[str]:
        """Eine Sektion pro Kategorie, in fester CATEGORIES-Reihenfolge."""
        all_entries = self.loot_manager.get_entries(target_ip=target_ip) if self.loot_manager else []
        lines: List[str] = []

        for category in sorted(CATEGORIES, key=lambda c: c["order"]):
            cat_entries = [e for e in all_entries if e.get("category") == category["id"]]

            lines.append(f"## {category['name']}")
            lines.append("")

            if not cat_entries:
                lines.append("*Keine Einträge in dieser Phase.*")
                lines.append("")
                continue

            # Chronologisch (älteste zuerst) - erzählt die Phase als Ablauf
            for entry in reversed(cat_entries):
                lines.extend(self._render_loot_entry(entry))

            lines.append(SECTION_NOTES_PLACEHOLDER)
            lines.append("")
            lines.append("---")
            lines.append("")

        return lines

    def _render_loot_entry(self, entry: Dict[str, Any]) -> List[str]:
        """Rendert einen einzelnen Loot-Eintrag passend zu seinem `type` und `severity`."""
        entry_type = entry.get("type", "note")
        severity = str(entry.get("severity", "info")).lower()
        title = entry.get("title", "Unbenannter Eintrag")
        content = (entry.get("content") or "").strip()

        sev_badge = ""
        if severity and severity != "info":
            from core.reporting.charts import render_severity_badge
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

    # ------------------------------------------------------------------ #
    # Remediation-Plan & Anhänge
    # ------------------------------------------------------------------ #

    def _render_remediation_plan(self) -> List[str]:
        return [
            "## Empfehlungen (Remediation-Plan)",
            "",
            "| Priorität | Empfehlung | Betrifft Finding # |",
            "|---|---|---|",
            "| | | |",
            "",
            "---",
            "",
        ]

    def _render_command_history(self, target_ip: Optional[str]) -> List[str]:
        lines = [
            "## Anhang A: Chronologischer Befehlsverlauf (Terminal History)",
            "",
        ]
        if not self.clipboard_watcher:
            lines.append("*Keine Clipboard-Historie aufgezeichnet.*")
            lines.append("")
            return lines

        history_items = self.clipboard_watcher.get_history(target_ip=target_ip)
        if not history_items:
            lines.append("*Keine Clipboard-Historie aufgezeichnet.*")
            lines.append("")
            return lines

        chronological = list(reversed(history_items))
        for i, item in enumerate(chronological, start=1):
            ts = item.get("timestamp", "").split(" ")[-1]
            target_tag = f" {_wrap_inline_code('[' + str(item.get('target_ip')) + ']')}" if item.get("target_ip") else ""
            lines.append(f"#### {i}. {_wrap_inline_code(ts)}{target_tag}")
            lines.extend(_wrap_code_fence(item.get("text", ""), lang="bash"))
            lines.append("")

        lines.append("---")
        lines.append("")
        return lines

    def _render_screenshots_appendix(self, target_ip: Optional[str]) -> List[str]:
        lines = [
            "## Anhang B: Screenshots",
            "",
        ]
        all_entries = self.loot_manager.get_entries(target_ip=target_ip) if self.loot_manager else []
        screenshots = [e for e in all_entries if e.get("type") == "screenshot"]

        if not screenshots:
            lines.append("*Keine Screenshots in diesem Projekt vorhanden.*")
            lines.append("")
            lines.append("---")
            lines.append("")
            return lines

        for i, entry in enumerate(reversed(screenshots), start=1):
            title = entry.get("title", f"Screenshot {i}")
            content = (entry.get("content") or "").strip()
            lines.append(f"### {i}. {title}")
            if entry.get("timestamp"):
                lines.append(f"**Zeitstempel:** `{entry.get('timestamp')}`  ")
            if entry.get("target_ip"):
                lines.append(f"**Target:** `{entry.get('target_ip')}`  ")
            lines.append("")
            if content.startswith("![") and content.endswith(")"):
                lines.append(content)
            else:
                lines.append(f"![{title}]({content})")
            lines.append("")

        lines.append("---")
        lines.append("")
        return lines

    def _render_footer(self, date_str: str, time_str: str) -> List[str]:
        return [
            f"*Erstellt mit SpectreHUD Pentest & CTF Companion – `{date_str} {time_str}`*",
            "",
        ]

"""
Zentraler Report-Generator für SpectreHUD.

Ersetzt die zwei bisher getrennten, divergierenden Markdown-Exporte
(LootManager.export_loot und ClipboardWatcher.export_report_markdown).
Beide pflegten eigene Alias-Listen und Rendering-Regeln, was schon jetzt
zu Inkonsistenzen (siehe: "cred"/"dir"-Bug) geführt hat und mit jeder
neuen Kategorie/jedem neuen Typ ein weiterer Ort wäre, an dem man Logik
synchron halten müsste.

Aufbau: pro Loot-Kategorie (core.loot_manager.CATEGORIES) eine Report-
Sektion, in fester Pentest-Reihenfolge (Recon -> Access -> PrivEsc ->
Post-Ex -> Scripts -> Misc). Innerhalb einer Sektion wird jeder Eintrag
je nach loot_manager.LOOT_TYPES-Typ passend gerendert (Code-Block, Bild-
Embed, Backtick-Inline). Am Ende jeder Sektion steht ein freier Markdown-
Platzhalter, den man beim Schreiben des Berichts direkt ausfüllen kann.

Die eigentliche Sektionsreihenfolge, das Sektions-Freitextfeld und der
Titel-Block sind bewusst über TEMPLATE_SECTIONS/HEADER_TEMPLATE als
Konstanten ausgelagert, damit sie sich später (z.B. für ein eigenes
Firmen-Reportformat) ohne Umbau der Rendering-Logik anpassen lassen.
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.loot_manager import CATEGORIES, LOOT_TYPES
from core.logger import get_logger

logger = get_logger("report_builder")

# Freitext-Platzhalter, der an das Ende jeder Kategorie-Sektion gehängt wird.
# So kann der Nutzer die automatisch gesammelten Rohdaten direkt im
# exportierten .md zu Fließtext ausformulieren, statt das separat zu tun.
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
    """Baut den vollständigen Markdown-Report aus Loot + Clipboard-History."""

    def __init__(self, loot_manager=None, clipboard_watcher=None, project_manager=None):
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher
        self.project_manager = project_manager

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def build(self, target_ip: Optional[str] = None, project_name: Optional[str] = None) -> str:
        """Baut den kompletten Report-String (noch nicht auf Disk geschrieben)."""
        lines: List[str] = []
        lines.extend(self._render_header(target_ip, project_name))
        lines.extend(self._render_loot_sections(target_ip))
        lines.extend(self._render_command_history(target_ip))
        lines.extend(self._render_footer())
        return "\n".join(lines)

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
    # Sektionen
    # ------------------------------------------------------------------ #

    def _render_header(self, target_ip: Optional[str], project_name: Optional[str]) -> List[str]:
        target_display = target_ip if target_ip and target_ip != "all" else "Alle Targets"
        title = f"Pentest Report: {project_name}" if project_name else "Pentest / CTF Session Report"
        return [
            f"# {title}",
            f"**Ziel:** {_wrap_inline_code(target_display)}  ",
            f"**Erstellt am:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`  ",
            "",
            "---",
            "",
        ]

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
        """Rendert einen einzelnen Loot-Eintrag passend zu seinem `type`."""
        entry_type = entry.get("type", "note")
        title = entry.get("title", "Unbenannter Eintrag")
        content = (entry.get("content") or "").strip()

        lines = [f"### {title}"]
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

    def _render_command_history(self, target_ip: Optional[str]) -> List[str]:
        lines = [
            "## Chronologischer Befehlsverlauf (Terminal History)",
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

    def _render_footer(self) -> List[str]:
        return [
            "## Executive Summary",
            "",
            "- **Initial Access / Schwachstelle:** ",
            "- **Privilege Escalation:** ",
            "- **Business Impact / Risiko:** ",
            "- **Empfohlene Remediation:** ",
            "",
        ]

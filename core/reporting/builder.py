"""
Zentraler Report-Generator für SpectreHUD.

Bietet die ReportBuilder-Facade zur Erstellung und zum atomaren Exportieren
von strukturierten Markdown-Berichten über die moderne Template-Engine.
"""

from pathlib import Path
from typing import Any, Optional

from core.logger import get_logger

logger = get_logger("report_builder")


class ReportBuilder:
    """Baut den vollständigen, professionellen Markdown-Report aus Loot + Clipboard-History."""

    def __init__(self, loot_manager=None, clipboard_watcher=None, project_manager=None):
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher
        self.project_manager = project_manager

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def build(
        self,
        target_ip: Optional[str] = None,
        project_name: Optional[str] = None,
        template: Optional[Any] = None,
    ) -> str:
        """Baut den kompletten Report-String unter Verwendung der Template-Engine."""
        from core.reporting.template_engine import (
            LEGACY_DEFAULT_TEMPLATE,
            ReportContext,
            TemplateRenderer,
        )

        all_loot = self.loot_manager.get_entries(target_ip=target_ip) if self.loot_manager else []
        raw_clips = (
            self.clipboard_watcher.get_history(target_ip=target_ip)
            if self.clipboard_watcher
            else []
        )
        has_raw = bool(raw_clips)
        try:
            all_clips = (
                self.clipboard_watcher.get_history(target_ip=target_ip, only_report=True)
                if self.clipboard_watcher
                else []
            )
        except TypeError:
            all_clips = [c for c in raw_clips if c.get("include_in_report", False)]

        pname = project_name or (
            self.project_manager.get_active_project() if self.project_manager else "Default"
        )
        tip = target_ip or ""

        context = ReportContext(
            loot_entries=all_loot,
            clipboard_history=all_clips,
            project_name=pname,
            target_ip=tip,
            has_raw_clipboard_history=has_raw,
        )

        active_template = template or LEGACY_DEFAULT_TEMPLATE
        return TemplateRenderer().render(active_template, context)

    def export(
        self, output_path: Path, target_ip: Optional[str] = None, project_name: Optional[str] = None
    ) -> str:
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


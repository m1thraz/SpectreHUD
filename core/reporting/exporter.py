"""
Core Facade for HTML Report Exporting in SpectreHUD.
"""

from pathlib import Path
from typing import Optional

from core.logger import get_logger
from core.atomic_write import atomic_write_text
from core.reporting.assets import MAX_EMBED_IMAGE_FILE_SIZE, encode_image_base64
from core.reporting.markdown import (
    sanitize_url,
    format_inline,
    resolve_and_embed_images,
    convert_markdown_to_html,
)
from core.reporting.template import render_report_html
from core.reporting.profiles import ReportExportProfile
from core.reporting.professional import (
    build_professional_cover_data,
    normalize_professional_severity,
    normalize_professional_timestamps,
    professional_section_has_meaningful_content,
    prune_professional_section_html,
    renumber_professional_heading,
    render_professional_cover,
    strip_professional_generator_footer,
)
from core.reporting.findings import (
    convert_markdown_with_findings,
)
from core.reporting.section_markers import segment_report_markdown, strip_section_markers

logger = get_logger(__name__)


class HtmlReportExporter:
    """Exports markdown reports to standalone, professionally styled HTML with base64 embedded images."""

    MAX_EMBED_IMAGE_FILE_SIZE = MAX_EMBED_IMAGE_FILE_SIZE

    @staticmethod
    def _encode_image_base64(image_path: Path) -> Optional[str]:
        """Encodes an image file to a base64 data URI."""
        return encode_image_base64(image_path)

    @classmethod
    def _resolve_and_embed_images(cls, md_text: str, project_dir: Optional[Path]) -> str:
        """Finds all ![alt](src) in markdown and embeds local images as base64 data URIs."""
        return resolve_and_embed_images(md_text, project_dir)

    @staticmethod
    def _sanitize_url(url: str, is_image: bool = False) -> str:
        """Sanitizes URLs for href or src attributes."""
        return sanitize_url(url, is_image=is_image)

    @classmethod
    def _format_inline(cls, text: str) -> str:
        """Formats inline markdown: bold, italic, inline code, links, images."""
        return format_inline(text)

    @classmethod
    def markdown_to_html(cls, md_text: str, project_dir: Optional[Path] = None) -> str:
        """Converts Markdown text to HTML body structure."""
        return convert_markdown_to_html(md_text, project_dir=project_dir)

    @classmethod
    def _professional_body_html(
        cls, markdown_content: str, project_dir: Optional[Path]
    ) -> str:
        markdown_content = strip_professional_generator_footer(markdown_content)
        embedded_markdown = resolve_and_embed_images(markdown_content, project_dir)
        class_names = {
            "header_metadata": "report-header-metadata",
            "executive_summary": "report-executive",
            "scope_limitations": "report-scope",
            "phase_section": "report-phase",
            "attack_path": "report-attack-path",
            "finding_section": "report-findings",
            "remediation_table": "report-remediation",
            "appendix": "report-appendix",
        }
        html_segments = []
        segments = segment_report_markdown(embedded_markdown)
        uses_phase_narrative = any(
            segment.is_structured and segment.section_type == "phase_section"
            for segment in segments
        )
        visible_number = 0
        for segment in segments:
            if segment.is_structured and not professional_section_has_meaningful_content(
                segment.section_type, segment.markdown
            ):
                continue
            segment_markdown = segment.markdown
            if segment.is_structured and not uses_phase_narrative:
                renumbered, changed = renumber_professional_heading(
                    segment_markdown, visible_number + 1
                )
                if changed:
                    visible_number += 1
                    segment_markdown = renumbered
            body = convert_markdown_with_findings(
                strip_section_markers(segment_markdown), project_dir=None
            )
            if not segment.is_structured:
                html_segments.append(body)
                continue
            body = prune_professional_section_html(segment.section_type, body)
            table_class = {
                "executive_summary": "findings-matrix",
                "remediation_table": "action-plan",
            }.get(segment.section_type)
            if table_class:
                body = body.replace("<table>", f'<table class="{table_class}">', 1)
            phase_attr = (
                f' data-phase="{segment.category_id}"' if segment.category_id else ""
            )
            html_segments.append(
                f'<section class="report-section {class_names[segment.section_type]}"'
                f"{phase_attr}>{body}</section>"
            )
        body_html = normalize_professional_severity("\n".join(html_segments))
        return normalize_professional_timestamps(body_html)

    @classmethod
    def build_full_html(
        cls,
        markdown_content: str,
        project_dir: Optional[Path] = None,
        project_name: Optional[str] = None,
        target_ip: Optional[str] = None,
        theme: str = "dark",
        report_font: str = "segoe_ui",
        language: str = "en",
        profile: ReportExportProfile | str = ReportExportProfile.INTERACTIVE,
    ) -> str:
        """Generates the full, styled HTML document ready for export."""
        active_profile = ReportExportProfile(profile)
        body_html = (
            cls._professional_body_html(markdown_content, project_dir)
            if active_profile is ReportExportProfile.PROFESSIONAL_PRINT
            else convert_markdown_with_findings(markdown_content, project_dir=project_dir)
        )
        pname = project_name or (project_dir.name if project_dir else "Target")
        cover_data = None
        if active_profile is ReportExportProfile.PROFESSIONAL_PRINT:
            cover_data = build_professional_cover_data(
                markdown_content,
                project_name=pname,
                target_ip=target_ip,
                language=language,
                body_html=body_html,
            )
            body_html = render_professional_cover(cover_data) + body_html
        return render_report_html(
            body_html=body_html,
            project_name=pname,
            target_ip=target_ip,
            theme=theme,
            report_font=report_font,
            language=language,
            profile=active_profile.value,
            classification=cover_data.classification if cover_data else None,
        )

    @classmethod
    def export_to_file(
        cls,
        markdown_content: str,
        output_path: Path,
        project_dir: Optional[Path] = None,
        project_name: Optional[str] = None,
        target_ip: Optional[str] = None,
        theme: str = "dark",
        report_font: str = "segoe_ui",
        language: str = "en",
        profile: ReportExportProfile | str = ReportExportProfile.INTERACTIVE,
    ) -> bool:
        """Renders HTML from Markdown and writes it atomically to output_path."""
        out = Path(output_path)
        if out.suffix.lower() != ".html":
            out = out.with_suffix(".html")

        full_html = cls.build_full_html(
            markdown_content=markdown_content,
            project_dir=project_dir,
            project_name=project_name,
            target_ip=target_ip,
            theme=theme,
            report_font=report_font,
            language=language,
            profile=profile,
        )
        try:
            return atomic_write_text(out, full_html, encoding="utf-8")
        except OSError as e:
            logger.error(f"Failed to write HTML report to {out}: {e}", exc_info=True)
            return False

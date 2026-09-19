"""
Core Facade for HTML Report Exporting in SpectreHUD.
"""

from pathlib import Path
from typing import Optional

from core.logger import get_logger
from core.atomic_write import atomic_write_text
from core.reporting.assets import MAX_EMBED_IMAGE_FILE_SIZE
from core.reporting.export_result import (
    ExportArtifact,
    ExportError,
    ExportErrorCode,
    ExportResult,
)
from core.reporting.markdown import resolve_and_embed_images
from core.reporting.attack_path_export import render_professional_attack_path
from core.reporting.template import render_report_html
from core.reporting.profiles import ReportExportProfile
from core.reporting.professional import (
    build_professional_cover_data,
    extract_report_title,
    normalize_professional_remediation_table,
    normalize_professional_severity,
    normalize_professional_timestamps,
    professional_section_has_meaningful_content,
    prune_professional_section_html,
    prune_unstructured_header_metadata_html,
    renumber_professional_heading,
    render_professional_cover,
    strip_professional_generator_footer,
    synchronize_professional_findings_matrix,
)
from core.reporting.findings import (
    FINDING_START_RE,
    convert_markdown_with_findings,
)
from core.reporting.section_markers import segment_report_markdown, strip_section_markers

logger = get_logger(__name__)


class HtmlReportExporter:
    """Exports markdown reports to standalone, professionally styled HTML with base64 embedded images."""

    MAX_EMBED_IMAGE_FILE_SIZE = MAX_EMBED_IMAGE_FILE_SIZE

    @classmethod
    def _professional_body_html(
        cls, markdown_content: str, project_dir: Optional[Path], language: str
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
        has_structured_header = any(
            segment.is_structured and segment.section_type == "header_metadata"
            for segment in segments
        )
        uses_phase_narrative = any(
            segment.is_structured and segment.section_type == "phase_section"
            for segment in segments
        )
        visible_number = 0
        finding_counter = 1
        for segment in segments:
            if segment.is_structured and not professional_section_has_meaningful_content(
                segment.section_type, segment.markdown
            ):
                continue
            segment_markdown = segment.markdown
            if segment.section_type == "executive_summary":
                segment_markdown = synchronize_professional_findings_matrix(
                    segment_markdown, markdown_content, language
                )
            if segment.is_structured and not uses_phase_narrative:
                renumbered, changed = renumber_professional_heading(
                    segment_markdown, visible_number + 1
                )
                if changed:
                    visible_number += 1
                    segment_markdown = renumbered
            clean_segment_markdown = strip_section_markers(segment_markdown)
            if segment.section_type == "attack_path":
                body = render_professional_attack_path(clean_segment_markdown, language)
            else:
                body = convert_markdown_with_findings(
                    clean_segment_markdown,
                    project_dir=None,
                    start_index=finding_counter,
                )
            finding_counter += len(FINDING_START_RE.findall(segment_markdown))
            if not segment.is_structured:
                if not has_structured_header:
                    body = prune_unstructured_header_metadata_html(body)
                if body.strip():
                    html_segments.append(body)
                continue
            body = prune_professional_section_html(segment.section_type, body)
            if not body.strip():
                continue
            table_class = {
                "executive_summary": "findings-matrix",
                "remediation_table": "action-plan",
            }.get(segment.section_type)
            if table_class:
                extra = (
                    " action-plan-4col"
                    if table_class == "action-plan" and "<th>" in body and body.count("<th>") >= 4
                    else ""
                )
                body = body.replace("<table>", f'<table class="{table_class}{extra}">', 1)
            phase_attr = f' data-phase="{segment.category_id}"' if segment.category_id else ""
            html_segments.append(
                f'<section class="report-section {class_names[segment.section_type]}"'
                f"{phase_attr}>{body}</section>"
            )
        body_html = normalize_professional_severity("\n".join(html_segments))
        body_html = normalize_professional_remediation_table(body_html)
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
        category: Optional[str] = None,
    ) -> str:
        """Generates the full, styled HTML document ready for export."""
        active_profile = ReportExportProfile(profile)
        if active_profile is ReportExportProfile.PROFESSIONAL_PRINT:
            body_html = cls._professional_body_html(markdown_content, project_dir, language)
        else:
            raw_html = convert_markdown_with_findings(markdown_content, project_dir=project_dir)
            body_html = normalize_professional_remediation_table(raw_html)
        title_from_md = extract_report_title(markdown_content)
        pname = (
            project_name
            or (project_dir.name if project_dir else None)
            or title_from_md
            or "Target"
        )
        cover_data = None
        if active_profile is ReportExportProfile.PROFESSIONAL_PRINT:
            cover_data = build_professional_cover_data(
                markdown_content,
                project_name=pname,
                target_ip=target_ip,
                language=language,
                body_html=body_html,
                category=category,
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
            report_label=cover_data.header_label if cover_data else None,
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
        category: Optional[str] = None,
    ) -> ExportResult:
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
            category=category,
        )
        try:
            success = atomic_write_text(out, full_html, encoding="utf-8")
            if not success:
                return ExportResult.failure(
                    ExportError(
                        code=ExportErrorCode.DESTINATION_ERROR,
                        message=f"Failed to write HTML report to {out}",
                    )
                )
            bytes_written = out.stat().st_size if out.exists() else len(full_html.encode("utf-8"))
            return ExportResult.success(
                artifacts=(ExportArtifact(path=out, format="html", bytes_written=bytes_written),)
            )
        except OSError as e:
            logger.error(f"Failed to write HTML report to {out}: {e}", exc_info=True)
            return ExportResult.failure(
                ExportError(
                    code=ExportErrorCode.DESTINATION_ERROR,
                    message=f"Failed to write HTML report to {out}: {e}",
                    details=str(e),
                )
            )

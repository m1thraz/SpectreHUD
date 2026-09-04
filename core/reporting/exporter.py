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
    def build_full_html(
        cls,
        markdown_content: str,
        project_dir: Optional[Path] = None,
        project_name: Optional[str] = None,
        target_ip: Optional[str] = None,
        theme: str = "dark",
        report_font: str = "segoe_ui",
        language: str = "en",
    ) -> str:
        """Generates the full, styled HTML document ready for export."""
        body_html = cls.markdown_to_html(markdown_content, project_dir=project_dir)
        pname = project_name or (project_dir.name if project_dir else "Target")
        return render_report_html(
            body_html=body_html,
            project_name=pname,
            target_ip=target_ip,
            theme=theme,
            report_font=report_font,
            language=language,
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
        )
        try:
            return atomic_write_text(out, full_html, encoding="utf-8")
        except OSError as e:
            logger.error(f"Failed to write HTML report to {out}: {e}", exc_info=True)
            return False

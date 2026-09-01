"""
HTML Report Exporter (Compatibility Facade).

Re-exports HtmlReportExporter from the modular core.reporting package.
"""

from core.reporting import (
    HtmlReportExporter,
    MAX_EMBED_IMAGE_FILE_SIZE,
    REPORT_CSS,
    encode_image_base64,
    sanitize_url,
    format_inline,
    resolve_and_embed_images,
    convert_markdown_to_html,
    render_report_html,
    render_severity_badge,
    render_metrics_summary,
)

__all__ = [
    "HtmlReportExporter",
    "MAX_EMBED_IMAGE_FILE_SIZE",
    "REPORT_CSS",
    "encode_image_base64",
    "sanitize_url",
    "format_inline",
    "resolve_and_embed_images",
    "convert_markdown_to_html",
    "render_report_html",
    "render_severity_badge",
    "render_metrics_summary",
]

"""
SpectreHUD Reporting Package.

Provides modular HTML report generation, CSS styling, markdown conversion, and charts.
"""

from core.reporting.exporter import HtmlReportExporter
from core.reporting.assets import MAX_EMBED_IMAGE_FILE_SIZE, REPORT_CSS, encode_image_base64
from core.reporting.markdown import (
    sanitize_url,
    format_inline,
    resolve_and_embed_images,
    convert_markdown_to_html,
)
from core.reporting.template import render_report_html
from core.reporting.charts import render_severity_badge, render_metrics_summary
from core.reporting.template_engine import (
    TemplateSection,
    ReportTemplate,
    ReportContext,
    TemplateRenderer,
    LEGACY_DEFAULT_TEMPLATE,
)
from core.reporting.template_repository import (
    TemplateRepository,
    template_to_dict,
    dict_to_template,
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
    "TemplateSection",
    "ReportTemplate",
    "ReportContext",
    "TemplateRenderer",
    "LEGACY_DEFAULT_TEMPLATE",
    "TemplateRepository",
    "template_to_dict",
    "dict_to_template",
]

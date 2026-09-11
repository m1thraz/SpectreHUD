"""
SpectreHUD Reporting Package.

Provides modular HTML report generation, CSS styling, markdown conversion, and charts.
"""

from core.reporting.exporter import HtmlReportExporter
from core.reporting.export_result import (
    ExportArtifact,
    ExportError,
    ExportErrorCode,
    ExportResult,
    ExportStatus,
)
from core.reporting.assets import (
    MAX_EMBED_IMAGE_FILE_SIZE,
    ImageEmbeddingBudget,
    encode_image_base64,
)
from core.reporting.styles import (
    REPORT_BASE_CSS,
    REPORT_CSS,
    REPORT_LIGHT_CSS,
    REPORT_PRINT_CSS,
    REPORT_PROFESSIONAL_CSS,
    get_report_css,
)
from core.reporting.markdown import (
    sanitize_url,
    format_inline,
    resolve_and_embed_images,
    convert_markdown_to_html,
)
from core.reporting.template import render_report_html
from core.reporting.profiles import ReportExportProfile
from core.reporting.section_markers import (
    KNOWN_SECTION_TYPES,
    RenderedSection,
    reconcile_section_markers,
    segment_report_markdown,
    wrap_section_markdown,
)
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
from core.reporting.file_manager import (
    ReportBackupError,
    ReportFileManager,
    ReportSaveError,
)
from core.reporting.builder import ReportBuilder
from core.reporting.note_formatter import append_report_note, format_report_note
from core.reporting.navigation import build_report_navigation
from core.reporting.draft_manager import (
    DRAFT_FILENAME,
    discard_draft,
    get_draft,
    get_draft_path,
    has_recoverable_draft,
    save_draft,
)
from core.reporting.loot_sync import (
    FALLBACK_SECTION_TITLE,
    LootReportState,
    PAGEBREAK_HTML,
    PAGEBREAK_MARKER,
    PAGEBREAK_REGEX,
    SPACER_REGEX,
    append_missing_loot_to_text,
    classify_loot_report_state,
    extract_report_markers,
    format_spacer_marker,
    loot_content_hash,
    preserve_markers_in_preview_roundtrip,
    strip_report_markers,
)
from core.reporting.outline import HeadingItem, extract_headings

__all__ = [
    "ExportArtifact",
    "ExportError",
    "ExportErrorCode",
    "ExportResult",
    "ExportStatus",
    "HtmlReportExporter",
    "MAX_EMBED_IMAGE_FILE_SIZE",
    "ImageEmbeddingBudget",
    "REPORT_BASE_CSS",
    "REPORT_CSS",
    "REPORT_LIGHT_CSS",
    "REPORT_PRINT_CSS",
    "REPORT_PROFESSIONAL_CSS",
    "get_report_css",
    "encode_image_base64",
    "sanitize_url",
    "format_inline",
    "resolve_and_embed_images",
    "convert_markdown_to_html",
    "render_report_html",
    "ReportExportProfile",
    "KNOWN_SECTION_TYPES",
    "RenderedSection",
    "reconcile_section_markers",
    "segment_report_markdown",
    "wrap_section_markdown",
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
    "ReportBackupError",
    "ReportFileManager",
    "ReportSaveError",
    "ReportBuilder",
    "append_report_note",
    "format_report_note",
    "build_report_navigation",
    "DRAFT_FILENAME",
    "discard_draft",
    "get_draft",
    "get_draft_path",
    "has_recoverable_draft",
    "save_draft",
    "FALLBACK_SECTION_TITLE",
    "LootReportState",
    "PAGEBREAK_HTML",
    "PAGEBREAK_MARKER",
    "PAGEBREAK_REGEX",
    "SPACER_REGEX",
    "append_missing_loot_to_text",
    "classify_loot_report_state",
    "extract_report_markers",
    "format_spacer_marker",
    "loot_content_hash",
    "preserve_markers_in_preview_roundtrip",
    "strip_report_markers",
    "HeadingItem",
    "extract_headings",
]


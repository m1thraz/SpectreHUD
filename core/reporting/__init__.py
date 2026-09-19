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
from core.reporting.report_palette import (
    PRINT_MARGIN_HEADER_COLOR,
    REPORT_ICON_COLORS,
    REPORT_LIGHT_PALETTE,
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
from core.reporting.print_layout import (
    PRINT_KEEP_TOGETHER,
    PRINT_KEEP_WITH_NEXT,
    PRINT_PAGE_START,
    SECTION_PRINT_LAYOUT_POLICIES,
    PrintLayoutPolicy,
    section_print_layout_attribute,
)
from core.reporting.section_markers import (
    KNOWN_SECTION_TYPES,
    RenderedSection,
    normalize_leading_section_pagebreaks,
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
from core.reporting.readiness import (
    ReportReadinessAssessment,
    ReportReadinessIssue,
    ReportReadinessLevel,
    assess_report_readiness,
)
from core.reporting.draft_manager import (
    DRAFT_FILENAME,
    discard_draft,
    get_draft,
    get_draft_path,
    has_recoverable_draft,
    save_draft,
)
from core.reporting.session import (
    ReportLoadState,
    ReportPersistFailureReason,
    ReportPersistResult,
    ReportRecoveryDraft,
    ReportSessionService,
)
from core.reporting.mutation_service import (
    ReportMutationFailureReason,
    ReportMutationResult,
    ReportMutationService,
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
    format_loot_marker,
    format_spacer_marker,
    loot_content_hash,
    preserve_markers_in_preview_roundtrip,
    strip_report_markers,
)
from core.reporting.loot_reconciliation import (
    LootDifferenceKind,
    LootReconciliationAction,
    LootReconciliationError,
    LootReconciliationItem,
    LootReconciliationResult,
    LootReconciliationSelection,
    analyze_loot_reconciliation,
    reconcile_loot_report,
)
from core.reporting.outline import HeadingItem, extract_headings
from core.reporting.report_metadata import ReportMetadata
from core.reporting.report_evidence import ReportEvidenceItem
from core.reporting.report_finding import ReportFindingItem
from core.reporting.report_appendix import ReportAppendix
from core.reporting.report_executive_summary import ReportExecutiveSummary
from core.reporting.report_remediation import ReportRemediationPlan
from core.reporting.report_attack_path import AttackPathStep, ReportAttackPath
from core.reporting.report_scope import (
    ReportScopeMethodology,
    ScopeExclusionItem,
    ScopeTargetItem,
)
from core.reporting.workspace_model import (
    ReportNarrativeSection,
    ReportWorkspaceDocument,
)
from core.reporting.finding_conversion import (
    duplicate_report_finding,
    evidence_from_loot_entry,
    finding_from_loot_entry,
    supporting_evidence_from_loot_entry,
)
from core.reporting.finding_promotion import (
    FindingPromotionFailureReason,
    FindingPromotionResult,
    FindingPromotionService,
    LootFindingPromotionStore,
)
from core.reporting.evidence_markers import (
    format_evidence_block,
    parse_evidence_blocks,
    reconcile_evidence_markers,
    replace_evidence_block,
    strip_evidence_markers,
)
from core.reporting.professional import (
    strip_generator_footer,
    strip_professional_generator_footer,
)
from core.reporting.evidence_bundler import (
    ALLOWED_CORRELATION_WINDOWS,
    AlreadyAttachedKey,
    EvidenceCandidate,
    EvidenceSuggestion,
    SourceType,
    calculate_unscoped_proximity_seconds,
    normalize_correlation_window_seconds,
    suggest_related_evidence,
)

__all__ = [
    "ALLOWED_CORRELATION_WINDOWS",
    "AlreadyAttachedKey",
    "EvidenceCandidate",
    "EvidenceSuggestion",
    "SourceType",
    "calculate_unscoped_proximity_seconds",
    "normalize_correlation_window_seconds",
    "suggest_related_evidence",
    "strip_generator_footer",
    "strip_professional_generator_footer",
    "ExportArtifact",
    "ExportError",
    "ExportErrorCode",
    "ExportResult",
    "ExportStatus",
    "HtmlReportExporter",
    "MAX_EMBED_IMAGE_FILE_SIZE",
    "ImageEmbeddingBudget",
    "PRINT_MARGIN_HEADER_COLOR",
    "REPORT_BASE_CSS",
    "REPORT_CSS",
    "REPORT_ICON_COLORS",
    "REPORT_LIGHT_CSS",
    "REPORT_LIGHT_PALETTE",
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
    "PrintLayoutPolicy",
    "PRINT_PAGE_START",
    "PRINT_KEEP_TOGETHER",
    "PRINT_KEEP_WITH_NEXT",
    "SECTION_PRINT_LAYOUT_POLICIES",
    "section_print_layout_attribute",
    "KNOWN_SECTION_TYPES",
    "RenderedSection",
    "normalize_leading_section_pagebreaks",
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
    "ReportReadinessAssessment",
    "ReportReadinessIssue",
    "ReportReadinessLevel",
    "assess_report_readiness",
    "DRAFT_FILENAME",
    "discard_draft",
    "get_draft",
    "get_draft_path",
    "has_recoverable_draft",
    "save_draft",
    "ReportLoadState",
    "ReportPersistFailureReason",
    "ReportPersistResult",
    "ReportRecoveryDraft",
    "ReportSessionService",
    "ReportMutationFailureReason",
    "ReportMutationResult",
    "ReportMutationService",
    "FALLBACK_SECTION_TITLE",
    "LootReportState",
    "PAGEBREAK_HTML",
    "PAGEBREAK_MARKER",
    "PAGEBREAK_REGEX",
    "SPACER_REGEX",
    "append_missing_loot_to_text",
    "classify_loot_report_state",
    "extract_report_markers",
    "format_loot_marker",
    "format_spacer_marker",
    "loot_content_hash",
    "preserve_markers_in_preview_roundtrip",
    "strip_report_markers",
    "LootDifferenceKind",
    "LootReconciliationAction",
    "LootReconciliationError",
    "LootReconciliationItem",
    "LootReconciliationResult",
    "LootReconciliationSelection",
    "analyze_loot_reconciliation",
    "reconcile_loot_report",
    "HeadingItem",
    "extract_headings",
    "AttackPathStep",
    "ReportAppendix",
    "ReportAttackPath",
    "ReportEvidenceItem",
    "ReportExecutiveSummary",
    "ReportFindingItem",
    "ReportMetadata",
    "ReportNarrativeSection",
    "ReportRemediationPlan",
    "ReportScopeMethodology",
    "ReportWorkspaceDocument",
    "ScopeExclusionItem",
    "ScopeTargetItem",
    "duplicate_report_finding",
    "evidence_from_loot_entry",
    "finding_from_loot_entry",
    "format_evidence_block",
    "parse_evidence_blocks",
    "reconcile_evidence_markers",
    "replace_evidence_block",
    "strip_evidence_markers",
    "supporting_evidence_from_loot_entry",
    "FindingPromotionFailureReason",
    "FindingPromotionResult",
    "FindingPromotionService",
    "LootFindingPromotionStore",
]

"""UI building blocks used by the report editor."""

from ui.report.dialogs import (
    ClipboardHistoryPickerDialog,
    LootEntryPickerDialog,
    LootImagePickerDialog,
    ReportExportTypeDialog,
    select_html_export_options,
)
from ui.report.export_actions import ReportExportActions
from ui.report.format_actions import ReportFormatActions
from ui.report.workspace_navigator import ReportWorkspaceNavigator
from ui.report.metadata_inspector import ReportMetadataInspector
from ui.report.finding_inspector import ReportFindingInspector
from ui.report.section_inspector import ReportSectionInspector
from ui.report.summary_inspector import ReportSummaryInspector
from ui.report.remediation_inspector import ReportRemediationInspector
from ui.report.attack_path_inspector import ReportAttackPathInspector

__all__ = [
    "ClipboardHistoryPickerDialog",
    "LootEntryPickerDialog",
    "LootImagePickerDialog",
    "ReportAttackPathInspector",
    "ReportExportActions",
    "ReportExportTypeDialog",
    "ReportFormatActions",
    "ReportFindingInspector",
    "ReportMetadataInspector",
    "ReportRemediationInspector",
    "ReportSectionInspector",
    "ReportSummaryInspector",
    "ReportWorkspaceNavigator",
    "select_html_export_options",
]

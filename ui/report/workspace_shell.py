"""Construction and layout primitives for the Report Workspace shell."""

from dataclasses import dataclass
from typing import Any, Callable

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QSplitter, QStackedWidget, QVBoxLayout, QWidget

from core.i18n import t
from ui.glass_panel import GlassPanel
from ui.markdown_highlighter import MarkdownHighlighter
from ui.report.appendix_inspector import ReportAppendixInspector
from ui.report.attack_path_inspector import ReportAttackPathInspector
from ui.report.evidence_actions import ReportEvidenceActions
from ui.report.find_replace import FindReplaceBar
from ui.report.finding_inspector import ReportFindingInspector
from ui.report.metadata_inspector import ReportMetadataInspector
from ui.report.navigation import ReportLocation
from ui.report.preview import ReportDocument, ReportPreviewEdit
from ui.report.readiness_inspector import ReportReadinessInspector
from ui.report.remediation_inspector import ReportRemediationInspector
from ui.report.scope_inspector import ReportScopeInspector
from ui.report.section_inspector import ReportSectionInspector
from ui.report.source_editor import ReportSourceEditor
from ui.report.summary_inspector import ReportSummaryInspector
from ui.report.workspace_navigator import ReportWorkspaceNavigator
from ui.report.workspace_router import (
    InspectorSurface,
    ReportWorkspaceRouter,
    ReportWorkspaceSurfaces,
)


class ResponsiveStackedWidget(QStackedWidget):
    """Size the stack from its active inspector instead of every child."""

    def minimumSizeHint(self) -> QSize:
        current = self.currentWidget()
        if current is not None and current.isVisible():
            hint = current.minimumSizeHint()
            if hint.isValid() and hint.width() > 0:
                return QSize(min(hint.width(), 320), hint.height())
        return QSize(200, 100)


@dataclass(frozen=True)
class ReportWorkspaceCallbacks:
    navigate: Callable[[ReportLocation], None]
    add_finding: Callable[[], None]
    promote_finding: Callable[[], None]
    sync_loot: Callable[[], None]
    text_changed: Callable[[], None]
    metadata_changed: Callable[[Any], None]
    finding_changed: Callable[[Any], None]
    finding_deleted: Callable[[str], None]
    finding_duplicated: Callable[[str], None]
    section_changed: Callable[[str, str], None]
    summary_changed: Callable[[Any], None]
    finding_action_changed: Callable[[str, str, str], None]
    remediation_plan_changed: Callable[[Any], None]
    attack_path_changed: Callable[[Any], None]
    scope_changed: Callable[[Any], None]
    appendix_changed: Callable[[Any], None]
    editor_scroll: Callable[[int], None]
    preview_scroll: Callable[[int], None]


@dataclass(frozen=True)
class ReportWorkspaceShell:
    splitter: QSplitter
    navigator: ReportWorkspaceNavigator
    navigator_glass: GlassPanel
    center_stack: ResponsiveStackedWidget
    editor: ReportSourceEditor
    highlighter: MarkdownHighlighter
    find_replace: FindReplaceBar
    editor_glass: GlassPanel
    metadata_inspector: ReportMetadataInspector
    metadata_inspector_glass: GlassPanel
    readiness_inspector: ReportReadinessInspector
    readiness_inspector_glass: GlassPanel
    finding_inspector: ReportFindingInspector
    finding_inspector_glass: GlassPanel
    section_inspector: ReportSectionInspector
    section_inspector_glass: GlassPanel
    summary_inspector: ReportSummaryInspector
    summary_inspector_glass: GlassPanel
    remediation_inspector: ReportRemediationInspector
    remediation_inspector_glass: GlassPanel
    attack_path_inspector: ReportAttackPathInspector
    attack_path_inspector_glass: GlassPanel
    scope_inspector: ReportScopeInspector
    scope_inspector_glass: GlassPanel
    appendix_inspector: ReportAppendixInspector
    appendix_inspector_glass: GlassPanel
    preview_document: ReportDocument
    preview: ReportPreviewEdit
    preview_glass: GlassPanel
    router: ReportWorkspaceRouter


def wrap_glass_surface(widget: QWidget) -> GlassPanel:
    panel = GlassPanel()
    panel.setProperty("class", "ReportGlassPanel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(widget)
    viewport = getattr(widget, "viewport", None)
    if callable(viewport) and viewport():
        viewport().setAutoFillBackground(False)
    return panel


def build_report_workspace_shell(
    *,
    parent: QWidget,
    callbacks: ReportWorkspaceCallbacks,
    evidence_actions: ReportEvidenceActions,
) -> ReportWorkspaceShell:
    splitter = QSplitter(parent)
    splitter.setChildrenCollapsible(False)
    splitter.setHandleWidth(6)

    navigator = ReportWorkspaceNavigator(parent)
    navigator.navigate_requested.connect(callbacks.navigate)
    navigator.add_finding_requested.connect(callbacks.add_finding)
    navigator.promote_finding_requested.connect(callbacks.promote_finding)
    navigator.sync_loot_requested.connect(callbacks.sync_loot)
    navigator_glass = wrap_glass_surface(navigator)
    navigator_glass.setMinimumWidth(180)
    navigator_glass.setMaximumWidth(550)
    navigator_glass.setVisible(False)
    splitter.addWidget(navigator_glass)

    center_stack = ResponsiveStackedWidget(parent)
    center_stack.setMinimumWidth(200)
    editor = ReportSourceEditor()
    editor.setPlaceholderText(
        t(
            "report.editor_placeholder",
            "No report available for this project yet.\n\n"
            "Click 'Regenerate from Loot' above to start with an "
            "auto-generated report, or write your markdown directly here.",
        )
    )
    editor.setProperty("class", "ReportSourceEditor")
    editor.textChanged.connect(callbacks.text_changed)
    highlighter = MarkdownHighlighter(editor.document())
    find_replace = FindReplaceBar(editor, parent)
    editor_glass = wrap_glass_surface(editor)
    center_stack.addWidget(editor_glass)

    metadata = ReportMetadataInspector(parent)
    metadata.metadata_changed.connect(callbacks.metadata_changed)
    metadata_glass = wrap_glass_surface(metadata)
    center_stack.addWidget(metadata_glass)
    readiness = ReportReadinessInspector(parent)
    readiness.navigate_requested.connect(callbacks.navigate)
    readiness_glass = wrap_glass_surface(readiness)
    center_stack.addWidget(readiness_glass)

    finding = ReportFindingInspector(parent)
    finding.finding_changed.connect(callbacks.finding_changed)
    finding.finding_deleted.connect(callbacks.finding_deleted)
    finding.finding_duplicated.connect(callbacks.finding_duplicated)
    finding.request_loot_screenshot.connect(evidence_actions.attach_loot_screenshot)
    finding.request_image_file.connect(evidence_actions.attach_image_file)
    finding.request_clipboard_history.connect(evidence_actions.attach_clipboard_history)
    finding.request_loot_entry.connect(evidence_actions.attach_loot_entry)
    finding.request_create_finding.connect(callbacks.add_finding)
    finding.request_promote_loot.connect(callbacks.promote_finding)
    finding_glass = wrap_glass_surface(finding)
    center_stack.addWidget(finding_glass)

    section = ReportSectionInspector(parent)
    section.section_changed.connect(callbacks.section_changed)
    section_glass = wrap_glass_surface(section)
    center_stack.addWidget(section_glass)
    summary = ReportSummaryInspector(parent)
    summary.summary_changed.connect(callbacks.summary_changed)
    summary.finding_selected.connect(
        lambda finding_id: callbacks.navigate(ReportLocation.finding(finding_id))
    )
    summary_glass = wrap_glass_surface(summary)
    center_stack.addWidget(summary_glass)
    remediation = ReportRemediationInspector(parent)
    remediation.finding_action_changed.connect(callbacks.finding_action_changed)
    remediation.plan_changed.connect(callbacks.remediation_plan_changed)
    remediation.finding_selected.connect(
        lambda finding_id: callbacks.navigate(ReportLocation.finding(finding_id))
    )
    remediation_glass = wrap_glass_surface(remediation)
    center_stack.addWidget(remediation_glass)
    attack_path = ReportAttackPathInspector(parent)
    attack_path.attack_path_changed.connect(callbacks.attack_path_changed)
    attack_path.finding_selected.connect(
        lambda finding_id: callbacks.navigate(ReportLocation.finding(finding_id))
    )
    attack_path_glass = wrap_glass_surface(attack_path)
    center_stack.addWidget(attack_path_glass)
    scope = ReportScopeInspector(parent)
    scope.scope_changed.connect(callbacks.scope_changed)
    scope_glass = wrap_glass_surface(scope)
    center_stack.addWidget(scope_glass)
    appendix = ReportAppendixInspector(parent)
    appendix.appendix_changed.connect(callbacks.appendix_changed)
    appendix_glass = wrap_glass_surface(appendix)
    center_stack.addWidget(appendix_glass)
    splitter.addWidget(center_stack)

    preview_document = ReportDocument(parent=parent)
    preview = ReportPreviewEdit()
    preview.setDocument(preview_document)
    preview.setReadOnly(True)
    preview.setProperty("class", "ReportPreview")
    preview_glass = wrap_glass_surface(preview)
    preview_glass.setMinimumWidth(150)
    splitter.addWidget(preview_glass)

    router = ReportWorkspaceRouter(
        ReportWorkspaceSurfaces(
            metadata=InspectorSurface(metadata, metadata_glass),
            readiness=InspectorSurface(readiness, readiness_glass),
            finding=InspectorSurface(finding, finding_glass),
            section=InspectorSurface(section, section_glass),
            summary=InspectorSurface(summary, summary_glass),
            remediation=InspectorSurface(remediation, remediation_glass),
            attack_path=InspectorSurface(attack_path, attack_path_glass),
            scope=InspectorSurface(scope, scope_glass),
            appendix=InspectorSurface(appendix, appendix_glass),
            raw_markdown=editor_glass,
        )
    )
    editor.verticalScrollBar().valueChanged.connect(callbacks.editor_scroll)
    preview.verticalScrollBar().valueChanged.connect(callbacks.preview_scroll)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    splitter.setStretchFactor(2, 1)

    return ReportWorkspaceShell(
        splitter=splitter,
        navigator=navigator,
        navigator_glass=navigator_glass,
        center_stack=center_stack,
        editor=editor,
        highlighter=highlighter,
        find_replace=find_replace,
        editor_glass=editor_glass,
        metadata_inspector=metadata,
        metadata_inspector_glass=metadata_glass,
        readiness_inspector=readiness,
        readiness_inspector_glass=readiness_glass,
        finding_inspector=finding,
        finding_inspector_glass=finding_glass,
        section_inspector=section,
        section_inspector_glass=section_glass,
        summary_inspector=summary,
        summary_inspector_glass=summary_glass,
        remediation_inspector=remediation,
        remediation_inspector_glass=remediation_glass,
        attack_path_inspector=attack_path,
        attack_path_inspector_glass=attack_path_glass,
        scope_inspector=scope,
        scope_inspector_glass=scope_glass,
        appendix_inspector=appendix,
        appendix_inspector_glass=appendix_glass,
        preview_document=preview_document,
        preview=preview,
        preview_glass=preview_glass,
        router=router,
    )

"""Inspector routing for semantic Report Workspace locations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Generic, Optional, TypeVar

from PyQt6.QtWidgets import QWidget

from core.phases import normalize_phase_key
from core.reporting import ReportWorkspaceDocument, assess_report_readiness
from ui.report.appendix_inspector import ReportAppendixInspector
from ui.report.attack_path_inspector import ReportAttackPathInspector
from ui.report.finding_inspector import ReportFindingInspector
from ui.report.metadata_inspector import ReportMetadataInspector
from ui.report.navigation import ReportLocation, ReportLocationKind
from ui.report.readiness_inspector import ReportReadinessInspector
from ui.report.remediation_inspector import ReportRemediationInspector
from ui.report.scope_inspector import ReportScopeInspector
from ui.report.section_inspector import ReportSectionInspector
from ui.report.summary_inspector import ReportSummaryInspector

InspectorT = TypeVar("InspectorT", bound=QWidget)
PreviewTarget = tuple[str, str]


@dataclass(frozen=True)
class InspectorSurface(Generic[InspectorT]):
    inspector: InspectorT
    surface: QWidget


@dataclass(frozen=True)
class ReportWorkspaceSurfaces:
    metadata: InspectorSurface[ReportMetadataInspector]
    readiness: InspectorSurface[ReportReadinessInspector]
    finding: InspectorSurface[ReportFindingInspector]
    section: InspectorSurface[ReportSectionInspector]
    summary: InspectorSurface[ReportSummaryInspector]
    remediation: InspectorSurface[ReportRemediationInspector]
    attack_path: InspectorSurface[ReportAttackPathInspector]
    scope: InspectorSurface[ReportScopeInspector]
    appendix: InspectorSurface[ReportAppendixInspector]
    raw_markdown: QWidget


@dataclass(frozen=True)
class ReportRouteContext:
    target_ip: str
    project_dir: Optional[Path]
    loot_manager: object
    clipboard_history: object


@dataclass(frozen=True)
class ReportRoute:
    surface: Optional[QWidget]
    preview_target: Optional[PreviewTarget] = None
    structured: Optional[bool] = None


class ReportWorkspaceRouter:
    """Load the inspector associated with a semantic workspace destination."""

    _SECTION_ALIASES = {
        "summary": "executive_summary",
        "scope": "scope_limitations",
        "attack_narrative": "attack_path",
    }

    def __init__(self, surfaces: ReportWorkspaceSurfaces):
        self._surfaces = surfaces

    def route(
        self,
        location: ReportLocation,
        document: ReportWorkspaceDocument,
        context: ReportRouteContext,
    ) -> ReportRoute:
        kind = location.kind
        if kind is ReportLocationKind.METADATA:
            self._surfaces.metadata.inspector.load_metadata(document.metadata)
            return ReportRoute(
                self._surfaces.metadata.surface,
                ("section", "header_metadata"),
                structured=True,
            )
        if kind is ReportLocationKind.READINESS:
            self._surfaces.readiness.inspector.load_assessment(assess_report_readiness(document))
            return ReportRoute(self._surfaces.readiness.surface, structured=True)
        if kind is ReportLocationKind.FINDING:
            return self._route_finding(location.identity, document, context)
        if kind in (
            ReportLocationKind.FINDINGS_OVERVIEW,
            ReportLocationKind.PHASE_GROUP,
        ):
            return self._route_findings_overview(location, document, context)
        if kind in (ReportLocationKind.SECTION, ReportLocationKind.NARRATIVES_ROOT):
            return self._route_section(location.identity, document, context)
        if kind is ReportLocationKind.RAW_MARKDOWN:
            return ReportRoute(self._surfaces.raw_markdown, structured=False)
        return ReportRoute(None)

    def _route_finding(
        self,
        finding_id: Optional[str],
        document: ReportWorkspaceDocument,
        context: ReportRouteContext,
    ) -> ReportRoute:
        finding = document.get_finding(finding_id) if finding_id else None
        if finding is None:
            return ReportRoute(None)
        inspector = self._surfaces.finding.inspector
        inspector.set_project_target_ip(context.target_ip)
        inspector.load_finding(finding)
        return ReportRoute(
            self._surfaces.finding.surface,
            ("finding", finding.id),
            structured=True,
        )

    def _route_findings_overview(
        self,
        location: ReportLocation,
        document: ReportWorkspaceDocument,
        context: ReportRouteContext,
    ) -> ReportRoute:
        finding = None
        if location.kind is ReportLocationKind.PHASE_GROUP and location.identity:
            finding = next(
                (
                    candidate
                    for candidate in document.findings
                    if normalize_phase_key(candidate.phase) == location.identity
                ),
                None,
            )
        if finding is None and document.findings:
            finding = document.findings[0]

        inspector = self._surfaces.finding.inspector
        inspector.set_project_target_ip(context.target_ip)
        inspector.load_finding(finding)
        preview_target = (
            ("finding", finding.id) if finding is not None else ("section", "finding_section")
        )
        return ReportRoute(
            self._surfaces.finding.surface,
            preview_target,
            structured=True,
        )

    def _route_section(
        self,
        section_id: Optional[str],
        document: ReportWorkspaceDocument,
        context: ReportRouteContext,
    ) -> ReportRoute:
        identity = self._SECTION_ALIASES.get(
            section_id or "executive_summary",
            section_id or "executive_summary",
        )
        preview_target = ("section", identity)

        if identity == "executive_summary":
            self._surfaces.summary.inspector.load_summary(document)
            surface = self._surfaces.summary.surface
        elif identity == "remediation_table":
            self._surfaces.remediation.inspector.load_remediation(document)
            surface = self._surfaces.remediation.surface
        elif identity == "attack_path":
            self._surfaces.attack_path.inspector.load_attack_path(document)
            surface = self._surfaces.attack_path.surface
        elif identity == "scope_limitations":
            inspector = self._surfaces.scope.inspector
            inspector.set_project_target_ip(context.target_ip)
            inspector.load_scope(document)
            surface = self._surfaces.scope.surface
        elif identity == "appendix":
            inspector = self._surfaces.appendix.inspector
            inspector.set_context(
                loot_manager=context.loot_manager,
                clipboard_history=context.clipboard_history,
                project_dir=context.project_dir,
            )
            inspector.load_appendix(document)
            surface = self._surfaces.appendix.surface
        else:
            narrative = next(
                (
                    candidate
                    for candidate in document.narratives
                    if candidate.identity == identity or candidate.section_type == identity
                ),
                None,
            )
            title = narrative.title if narrative else identity
            content = narrative.content if narrative else ""
            section_icon = {
                "scope_limitations": "fa5s.bullseye",
                "attack_path": "fa5s.route",
                "appendix": "fa5s.paperclip",
            }.get(identity, "fa5s.edit")
            self._surfaces.section.inspector.load_section(
                identity,
                title,
                content,
                icon_name=section_icon,
            )
            surface = self._surfaces.section.surface

        return ReportRoute(surface, preview_target, structured=True)

"""Headless completion assessment for structured reports."""

from dataclasses import dataclass
from enum import Enum

from core.reporting.workspace_model import ReportWorkspaceDocument


class ReportReadinessLevel(str, Enum):
    BLOCKER = "blocker"
    REVIEW = "review"


@dataclass(frozen=True)
class ReportReadinessIssue:
    code: str
    level: ReportReadinessLevel
    target_kind: str
    target_id: str | None = None
    context: str = ""


@dataclass(frozen=True)
class ReportReadinessAssessment:
    issues: tuple[ReportReadinessIssue, ...]
    total_findings: int
    open_findings: int
    evidence_items: int

    @property
    def blockers(self) -> tuple[ReportReadinessIssue, ...]:
        return tuple(issue for issue in self.issues if issue.level is ReportReadinessLevel.BLOCKER)

    @property
    def review_items(self) -> tuple[ReportReadinessIssue, ...]:
        return tuple(issue for issue in self.issues if issue.level is ReportReadinessLevel.REVIEW)

    @property
    def status(self) -> str:
        if self.blockers:
            return "incomplete"
        if self.review_items:
            return "review"
        return "ready"


def assess_report_readiness(
    document: ReportWorkspaceDocument,
) -> ReportReadinessAssessment:
    issues: list[ReportReadinessIssue] = []
    required_metadata = (
        ("client", "metadata.client"),
        ("tester", "metadata.tester"),
        ("target_scope", "metadata.target_scope"),
        ("timeframe", "metadata.timeframe"),
    )
    for field_name, code in required_metadata:
        if not str(getattr(document.metadata, field_name, "") or "").strip():
            issues.append(
                ReportReadinessIssue(
                    code=code,
                    level=ReportReadinessLevel.BLOCKER,
                    target_kind="metadata",
                )
            )

    for finding in document.findings:
        context = finding.title.strip() or finding.id
        for field_name, code in (
            ("title", "finding.title"),
            ("description", "finding.description"),
            ("recommendation", "finding.recommendation"),
        ):
            if not str(getattr(finding, field_name, "") or "").strip():
                issues.append(
                    ReportReadinessIssue(
                        code=code,
                        level=ReportReadinessLevel.BLOCKER,
                        target_kind="finding",
                        target_id=finding.id,
                        context=context,
                    )
                )
        if not finding.evidence_items:
            issues.append(
                ReportReadinessIssue(
                    code="finding.evidence",
                    level=ReportReadinessLevel.REVIEW,
                    target_kind="finding",
                    target_id=finding.id,
                    context=context,
                )
            )

    summary = document.get_executive_summary()
    if not all(
        value.strip()
        for value in (
            summary.intro_text,
            summary.initial_access,
            summary.privilege_escalation,
            summary.business_impact,
            summary.remediation_summary,
        )
    ):
        issues.append(
            ReportReadinessIssue(
                code="summary.incomplete",
                level=ReportReadinessLevel.REVIEW,
                target_kind="section",
                target_id="executive_summary",
            )
        )

    return ReportReadinessAssessment(
        issues=tuple(issues),
        total_findings=len(document.findings),
        open_findings=sum(
            finding.status.lower() in {"open", "in_progress"} for finding in document.findings
        ),
        evidence_items=sum(len(finding.evidence_items) for finding in document.findings),
    )

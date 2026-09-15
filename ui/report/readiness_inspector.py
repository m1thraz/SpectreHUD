"""Integrated completion review for the Report Workspace."""

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.reporting import (
    ReportReadinessAssessment,
    ReportReadinessIssue,
    ReportReadinessLevel,
)
from ui.glass_panel import GlassPanel
from ui.report.inspector_style import (
    style_inspector_header,
    style_inspector_scroll,
    style_inspector_section,
)
from ui.report.navigation import ReportLocation
from ui.styles.icons import get_theme_color, icon


class ReportReadinessInspector(QWidget):
    navigate_requested = pyqtSignal(object)  # ReportLocation

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportReadinessInspector")
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        self.header_card = GlassPanel(self)
        header_layout = QHBoxLayout(self.header_card)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(8)

        header_icon = QLabel()
        header_icon.setPixmap(
            icon("fa5s.clipboard-check", color=get_theme_color("CYBER_CYAN")).pixmap(20, 20)
        )
        header_layout.addWidget(header_icon)

        self.lbl_title = QLabel(t("report.readiness_title", "Report Readiness"))
        style_inspector_header(self.header_card, self.lbl_title)
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()

        self.lbl_status = QLabel()
        self.lbl_status.setProperty("class", "ReportReadinessBadge")
        header_layout.addWidget(self.lbl_status)
        main_layout.addWidget(self.header_card)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget()
        style_inspector_scroll(scroll, content)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 8, 12, 12)
        content_layout.setSpacing(12)

        overview = GlassPanel(content)
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(12, 10, 12, 10)
        overview_layout.setSpacing(10)
        overview_title = QLabel(t("report.readiness_overview", "Completion Overview"))
        style_inspector_section(overview, overview_title)
        overview_layout.addWidget(overview_title)

        metrics = QGridLayout()
        metrics.setSpacing(8)
        self.lbl_findings = self._add_metric(metrics, 0, t("report.readiness_findings", "FINDINGS"))
        self.lbl_open = self._add_metric(
            metrics, 1, t("report.readiness_open", "OPEN / IN PROGRESS")
        )
        self.lbl_evidence = self._add_metric(metrics, 2, t("report.readiness_evidence", "EVIDENCE"))
        overview_layout.addLayout(metrics)

        self.lbl_summary = QLabel()
        self.lbl_summary.setProperty("class", "ReportInspectorHint")
        self.lbl_summary.setWordWrap(True)
        overview_layout.addWidget(self.lbl_summary)
        content_layout.addWidget(overview)

        self.blockers_card, self.blockers_layout = self._build_issue_section(
            content,
            t("report.readiness_blockers", "Must complete before handoff"),
        )
        content_layout.addWidget(self.blockers_card)

        self.review_card, self.review_layout = self._build_issue_section(
            content,
            t("report.readiness_review", "Review before export"),
        )
        content_layout.addWidget(self.review_card)
        content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll, stretch=1)

    @staticmethod
    def _add_metric(layout: QGridLayout, column: int, title: str) -> QLabel:
        card = QFrame()
        card.setProperty("class", "ReportMetricCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        label = QLabel(title)
        label.setProperty("class", "ReportMetricLabel")
        value = QLabel("0")
        value.setProperty("class", "ReportMetricValue")
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        layout.addWidget(card, 0, column)
        return value

    @staticmethod
    def _build_issue_section(parent: QWidget, title: str) -> tuple[QWidget, QVBoxLayout]:
        card = GlassPanel(parent)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)
        label = QLabel(title)
        style_inspector_section(card, label)
        layout.addWidget(label)
        return card, layout

    def load_assessment(self, assessment: ReportReadinessAssessment) -> None:
        self._clear_issue_rows(self.blockers_layout)
        self._clear_issue_rows(self.review_layout)

        self.lbl_findings.setText(str(assessment.total_findings))
        self.lbl_open.setText(str(assessment.open_findings))
        self.lbl_evidence.setText(str(assessment.evidence_items))
        status_text = {
            "incomplete": t("report.readiness_incomplete", "INCOMPLETE"),
            "review": t("report.readiness_needs_review", "REVIEW"),
            "ready": t("report.readiness_ready", "READY"),
        }[assessment.status]
        self.lbl_status.setText(status_text)
        self.lbl_status.setProperty("readinessState", assessment.status)
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)

        if assessment.status == "incomplete":
            summary = t(
                "report.readiness_summary_incomplete",
                "{count} required item(s) are missing. Export remains available, but the report is not ready for handoff.",
                count=len(assessment.blockers),
            )
        elif assessment.status == "review":
            summary = t(
                "report.readiness_summary_review",
                "Required content is complete. Review {count} advisory item(s) before export.",
                count=len(assessment.review_items),
            )
        else:
            summary = t(
                "report.readiness_summary_ready",
                "No incomplete or advisory report items were found.",
            )
        self.lbl_summary.setText(summary)

        self._populate_issues(self.blockers_layout, assessment.blockers)
        self._populate_issues(self.review_layout, assessment.review_items)

    @staticmethod
    def _clear_issue_rows(layout: QVBoxLayout) -> None:
        while layout.count() > 1:
            item = layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _populate_issues(
        self,
        layout: QVBoxLayout,
        issues: tuple[ReportReadinessIssue, ...],
    ) -> None:
        if not issues:
            empty = QLabel(t("report.readiness_none", "No open items."))
            empty.setProperty("class", "ReportInspectorHint")
            layout.addWidget(empty)
            return

        for issue in issues:
            button = QPushButton(self._issue_text(issue))
            button.setProperty("class", "ReadinessIssueBtn")
            button.setProperty("readinessLevel", issue.level.value)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(
                icon(
                    "fa5s.exclamation-circle"
                    if issue.level is ReportReadinessLevel.BLOCKER
                    else "fa5s.search",
                    color=get_theme_color(
                        "STATUS_ERROR"
                        if issue.level is ReportReadinessLevel.BLOCKER
                        else "STATUS_WARNING"
                    ),
                )
            )
            button.clicked.connect(
                lambda _checked=False, target=issue: self.navigate_requested.emit(
                    ReportLocation.from_legacy(target.target_kind, target.target_id)
                )
            )
            layout.addWidget(button)

    @staticmethod
    def _issue_text(issue: ReportReadinessIssue) -> str:
        labels = {
            "metadata.client": t(
                "report.readiness_issue_client", "Client / organization is missing"
            ),
            "metadata.tester": t("report.readiness_issue_tester", "Lead tester is missing"),
            "metadata.target_scope": t(
                "report.readiness_issue_target", "Target / scope is missing"
            ),
            "metadata.timeframe": t(
                "report.readiness_issue_timeframe", "Assessment period is missing"
            ),
            "finding.title": t("report.readiness_issue_finding_title", "Finding title is missing"),
            "finding.description": t(
                "report.readiness_issue_description", "Description is missing"
            ),
            "finding.recommendation": t(
                "report.readiness_issue_recommendation", "Recommendation is missing"
            ),
            "finding.evidence": t("report.readiness_issue_evidence", "No evidence is linked"),
            "summary.incomplete": t(
                "report.readiness_issue_summary",
                "Executive summary or key highlights are incomplete",
            ),
        }
        label = labels.get(issue.code, issue.code)
        return f"{label} · {issue.context}" if issue.context else label

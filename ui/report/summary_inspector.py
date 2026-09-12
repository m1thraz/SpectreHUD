"""
SpectreHUD Report Summary Inspector.

Provides an interactive executive dashboard for the Executive Summary section:
- High-level Posture & Severity Breakdown Scorecards
- Interactive Findings Matrix table with 1-click jump to finding
- Structured Management Summary (Intro) & Key Highlights form editor
"""

from typing import List, Optional

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.phases import get_phase
from core.reporting import (
    ReportExecutiveSummary,
    ReportFindingItem,
    ReportWorkspaceDocument,
)
from ui.glass_panel import GlassPanel
from ui.styles.icons import icon

SEV_COLORS = {
    "critical": "#f85149",
    "high": "#e3b341",
    "medium": "#d29922",
    "low": "#39d353",
    "info": "#58a6ff",
}

SEV_ICONS = {
    "critical": "fa5s.exclamation-circle",
    "high": "fa5s.exclamation-triangle",
    "medium": "fa5s.circle",
    "low": "fa5s.info-circle",
    "info": "fa5s.info-circle",
}

PHASE_LABELS_DE = {
    "recon": "Aufklärung & Enumeration",
    "access": "Initialer Zugriff",
    "privesc": "Rechteausweitung",
    "postex": "Post-Exploitation",
    "scripts": "Skripte & PoCs",
    "misc": "Sonstiges",
}


class ReportSummaryInspector(QWidget):
    """Interactive Executive Summary cockpit & editor."""

    summary_changed = pyqtSignal(ReportExecutiveSummary)
    finding_selected = pyqtSignal(str)  # Emits finding_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportSummaryInspector")
        self._summary = ReportExecutiveSummary()
        self._findings: List[ReportFindingItem] = []
        self._loading = False

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(250)
        self._debounce_timer.timeout.connect(self._emit_changed)

        self._build_ui()

    def minimumSizeHint(self) -> QSize:
        return QSize(260, 200)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "scorecards_panel"):
            self._reflow_scorecards(self.width())

    def _reflow_scorecards(self, width: int) -> None:
        if not hasattr(self, "sc_layout"):
            return
        self.sc_layout.removeWidget(self.card_posture)
        self.sc_layout.removeWidget(self.card_breakdown)
        self.sc_layout.removeWidget(self.card_status)
        if width >= 580:
            self.sc_layout.addWidget(self.card_posture, 0, 0, 1, 1)
            self.sc_layout.addWidget(self.card_breakdown, 0, 1, 1, 2)
            self.sc_layout.addWidget(self.card_status, 0, 3, 1, 1)
        elif width >= 400:
            self.sc_layout.addWidget(self.card_posture, 0, 0, 1, 1)
            self.sc_layout.addWidget(self.card_status, 0, 1, 1, 1)
            self.sc_layout.addWidget(self.card_breakdown, 1, 0, 1, 2)
        else:
            self.sc_layout.addWidget(self.card_posture, 0, 0, 1, 1)
            self.sc_layout.addWidget(self.card_breakdown, 1, 0, 1, 1)
            self.sc_layout.addWidget(self.card_status, 2, 0, 1, 1)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Header card
        self.header_card = GlassPanel(self)
        h_layout = QHBoxLayout(self.header_card)
        h_layout.setContentsMargins(12, 10, 12, 10)
        h_layout.setSpacing(8)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(icon("fa5s.chart-pie", color="#00e5ff").pixmap(20, 20))
        h_layout.addWidget(lbl_icon)

        self.lbl_title = QLabel(t("report.inspector_summary_title", "Executive Summary & Management Overview"))
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f0f6fc;")
        h_layout.addWidget(self.lbl_title)
        h_layout.addStretch()

        self.lbl_posture_badge = QLabel()
        self.lbl_posture_badge.setStyleSheet(
            "font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; "
            "background: rgba(248, 81, 73, 0.2); color: #f85149; border: 1px solid rgba(248, 81, 73, 0.4);"
        )
        h_layout.addWidget(self.lbl_posture_badge)

        main_layout.addWidget(self.header_card)

        # 2. Scrollable Body
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(12, 8, 12, 12)
        self.content_layout.setSpacing(12)

        # Scorecards Row
        self.scorecards_panel = GlassPanel(content_widget)
        self.sc_layout = QGridLayout(self.scorecards_panel)
        self.sc_layout.setContentsMargins(12, 10, 12, 10)
        self.sc_layout.setSpacing(10)

        # Card A: Overall Posture
        self.card_posture = QFrame()
        self.card_posture.setStyleSheet("background: rgba(22, 27, 34, 0.7); border: 1px solid #30363d; border-radius: 6px; padding: 6px;")
        v_posture = QVBoxLayout(self.card_posture)
        v_posture.setContentsMargins(6, 6, 6, 6)
        lbl_posture_title = QLabel(t("report.summary_posture_label", "OVERALL POSTURE"))
        lbl_posture_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #8b949e;")
        self.lbl_posture_val = QLabel("NO FINDINGS")
        self.lbl_posture_val.setStyleSheet("font-size: 14px; font-weight: bold; color: #58a6ff;")
        v_posture.addWidget(lbl_posture_title)
        v_posture.addWidget(self.lbl_posture_val)

        # Card B: Severity Breakdown
        self.card_breakdown = QFrame()
        self.card_breakdown.setStyleSheet("background: rgba(22, 27, 34, 0.7); border: 1px solid #30363d; border-radius: 6px; padding: 6px;")
        v_breakdown = QVBoxLayout(self.card_breakdown)
        v_breakdown.setContentsMargins(6, 6, 6, 6)
        lbl_breakdown_title = QLabel(t("report.summary_breakdown_label", "SEVERITY BREAKDOWN"))
        lbl_breakdown_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #8b949e;")
        v_breakdown.addWidget(lbl_breakdown_title)

        self.pills_row = QHBoxLayout()
        self.pills_row.setSpacing(6)
        self.pill_crit = self._create_pill_label("CRITICAL", "#f85149")
        self.pill_high = self._create_pill_label("HIGH", "#e3b341")
        self.pill_med = self._create_pill_label("MEDIUM", "#d29922")
        self.pill_low = self._create_pill_label("LOW", "#39d353")
        self.pill_info = self._create_pill_label("INFO", "#58a6ff")
        self.pills_row.addWidget(self.pill_crit)
        self.pills_row.addWidget(self.pill_high)
        self.pills_row.addWidget(self.pill_med)
        self.pills_row.addWidget(self.pill_low)
        self.pills_row.addWidget(self.pill_info)
        v_breakdown.addLayout(self.pills_row)

        # Card C: Findings Status
        self.card_status = QFrame()
        self.card_status.setStyleSheet("background: rgba(22, 27, 34, 0.7); border: 1px solid #30363d; border-radius: 6px; padding: 6px;")
        v_status = QVBoxLayout(self.card_status)
        v_status.setContentsMargins(6, 6, 6, 6)
        lbl_status_title = QLabel(t("report.summary_status_label", "FINDINGS STATUS"))
        lbl_status_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #8b949e;")
        self.lbl_status_val = QLabel("0 Total · 0 Open · 0 Resolved")
        self.lbl_status_val.setStyleSheet("font-size: 12px; font-weight: bold; color: #c9d1d9;")
        v_status.addWidget(lbl_status_title)
        v_status.addWidget(self.lbl_status_val)

        # Place initial cards in grid
        self._reflow_scorecards(600)

        self.content_layout.addWidget(self.scorecards_panel)

        # 3. Management Summary (Intro text)
        intro_card = GlassPanel(content_widget)
        intro_layout = QVBoxLayout(intro_card)
        intro_layout.setContentsMargins(12, 10, 12, 10)
        intro_layout.setSpacing(6)

        lbl_intro_header = QLabel(t("report.summary_intro_title", "Management Summary / Executive Narrative"))
        lbl_intro_header.setStyleSheet("font-size: 12px; font-weight: bold; color: #f0f6fc;")
        intro_layout.addWidget(lbl_intro_header)

        self.txt_intro = QPlainTextEdit()
        self.txt_intro.setPlaceholderText(
            t("report.summary_intro_placeholder", "High-level summary of the assessment, key results, and general risk posture for management...")
        )
        self.txt_intro.setMaximumHeight(90)
        self.txt_intro.textChanged.connect(self._on_field_changed)
        intro_layout.addWidget(self.txt_intro)

        self.content_layout.addWidget(intro_card)

        # 4. Findings Matrix Table
        matrix_card = GlassPanel(content_widget)
        matrix_layout = QVBoxLayout(matrix_card)
        matrix_layout.setContentsMargins(12, 10, 12, 10)
        matrix_layout.setSpacing(6)

        matrix_hdr = QHBoxLayout()
        lbl_matrix_title = QLabel(t("report.summary_matrix_title", "Findings Matrix (Overview)"))
        lbl_matrix_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #f0f6fc;")
        matrix_hdr.addWidget(lbl_matrix_title)
        matrix_hdr.addStretch()

        lbl_matrix_hint = QLabel(t("report.summary_matrix_hint", "Double-click or click [>] to inspect finding"))
        lbl_matrix_hint.setStyleSheet("font-size: 11px; color: #8b949e;")
        matrix_hdr.addWidget(lbl_matrix_hint)
        matrix_layout.addLayout(matrix_hdr)

        self.tbl_matrix = QTableWidget()
        self.tbl_matrix.setColumnCount(6)
        self.tbl_matrix.setHorizontalHeaderLabels([
            "#",
            t("report.col_severity", "Severity"),
            t("report.col_finding", "Finding"),
            t("report.col_phase", "Phase"),
            t("report.col_status", "Status"),
            t("report.col_action", "Action"),
        ])
        self.tbl_matrix.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_matrix.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_matrix.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_matrix.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_matrix.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_matrix.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_matrix.verticalHeader().setVisible(False)
        self.tbl_matrix.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_matrix.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tbl_matrix.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_matrix.setMinimumHeight(160)
        self.tbl_matrix.setMaximumHeight(260)
        self.tbl_matrix.setMinimumWidth(0)
        self.tbl_matrix.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tbl_matrix.cellDoubleClicked.connect(self._on_table_double_clicked)
        self.tbl_matrix.setStyleSheet(
            """
            QTableWidget {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 4px;
                gridline-color: #21262d;
                color: #c9d1d9;
            }
            QHeaderView::section {
                background: #0d1117;
                color: #8b949e;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #21262d;
                padding: 4px;
            }
            QTableWidget::item:hover {
                background: rgba(0, 229, 255, 0.08);
            }
            QTableWidget::item:selected {
                background: rgba(0, 229, 255, 0.18);
                color: #f0f6fc;
            }
            """
        )
        matrix_layout.addWidget(self.tbl_matrix)

        self.content_layout.addWidget(matrix_card)

        # 5. Key Highlights / Kernaussagen Form
        highlights_card = GlassPanel(content_widget)
        hl_layout = QVBoxLayout(highlights_card)
        hl_layout.setContentsMargins(12, 10, 12, 10)
        hl_layout.setSpacing(8)

        lbl_hl_header = QLabel(t("report.summary_highlights_title", "Key Assessment Highlights & Vectors"))
        lbl_hl_header.setStyleSheet("font-size: 12px; font-weight: bold; color: #f0f6fc;")
        hl_layout.addWidget(lbl_hl_header)

        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        self.txt_initial_access = QPlainTextEdit()
        self.txt_initial_access.setPlaceholderText(
            t("report.summary_initial_access_placeholder", "e.g. Exposed anonymous FTP service, unauthenticated upload...")
        )
        self.txt_initial_access.setMaximumHeight(50)
        self.txt_initial_access.textChanged.connect(self._on_field_changed)
        form.addRow(self._make_label(t("report.summary_initial_access", "Initial Access:")), self.txt_initial_access)

        self.txt_privesc = QPlainTextEdit()
        self.txt_privesc.setPlaceholderText(
            t("report.summary_privesc_placeholder", "e.g. Sudo NOPASSWD /usr/bin/less, unquoted service path...")
        )
        self.txt_privesc.setMaximumHeight(50)
        self.txt_privesc.textChanged.connect(self._on_field_changed)
        form.addRow(self._make_label(t("report.summary_privesc", "Privilege Escalation:")), self.txt_privesc)

        self.txt_business_impact = QPlainTextEdit()
        self.txt_business_impact.setPlaceholderText(
            t("report.summary_business_impact_placeholder", "e.g. Complete takeover of infrastructure, domain controller compromise...")
        )
        self.txt_business_impact.setMaximumHeight(50)
        self.txt_business_impact.textChanged.connect(self._on_field_changed)
        form.addRow(self._make_label(t("report.summary_business_impact", "Business Impact & Risk:")), self.txt_business_impact)

        self.txt_remediation = QPlainTextEdit()
        self.txt_remediation.setPlaceholderText(
            t("report.summary_remediation_placeholder", "e.g. Disable anonymous FTP, remove sudo NOPASSWD rules, enforce least-privilege...")
        )
        self.txt_remediation.setMaximumHeight(50)
        self.txt_remediation.textChanged.connect(self._on_field_changed)
        form.addRow(self._make_label(t("report.summary_remediation", "Key Recommendations:")), self.txt_remediation)

        hl_layout.addLayout(form)
        self.content_layout.addWidget(highlights_card)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, stretch=1)

    def _create_pill_label(self, name: str, color: str) -> QLabel:
        lbl = QLabel(f"{name}: 0")
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 3px; "
            f"background: rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.15); "
            f"color: {color}; border: 1px solid rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.35);"
        )
        return lbl

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #8b949e;")
        return lbl

    def load_summary(self, doc: ReportWorkspaceDocument) -> None:
        """Loads both the structured executive summary metadata and the findings matrix."""
        self._loading = True
        try:
            self._findings = list(doc.findings)
            self._summary = doc.get_executive_summary()

            # 1. Update text fields
            self.lbl_title.setText(self._summary.title or t("report.inspector_summary_title", "Executive Summary & Management Overview"))
            self.txt_intro.setPlainText(self._summary.intro_text)
            self.txt_initial_access.setPlainText(self._summary.initial_access)
            self.txt_privesc.setPlainText(self._summary.privilege_escalation)
            self.txt_business_impact.setPlainText(self._summary.business_impact)
            self.txt_remediation.setPlainText(self._summary.remediation_summary)

            # 2. Update KPI Scorecards
            self._refresh_scorecards(self._findings)

            # 3. Update Matrix Table
            self._refresh_matrix_table(self._findings, doc.language)
        finally:
            self._loading = False

    def _refresh_scorecards(self, findings: List[ReportFindingItem]) -> None:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        open_count = 0
        resolved_count = 0

        for f in findings:
            sev = (f.severity or "info").lower()
            if sev in counts:
                counts[sev] += 1
            else:
                counts["info"] += 1

            status_val = (f.status or "").strip().lower()
            if status_val in ("resolved", "closed", "behoben"):
                resolved_count += 1
            else:
                open_count += 1

        self.pill_crit.setText(f"CRIT: {counts['critical']}")
        self.pill_high.setText(f"HIGH: {counts['high']}")
        self.pill_med.setText(f"MED: {counts['medium']}")
        self.pill_low.setText(f"LOW: {counts['low']}")
        self.pill_info.setText(f"INFO: {counts['info']}")

        # Overall Posture
        if counts["critical"] > 0:
            posture_text = "CRITICAL RISK"
            posture_color = "#f85149"
        elif counts["high"] > 0:
            posture_text = "HIGH RISK"
            posture_color = "#e3b341"
        elif counts["medium"] > 0:
            posture_text = "MEDIUM RISK"
            posture_color = "#d29922"
        elif counts["low"] > 0:
            posture_text = "LOW RISK"
            posture_color = "#39d353"
        elif counts["info"] > 0:
            posture_text = "INFORMATIONAL"
            posture_color = "#58a6ff"
        else:
            posture_text = "NO FINDINGS"
            posture_color = "#8b949e"

        self.lbl_posture_val.setText(posture_text)
        self.lbl_posture_val.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {posture_color};")
        self.lbl_posture_badge.setText(posture_text)
        self.lbl_posture_badge.setStyleSheet(
            f"font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; "
            f"background: rgba({int(posture_color[1:3], 16)}, {int(posture_color[3:5], 16)}, {int(posture_color[5:7], 16)}, 0.18); "
            f"color: {posture_color}; border: 1px solid rgba({int(posture_color[1:3], 16)}, {int(posture_color[3:5], 16)}, {int(posture_color[5:7], 16)}, 0.4);"
        )

        total_findings = len(findings)
        self.lbl_status_val.setText(
            f"{total_findings} {t('report.status_total', 'Total')} · {open_count} {t('report.status_open', 'Open')} · {resolved_count} {t('report.status_resolved', 'Resolved')}"
        )

    def _refresh_matrix_table(self, findings: List[ReportFindingItem], language: str = "de") -> None:
        self.tbl_matrix.setRowCount(len(findings))

        for row, f in enumerate(findings):
            # Col 0: Index
            it_idx = QTableWidgetItem(str(row + 1))
            it_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_idx.setData(Qt.ItemDataRole.UserRole, f.id)
            self.tbl_matrix.setItem(row, 0, it_idx)

            # Col 1: Severity badge
            sev = (f.severity or "medium").lower()
            it_sev = QTableWidgetItem(sev.upper())
            it_sev.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_sev.setIcon(icon(SEV_ICONS.get(sev, "fa5s.circle"), color=SEV_COLORS.get(sev, "#d29922")))
            it_sev.setForeground(Qt.GlobalColor.white)
            self.tbl_matrix.setItem(row, 1, it_sev)

            # Col 2: Title
            it_title = QTableWidgetItem(f.title or t("report.finding_unnamed", "Untitled Finding"))
            it_title.setToolTip(f.description[:200] if f.description else "")
            self.tbl_matrix.setItem(row, 2, it_title)

            # Col 3: Phase
            p_obj = get_phase(f.phase)
            ph_name = PHASE_LABELS_DE.get(p_obj.key, p_obj.short) if language == "de" else p_obj.short
            it_phase = QTableWidgetItem(ph_name)
            it_phase.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_matrix.setItem(row, 3, it_phase)

            # Col 4: Status
            status_text = "Offen" if f.status == "open" else ("Behoben" if f.status in ("resolved", "closed") else f.status.capitalize())
            if language != "de":
                status_text = f.status.capitalize()
            it_status = QTableWidgetItem(status_text)
            it_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_matrix.setItem(row, 4, it_status)

            # Col 5: Action button
            btn_jump = QPushButton()
            btn_jump.setIcon(icon("fa5s.arrow-right", color="#00e5ff"))
            btn_jump.setToolTip(t("report.jump_to_finding_tip", "Inspect this finding"))
            btn_jump.setStyleSheet(
                "QPushButton { background: rgba(0, 229, 255, 0.1); border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 3px; padding: 2px 6px; } "
                "QPushButton:hover { background: rgba(0, 229, 255, 0.25); }"
            )
            fid = f.id
            btn_jump.clicked.connect(lambda checked=False, target_id=fid: self.finding_selected.emit(target_id))
            self.tbl_matrix.setCellWidget(row, 5, btn_jump)

    def _on_table_double_clicked(self, row: int, _col: int) -> None:
        it = self.tbl_matrix.item(row, 0)
        if it:
            fid = it.data(Qt.ItemDataRole.UserRole)
            if fid:
                self.finding_selected.emit(fid)

    def _on_field_changed(self) -> None:
        if self._loading:
            return
        self._debounce_timer.start()

    def _emit_changed(self) -> None:
        self._summary.intro_text = self.txt_intro.toPlainText().strip()
        self._summary.initial_access = self.txt_initial_access.toPlainText().strip()
        self._summary.privilege_escalation = self.txt_privesc.toPlainText().strip()
        self._summary.business_impact = self.txt_business_impact.toPlainText().strip()
        self._summary.remediation_summary = self.txt_remediation.toPlainText().strip()
        self.summary_changed.emit(self._summary)

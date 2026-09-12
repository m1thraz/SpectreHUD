"""
Interactive Remediation & Action Plan Inspector for SpectreHUD Report Workspace.
Provides strategic hardening guidance, in-place action editing, and status workflow management.
"""

from typing import List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
    ReportFindingItem,
    ReportRemediationPlan,
    ReportWorkspaceDocument,
)
from ui.glass_panel import GlassPanel
from ui.styles.icons import icon

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}

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

STATUS_ITEMS = [
    ("open", "Offen / Open", "#f85149"),
    ("in_progress", "In Arbeit / In Progress", "#d29922"),
    ("resolved", "Behoben / Resolved", "#39d353"),
    ("accepted_risk", "Akzeptiert / Accepted Risk", "#8b949e"),
]


class ReportRemediationInspector(QWidget):
    """Interactive Remediation & Action Plan inspector and management cockpit."""

    plan_changed = pyqtSignal(ReportRemediationPlan)
    finding_action_changed = pyqtSignal(str, str, str)  # finding_id, recommendation, status
    finding_selected = pyqtSignal(str)  # finding_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportRemediationInspector")
        self._plan = ReportRemediationPlan()
        self._findings: List[ReportFindingItem] = []
        self._language = "de"
        self._loading = False
        self._active_filter = "all"  # "all", "open", "resolved"

        self._guidance_timer = QTimer(self)
        self._guidance_timer.setSingleShot(True)
        self._guidance_timer.setInterval(300)
        self._guidance_timer.timeout.connect(self._emit_plan_changed)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Header Card
        self.header_card = GlassPanel(self)
        h_layout = QHBoxLayout(self.header_card)
        h_layout.setContentsMargins(12, 10, 12, 10)
        h_layout.setSpacing(8)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(icon("fa5s.tasks", color="#00e5ff").pixmap(20, 20))
        h_layout.addWidget(lbl_icon)

        self.lbl_title = QLabel(t("report.inspector_remediation_title", "Remediation & Action Plan"))
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f0f6fc;")
        h_layout.addWidget(self.lbl_title)
        h_layout.addStretch()

        self.lbl_progress_badge = QLabel()
        self.lbl_progress_badge.setStyleSheet(
            "font-size: 11px; font-weight: bold; padding: 3px 10px; border-radius: 4px; "
            "background: rgba(57, 211, 83, 0.15); color: #39d353; border: 1px solid rgba(57, 211, 83, 0.35);"
        )
        h_layout.addWidget(self.lbl_progress_badge)

        main_layout.addWidget(self.header_card)

        # 2. Scroll Area Body
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(12, 8, 12, 12)
        self.content_layout.setSpacing(10)

        # Strategic Guidance Card
        guidance_card = GlassPanel(content_widget)
        g_layout = QVBoxLayout(guidance_card)
        g_layout.setContentsMargins(12, 10, 12, 10)
        g_layout.setSpacing(6)

        lbl_g_header = QLabel(t("report.remediation_guidance_title", "Strategic Guidance & Hardening Roadmap"))
        lbl_g_header.setStyleSheet("font-size: 12px; font-weight: bold; color: #f0f6fc;")
        g_layout.addWidget(lbl_g_header)

        self.txt_guidance = QPlainTextEdit()
        self.txt_guidance.setPlaceholderText(
            t(
                "report.remediation_guidance_placeholder",
                "High-level remediation guidance, strategic principles (e.g. least privilege, patch cycle, network segregation)...",
            )
        )
        self.txt_guidance.setMaximumHeight(80)
        self.txt_guidance.textChanged.connect(self._on_guidance_changed)
        g_layout.addWidget(self.txt_guidance)

        self.content_layout.addWidget(guidance_card)

        # Remediation Matrix Card
        matrix_card = GlassPanel(content_widget)
        matrix_layout = QVBoxLayout(matrix_card)
        matrix_layout.setContentsMargins(12, 10, 12, 10)
        matrix_layout.setSpacing(8)

        # Toolbar above table: Title + Filter Toggle Buttons
        tbl_top_bar = QHBoxLayout()
        lbl_matrix_title = QLabel(t("report.remediation_matrix_title", "Remediation & Action Matrix"))
        lbl_matrix_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #f0f6fc;")
        tbl_top_bar.addWidget(lbl_matrix_title)
        tbl_top_bar.addStretch()

        self.btn_filter_group = QButtonGroup(self)
        self.btn_filter_group.setExclusive(True)

        self.btn_filter_all = QPushButton(t("report.filter_all", "All"))
        self.btn_filter_all.setCheckable(True)
        self.btn_filter_all.setChecked(True)
        self._style_filter_btn(self.btn_filter_all)
        self.btn_filter_group.addButton(self.btn_filter_all)
        tbl_top_bar.addWidget(self.btn_filter_all)

        self.btn_filter_open = QPushButton(t("report.filter_open", "Open"))
        self.btn_filter_open.setCheckable(True)
        self._style_filter_btn(self.btn_filter_open)
        self.btn_filter_group.addButton(self.btn_filter_open)
        tbl_top_bar.addWidget(self.btn_filter_open)

        self.btn_filter_resolved = QPushButton(t("report.filter_resolved", "Remediated"))
        self.btn_filter_resolved.setCheckable(True)
        self._style_filter_btn(self.btn_filter_resolved)
        self.btn_filter_group.addButton(self.btn_filter_resolved)
        tbl_top_bar.addWidget(self.btn_filter_resolved)

        self.btn_filter_all.clicked.connect(lambda: self._set_filter("all"))
        self.btn_filter_open.clicked.connect(lambda: self._set_filter("open"))
        self.btn_filter_resolved.clicked.connect(lambda: self._set_filter("resolved"))

        matrix_layout.addLayout(tbl_top_bar)

        # Table Widget
        self.tbl_actions = QTableWidget()
        self.tbl_actions.setColumnCount(5)
        self.tbl_actions.setHorizontalHeaderLabels([
            t("report.col_priority", "Priority"),
            t("report.col_vulnerability", "Vulnerability"),
            t("report.col_recommended_action", "Recommended Action"),
            t("report.col_status", "Status"),
            t("report.col_action", "Action"),
        ])
        self.tbl_actions.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_actions.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_actions.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_actions.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_actions.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_actions.verticalHeader().setVisible(False)
        self.tbl_actions.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_actions.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tbl_actions.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_actions.setMinimumHeight(240)
        self.tbl_actions.cellDoubleClicked.connect(self._on_table_double_clicked)
        self.tbl_actions.setStyleSheet(
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
                padding: 5px;
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
        matrix_layout.addWidget(self.tbl_actions)

        self.content_layout.addWidget(matrix_card)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, stretch=1)

    def _style_filter_btn(self, btn: QPushButton) -> None:
        btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(22, 27, 34, 0.8);
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #21262d;
                color: #c9d1d9;
            }
            QPushButton:checked {
                background: rgba(0, 229, 255, 0.15);
                color: #00e5ff;
                border-color: rgba(0, 229, 255, 0.4);
                font-weight: bold;
            }
            """
        )

    def load_remediation(self, doc: ReportWorkspaceDocument) -> None:
        """Loads both the strategic guidance and the findings action matrix."""
        self._loading = True
        try:
            self._findings = list(doc.findings)
            self._plan = doc.get_remediation_plan()
            self._language = doc.language

            self.lbl_title.setText(self._plan.title or t("report.inspector_remediation_title", "Remediation & Action Plan"))
            self.txt_guidance.setPlainText(self._plan.strategic_guidance)

            self._refresh_table()
            self._refresh_progress()
        finally:
            self._loading = False

    def _set_filter(self, filter_mode: str) -> None:
        self._active_filter = filter_mode
        self._refresh_table()

    def _refresh_progress(self) -> None:
        total = len(self._findings)
        resolved = sum(1 for f in self._findings if (f.status or "").strip().lower() in ("resolved", "closed", "behoben"))
        pct = int((resolved / total) * 100) if total > 0 else 0
        self.lbl_progress_badge.setText(f"Remediation: {resolved} / {total} Resolved ({pct}%)")

    def _refresh_table(self) -> None:
        # Sort findings: Critical -> High -> Medium -> Low -> Info
        sorted_findings = sorted(
            self._findings,
            key=lambda f: SEVERITY_ORDER.get((f.severity or "medium").strip().lower(), 99),
        )

        # Filter
        visible_findings: List[ReportFindingItem] = []
        for f in sorted_findings:
            is_res = (f.status or "").strip().lower() in ("resolved", "closed", "behoben")
            if self._active_filter == "open" and is_res:
                continue
            if self._active_filter == "resolved" and not is_res:
                continue
            visible_findings.append(f)

        self.tbl_actions.setRowCount(len(visible_findings))

        for row, f in enumerate(visible_findings):
            fid = f.id

            # Col 0: Priority Badge
            sev = (f.severity or "medium").strip().lower()
            it_sev = QTableWidgetItem(sev.upper())
            it_sev.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_sev.setIcon(icon(SEV_ICONS.get(sev, "fa5s.circle"), color=SEV_COLORS.get(sev, "#d29922")))
            it_sev.setData(Qt.ItemDataRole.UserRole, fid)
            it_sev.setForeground(Qt.GlobalColor.white)
            self.tbl_actions.setItem(row, 0, it_sev)

            # Col 1: Vulnerability Title & Phase
            p_obj = get_phase(f.phase)
            title_text = f.title or t("report.finding_unnamed", "Untitled Finding")
            it_vuln = QTableWidgetItem(f"{title_text}  ({p_obj.short})")
            it_vuln.setToolTip(f"{title_text}\nPhase: {p_obj.long}")
            self.tbl_actions.setItem(row, 1, it_vuln)

            # Col 2: Recommended Action (In-place editable LineEdit)
            edit_action = QLineEdit()
            edit_action.setText(f.recommendation or "")
            edit_action.setPlaceholderText(t("report.recommendation_placeholder", "Define concrete remediation steps..."))
            edit_action.setStyleSheet(
                "QLineEdit { background: #0d1117; border: 1px solid #30363d; border-radius: 3px; color: #c9d1d9; padding: 3px 6px; } "
                "QLineEdit:focus { border-color: #00e5ff; }"
            )
            edit_action.editingFinished.connect(
                lambda target_id=fid, edit_w=edit_action: self._on_action_text_changed(target_id, edit_w.text())
            )
            self.tbl_actions.setCellWidget(row, 2, edit_action)

            # Col 3: Status Combo
            cmb_status = QComboBox()
            cmb_status.setStyleSheet(
                "QComboBox { background: #0d1117; border: 1px solid #30363d; border-radius: 3px; color: #c9d1d9; padding: 2px 6px; } "
                "QComboBox:focus { border-color: #00e5ff; }"
            )
            current_status = (f.status or "open").strip().lower()
            current_idx = 0
            for idx, (st_val, st_lbl, _st_col) in enumerate(STATUS_ITEMS):
                cmb_status.addItem(st_lbl, st_val)
                if current_status == st_val or (current_status in ("closed", "behoben") and st_val == "resolved"):
                    current_idx = idx

            cmb_status.setCurrentIndex(current_idx)
            cmb_status.currentIndexChanged.connect(
                lambda idx, target_id=fid, cmb=cmb_status: self._on_status_changed(target_id, cmb.currentData())
            )
            self.tbl_actions.setCellWidget(row, 3, cmb_status)

            # Col 4: Jump button [>]
            btn_jump = QPushButton()
            btn_jump.setIcon(icon("fa5s.arrow-right", color="#00e5ff"))
            btn_jump.setToolTip(t("report.jump_to_finding_tip", "Inspect finding details"))
            btn_jump.setStyleSheet(
                "QPushButton { background: rgba(0, 229, 255, 0.1); border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 3px; padding: 2px 6px; } "
                "QPushButton:hover { background: rgba(0, 229, 255, 0.25); }"
            )
            btn_jump.clicked.connect(lambda checked=False, target_id=fid: self.finding_selected.emit(target_id))
            self.tbl_actions.setCellWidget(row, 4, btn_jump)

    def _on_action_text_changed(self, finding_id: str, new_text: str) -> None:
        if self._loading:
            return
        target = next((f for f in self._findings if f.id == finding_id), None)
        if target and target.recommendation != new_text:
            target.recommendation = new_text
            self.finding_action_changed.emit(finding_id, target.recommendation, target.status)

    def _on_status_changed(self, finding_id: str, new_status: str) -> None:
        if self._loading:
            return
        target = next((f for f in self._findings if f.id == finding_id), None)
        if target and target.status != new_status:
            target.status = new_status
            self._refresh_progress()
            self.finding_action_changed.emit(finding_id, target.recommendation, target.status)

    def _on_table_double_clicked(self, row: int, _col: int) -> None:
        it = self.tbl_actions.item(row, 0)
        if it:
            fid = it.data(Qt.ItemDataRole.UserRole)
            if fid:
                self.finding_selected.emit(fid)

    def _on_guidance_changed(self) -> None:
        if self._loading:
            return
        self._guidance_timer.start()

    def _emit_plan_changed(self) -> None:
        self._plan.strategic_guidance = self.txt_guidance.toPlainText().strip()
        self.plan_changed.emit(self._plan)

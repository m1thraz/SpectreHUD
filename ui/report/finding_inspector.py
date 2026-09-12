"""
SpectreHUD Report Finding Inspector.

Provides a dedicated finding editor with severity selection, phase categorization,
markdown description/recommendation editing, and target scoping.
"""

from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.reporting import ReportFindingItem
from ui.glass_panel import GlassPanel
from ui.styles.icons import icon

SEVERITIES = ["critical", "high", "medium", "low", "info"]
PHASES = ["recon", "access", "privesc", "postex", "scripts", "misc"]
STATUSES = [
    ("open", "Offen / Open"),
    ("in_progress", "In Arbeit / In Progress"),
    ("resolved", "Behoben / Resolved"),
    ("accepted_risk", "Akzeptiert / Accepted Risk"),
]


class ReportFindingInspector(QWidget):
    """Contextual form and markdown editor for a single finding."""

    finding_changed = pyqtSignal(ReportFindingItem)
    finding_deleted = pyqtSignal(str)
    finding_duplicated = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportFindingInspector")
        self._finding: Optional[ReportFindingItem] = None
        self._loading = False

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(250)
        self._debounce_timer.timeout.connect(self._emit_changed)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Header card
        header_card = GlassPanel(self)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(12, 8, 12, 8)
        h_layout.setSpacing(8)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(icon("fa5s.shield-alt", color="#00e5ff").pixmap(20, 20))
        h_layout.addWidget(lbl_icon)

        self.lbl_header_title = QLabel(t("report.inspector_finding_title", "Finding Details"))
        self.lbl_header_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f0f6fc;")
        h_layout.addWidget(self.lbl_header_title)
        h_layout.addStretch()

        self.btn_duplicate = QPushButton()
        self.btn_duplicate.setObjectName("btn_duplicate_finding")
        self.btn_duplicate.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_duplicate.setToolTip(t("report.duplicate_finding", "Finding duplizieren"))
        self.btn_duplicate.setIcon(icon("fa5s.copy", color="#79c0ff"))
        self.btn_duplicate.clicked.connect(self._on_duplicate_clicked)
        h_layout.addWidget(self.btn_duplicate)

        self.btn_delete = QPushButton()
        self.btn_delete.setObjectName("btn_delete_finding")
        self.btn_delete.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_delete.setToolTip(t("report.delete_finding", "Finding löschen"))
        self.btn_delete.setIcon(icon("fa5s.trash-alt", color="#f85149"))
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        h_layout.addWidget(self.btn_delete)

        main_layout.addWidget(header_card)

        # Form Scroll Area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content_widget = QWidget()
        v_content = QVBoxLayout(content_widget)
        v_content.setContentsMargins(12, 8, 12, 12)
        v_content.setSpacing(12)

        # Meta form
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("z.B. Remote Code Execution via Deserialization")
        self.txt_title.textChanged.connect(self._on_field_changed)
        form.addRow(self._make_label(t("report.finding_title", "Titel:")), self.txt_title)

        # Severity & Status in one row
        sev_row = QHBoxLayout()
        self.cmb_severity = QComboBox()
        for s in SEVERITIES:
            self.cmb_severity.addItem(s.upper(), s)
        self.cmb_severity.currentIndexChanged.connect(self._on_field_changed)
        sev_row.addWidget(self.cmb_severity)

        sev_row.addWidget(self._make_label(t("report.finding_status", "Status:")))
        self.cmb_status = QComboBox()
        for s_code, s_label in STATUSES:
            self.cmb_status.addItem(s_label, s_code)
        self.cmb_status.currentIndexChanged.connect(self._on_field_changed)
        sev_row.addWidget(self.cmb_status)
        form.addRow(self._make_label(t("report.finding_severity", "Severity:")), sev_row)

        # Phase & Target
        phase_row = QHBoxLayout()
        self.cmb_phase = QComboBox()
        for p in PHASES:
            self.cmb_phase.addItem(p.capitalize(), p)
        self.cmb_phase.currentIndexChanged.connect(self._on_field_changed)
        phase_row.addWidget(self.cmb_phase)

        phase_row.addWidget(self._make_label(t("report.finding_target", "Target:")))
        self.txt_target = QLineEdit()
        self.txt_target.setPlaceholderText("z.B. 10.10.10.5 oder /api/v1/auth")
        self.txt_target.textChanged.connect(self._on_field_changed)
        phase_row.addWidget(self.txt_target)
        form.addRow(self._make_label(t("report.finding_phase", "Phase:")), phase_row)

        v_content.addLayout(form)

        # Description text
        v_content.addWidget(self._make_section_header(t("report.finding_desc", "Beschreibung & Proof of Concept")))
        self.txt_desc = QPlainTextEdit()
        self.txt_desc.setPlaceholderText("Technische Beschreibung der Schwachstelle, Ausnutzungsschritte und Nachweise...")
        self.txt_desc.setMinimumHeight(140)
        self.txt_desc.textChanged.connect(self._on_field_changed)
        v_content.addWidget(self.txt_desc)

        # Recommendation text
        v_content.addWidget(self._make_section_header(t("report.finding_rec", "Empfohlene Behebung (Remediation)")))
        self.txt_rec = QPlainTextEdit()
        self.txt_rec.setPlaceholderText("Konkrete Handlungsempfehlungen zur Behebung oder Risikominderung...")
        self.txt_rec.setMinimumHeight(100)
        self.txt_rec.textChanged.connect(self._on_field_changed)
        v_content.addWidget(self.txt_rec)

        # References
        v_content.addWidget(self._make_section_header(t("report.finding_refs", "Referenzen & CVEs (eine pro Zeile)")))
        self.txt_refs = QPlainTextEdit()
        self.txt_refs.setPlaceholderText("- CVE-2026-12345\n- https://owasp.org/...")
        self.txt_refs.setMaximumHeight(80)
        self.txt_refs.textChanged.connect(self._on_field_changed)
        v_content.addWidget(self.txt_refs)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, stretch=1)

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: 500; color: #c9d1d9; font-size: 12px;")
        return lbl

    def _make_section_header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; color: #79c0ff; font-size: 12px; margin-top: 4px;")
        return lbl

    def load_finding(self, finding: ReportFindingItem) -> None:
        self._loading = True
        try:
            self._finding = finding
            self.lbl_header_title.setText(finding.title or t("report.new_finding", "Neues Finding"))
            self.txt_title.setText(finding.title)

            sev_idx = self.cmb_severity.findData(finding.severity.lower())
            if sev_idx >= 0:
                self.cmb_severity.setCurrentIndex(sev_idx)

            stat_idx = self.cmb_status.findData(finding.status.lower())
            if stat_idx >= 0:
                self.cmb_status.setCurrentIndex(stat_idx)

            phase_idx = self.cmb_phase.findData(finding.phase.lower())
            if phase_idx >= 0:
                self.cmb_phase.setCurrentIndex(phase_idx)

            self.txt_target.setText(", ".join(finding.targets))
            self.txt_desc.setPlainText(finding.description)
            self.txt_rec.setPlainText(finding.recommendation)
            self.txt_refs.setPlainText("\n".join(finding.references))
        finally:
            self._loading = False

    def _on_field_changed(self) -> None:
        if self._loading:
            return
        self._debounce_timer.start()

    def _emit_changed(self) -> None:
        if not self._finding:
            return
        targets = [t.strip() for t in self.txt_target.text().split(",") if t.strip()]
        refs = [r.strip().lstrip("-* ").strip() for r in self.txt_refs.toPlainText().splitlines() if r.strip()]

        updated = ReportFindingItem(
            id=self._finding.id,
            title=self.txt_title.text().strip(),
            severity=str(self.cmb_severity.currentData()),
            status=str(self.cmb_status.currentData()),
            phase=str(self.cmb_phase.currentData()),
            targets=targets,
            timestamp=self._finding.timestamp,
            description=self.txt_desc.toPlainText(),
            recommendation=self.txt_rec.toPlainText(),
            references=refs,
            evidence_items=list(self._finding.evidence_items),
            loot_marker=self._finding.loot_marker,
            raw_extra=self._finding.raw_extra,
        )
        self._finding = updated
        self.lbl_header_title.setText(updated.title or t("report.new_finding", "Neues Finding"))
        self.finding_changed.emit(updated)

    def _on_delete_clicked(self) -> None:
        if self._finding:
            self.finding_deleted.emit(self._finding.id)

    def _on_duplicate_clicked(self) -> None:
        if self._finding:
            self.finding_duplicated.emit(self._finding.id)

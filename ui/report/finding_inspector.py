"""
SpectreHUD Report Finding Inspector.

Provides a dedicated finding editor with severity selection, phase categorization,
markdown description/recommendation editing, target scoping, and an integrated
Evidence & Proof-of-Concept drawer (Loot screenshots, terminal outputs, credentials).
"""

from typing import Optional
import uuid

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
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
from core.phases import normalize_phase_key
from core.reporting import ReportEvidenceItem, ReportFindingItem
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


class ReportEvidenceCard(QFrame):
    """Visual card representation of an attached evidence item."""

    insert_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    caption_changed = pyqtSignal(str, str)

    def __init__(self, item: ReportEvidenceItem, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("ReportEvidenceCard")
        self.setStyleSheet(
            "#ReportEvidenceCard { background: #161b22; border: 1px solid #30363d; border-radius: 6px; } "
            "#ReportEvidenceCard:hover { border-color: #58a6ff; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        lbl_icon = QLabel()
        if item.type == "screenshot":
            ic = icon("fa5s.camera", color="#79c0ff")
        elif item.type == "terminal":
            ic = icon("fa5s.terminal", color="#7ee787")
        elif item.type == "credential":
            ic = icon("fa5s.key", color="#d29922")
        else:
            ic = icon("fa5s.code", color="#bc8cff")
        lbl_icon.setPixmap(ic.pixmap(18, 18))
        layout.addWidget(lbl_icon)

        center_layout = QVBoxLayout()
        center_layout.setSpacing(2)

        self.txt_caption = QLineEdit()
        self.txt_caption.setText(item.caption or item.type.capitalize())
        self.txt_caption.setPlaceholderText(t("report.evidence_caption_placeholder", "Caption / label..."))
        self.txt_caption.setStyleSheet(
            "background: #0d1117; color: #f0f6fc; border: 1px solid #21262d; border-radius: 3px; font-size: 11px; font-weight: bold; padding: 2px 4px;"
        )
        self.txt_caption.textChanged.connect(self._on_caption_edited)
        center_layout.addWidget(self.txt_caption)

        preview_text = item.content.strip().replace("\r\n", " ").replace("\n", " ")
        if len(preview_text) > 80:
            preview_text = preview_text[:77] + "..."
        lbl_preview = QLabel(preview_text or f"[{item.type}]")
        lbl_preview.setStyleSheet("color: #8b949e; font-size: 10px; font-family: Consolas, monospace;")
        center_layout.addWidget(lbl_preview)

        layout.addLayout(center_layout, stretch=1)

        self.btn_insert = QPushButton()
        self.btn_insert.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_insert.setToolTip(t("report.insert_in_desc", "Insert into description"))
        self.btn_insert.setIcon(icon("fa5s.arrow-up", color="#79c0ff"))
        self.btn_insert.clicked.connect(lambda: self.insert_requested.emit(self.item.id))
        layout.addWidget(self.btn_insert)

        self.btn_delete = QPushButton()
        self.btn_delete.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_delete.setToolTip(t("report.delete_evidence", "Remove evidence"))
        self.btn_delete.setIcon(icon("fa5s.trash-alt", color="#f85149"))
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.item.id))
        layout.addWidget(self.btn_delete)

    def _on_caption_edited(self, text: str) -> None:
        self.item.caption = text
        self.caption_changed.emit(self.item.id, text)


class ReportFindingInspector(QWidget):
    """Contextual form, evidence drawer, and markdown editor for a single finding."""

    finding_changed = pyqtSignal(ReportFindingItem)
    finding_deleted = pyqtSignal(str)
    finding_duplicated = pyqtSignal(str)

    # External picker requests
    request_loot_screenshot = pyqtSignal()
    request_image_file = pyqtSignal()
    request_clipboard_history = pyqtSignal()
    request_loot_entry = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportFindingInspector")
        self._finding: Optional[ReportFindingItem] = None
        self._loading = False
        self._project_target_ip = ""

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(250)
        self._debounce_timer.timeout.connect(self._emit_changed)

        self._build_ui()

    def set_project_target_ip(self, ip: str) -> None:
        self._project_target_ip = ip

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
        self.btn_duplicate.setToolTip(t("report.duplicate_finding", "Duplicate finding"))
        self.btn_duplicate.setIcon(icon("fa5s.copy", color="#79c0ff"))
        self.btn_duplicate.clicked.connect(self._on_duplicate_clicked)
        h_layout.addWidget(self.btn_duplicate)

        self.btn_delete = QPushButton()
        self.btn_delete.setObjectName("btn_delete_finding")
        self.btn_delete.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_delete.setToolTip(t("report.delete_finding", "Delete finding"))
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
        self.txt_title.setPlaceholderText(
            t("report.finding_title_placeholder", "e.g. Remote Code Execution via Deserialization")
        )
        self.txt_title.textChanged.connect(self._on_field_changed)
        form.addRow(self._make_label(t("report.finding_title", "Title:")), self.txt_title)

        # Severity & Status
        sev_row = QHBoxLayout()
        self.cmb_severity = QComboBox()
        for s in SEVERITIES:
            self.cmb_severity.addItem(s.upper(), s)
        self.cmb_severity.currentIndexChanged.connect(self._on_field_changed)
        sev_row.addWidget(self.cmb_severity)

        sev_row.addWidget(self._make_label(t("report.finding_status", "Status:")))
        self.cmb_status = QComboBox()
        for s_code, s_label in STATUSES:
            self.cmb_status.addItem(t(f"report.status_{s_code}", s_label), s_code)
        self.cmb_status.currentIndexChanged.connect(self._on_field_changed)
        sev_row.addWidget(self.cmb_status)
        form.addRow(self._make_label(t("report.finding_severity", "Severity:")), sev_row)

        # Phase & Target
        phase_row = QHBoxLayout()
        self.cmb_phase = QComboBox()
        for p in PHASES:
            self.cmb_phase.addItem(t(f"phases.{p}", p.capitalize()), p)
        self.cmb_phase.currentIndexChanged.connect(self._on_field_changed)
        phase_row.addWidget(self.cmb_phase)

        phase_row.addWidget(self._make_label(t("report.finding_target", "Target:")))
        self.txt_target = QLineEdit()
        self.txt_target.setPlaceholderText(
            t("report.finding_target_placeholder", "e.g. 10.10.10.5 or /api/v1/auth")
        )
        self.txt_target.textChanged.connect(self._on_field_changed)
        phase_row.addWidget(self.txt_target)

        self.btn_apply_target = QPushButton()
        self.btn_apply_target.setObjectName("btn_apply_target")
        self.btn_apply_target.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_apply_target.setToolTip(t("report.apply_project_target", "Apply project target IP"))
        self.btn_apply_target.setIcon(icon("fa5s.crosshairs", color="#79c0ff"))
        self.btn_apply_target.clicked.connect(self._on_apply_project_target)
        phase_row.addWidget(self.btn_apply_target)

        form.addRow(self._make_label(t("report.finding_phase", "Phase:")), phase_row)
        v_content.addLayout(form)

        # Description text
        v_content.addWidget(self._make_section_header(t("report.finding_desc", "Description & Proof of Concept")))
        self.txt_desc = QPlainTextEdit()
        self.txt_desc.setPlaceholderText(
            t(
                "report.finding_desc_placeholder",
                "Technical description of the vulnerability, reproduction steps, and proof of concept...",
            )
        )
        self.txt_desc.setMinimumHeight(140)
        self.txt_desc.textChanged.connect(self._on_field_changed)
        v_content.addWidget(self.txt_desc)

        # Evidence Drawer Section
        ev_header_layout = QHBoxLayout()
        ev_header_layout.addWidget(self._make_section_header(t("report.finding_evidence", "Evidence & Artifacts")))
        self.lbl_evidence_count = QLabel("(0)")
        self.lbl_evidence_count.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: bold;")
        ev_header_layout.addWidget(self.lbl_evidence_count)
        ev_header_layout.addStretch()

        # Evidence Action Buttons
        self.btn_add_loot_screenshot = QPushButton()
        self.btn_add_loot_screenshot.setObjectName("btn_add_loot_screenshot")
        self.btn_add_loot_screenshot.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_add_loot_screenshot.setToolTip(t("report.add_loot_screenshot", "Insert screenshot from Loot"))
        self.btn_add_loot_screenshot.setIcon(icon("fa5s.camera", color="#79c0ff"))
        self.btn_add_loot_screenshot.clicked.connect(self.request_loot_screenshot.emit)
        ev_header_layout.addWidget(self.btn_add_loot_screenshot)

        self.btn_browse_screenshot = QPushButton()
        self.btn_browse_screenshot.setObjectName("btn_browse_screenshot")
        self.btn_browse_screenshot.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_browse_screenshot.setToolTip(t("report.browse_screenshot", "Import image from disk"))
        self.btn_browse_screenshot.setIcon(icon("fa5s.folder-open", color="#79c0ff"))
        self.btn_browse_screenshot.clicked.connect(self.request_image_file.emit)
        ev_header_layout.addWidget(self.btn_browse_screenshot)

        self.btn_add_terminal = QPushButton()
        self.btn_add_terminal.setObjectName("btn_add_terminal")
        self.btn_add_terminal.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_add_terminal.setToolTip(t("report.add_terminal_evidence", "From clipboard history (Terminal/PoC)"))
        self.btn_add_terminal.setIcon(icon("fa5s.terminal", color="#7ee787"))
        self.btn_add_terminal.clicked.connect(self.request_clipboard_history.emit)
        ev_header_layout.addWidget(self.btn_add_terminal)

        self.btn_add_loot_entry = QPushButton()
        self.btn_add_loot_entry.setObjectName("btn_add_loot_entry")
        self.btn_add_loot_entry.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_add_loot_entry.setToolTip(t("report.add_loot_entry", "From session loot (Creds/Hashes/Flags)"))
        self.btn_add_loot_entry.setIcon(icon("fa5s.key", color="#d29922"))
        self.btn_add_loot_entry.clicked.connect(self.request_loot_entry.emit)
        ev_header_layout.addWidget(self.btn_add_loot_entry)

        self.btn_add_code = QPushButton()
        self.btn_add_code.setObjectName("btn_add_code")
        self.btn_add_code.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_add_code.setToolTip(t("report.add_code_evidence", "Insert code snippet / exploit"))
        self.btn_add_code.setIcon(icon("fa5s.code", color="#bc8cff"))
        self.btn_add_code.clicked.connect(self._on_add_code_clicked)
        ev_header_layout.addWidget(self.btn_add_code)

        v_content.addLayout(ev_header_layout)

        # Evidence Cards Container
        self.evidence_container = QWidget()
        self.evidence_cards_layout = QVBoxLayout(self.evidence_container)
        self.evidence_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.evidence_cards_layout.setSpacing(6)
        v_content.addWidget(self.evidence_container)

        # Recommendation text
        v_content.addWidget(self._make_section_header(t("report.finding_remediation", "Remediation & Recommendations")))
        self.txt_rec = QPlainTextEdit()
        self.txt_rec.setPlaceholderText(
            t(
                "report.finding_remediation_placeholder",
                "Remediation steps, configuration hardening, or patch guidance...",
            )
        )
        self.txt_rec.setMinimumHeight(100)
        self.txt_rec.textChanged.connect(self._on_field_changed)
        v_content.addWidget(self.txt_rec)

        # References
        v_content.addWidget(self._make_section_header(t("report.finding_refs", "References & CVEs (one per line)")))
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
            self.lbl_header_title.setText(finding.title or t("report.new_finding_default_title", "New Finding"))
            self.txt_title.setText(finding.title)

            sev_idx = self.cmb_severity.findData(finding.severity.lower())
            if sev_idx >= 0:
                self.cmb_severity.setCurrentIndex(sev_idx)

            stat_idx = self.cmb_status.findData(finding.status.lower())
            if stat_idx >= 0:
                self.cmb_status.setCurrentIndex(stat_idx)

            phase_idx = self.cmb_phase.findData(normalize_phase_key(finding.phase))
            if phase_idx >= 0:
                self.cmb_phase.setCurrentIndex(phase_idx)

            self.txt_target.setText(", ".join(finding.targets))
            self.txt_desc.setPlainText(finding.description)
            self.txt_rec.setPlainText(finding.recommendation)
            self.txt_refs.setPlainText("\n".join(finding.references))
            self._refresh_evidence_cards()
        finally:
            self._loading = False

    def _refresh_evidence_cards(self) -> None:
        while self.evidence_cards_layout.count():
            child = self.evidence_cards_layout.takeAt(0)
            widget = child.widget()
            if widget:
                widget.deleteLater()

        items = self._finding.evidence_items if self._finding else []
        self.lbl_evidence_count.setText(f"({len(items)})")

        if not items:
            lbl_empty = QLabel(t("report.no_evidence_yet", "No evidence linked yet."))
            lbl_empty.setStyleSheet("color: #8b949e; font-style: italic; font-size: 11px; padding: 4px;")
            self.evidence_cards_layout.addWidget(lbl_empty)
            return

        for ev in items:
            card = ReportEvidenceCard(ev, self)
            card.insert_requested.connect(self._on_insert_evidence_into_desc)
            card.delete_requested.connect(self._on_delete_evidence)
            card.caption_changed.connect(self._on_evidence_caption_changed)
            self.evidence_cards_layout.addWidget(card)

    def attach_evidence_item(self, item: ReportEvidenceItem, insert_into_description: bool = True) -> None:
        if not self._finding:
            return
        self._finding.attach_evidence(item, insert_into_description=insert_into_description)
        self._loading = True
        try:
            self.txt_desc.setPlainText(self._finding.description)
        finally:
            self._loading = False
        self._refresh_evidence_cards()
        self._emit_changed()

    def _on_insert_evidence_into_desc(self, item_id: str) -> None:
        if not self._finding:
            return
        ev = next((i for i in self._finding.evidence_items if i.id == item_id), None)
        if not ev:
            return
        md = ev.to_markdown()
        cur = self.txt_desc.textCursor()
        cur.insertText(f"\n\n{md}\n")
        self.txt_desc.setTextCursor(cur)
        self.txt_desc.setFocus()

    def _on_delete_evidence(self, item_id: str) -> None:
        if not self._finding:
            return
        self._finding.detach_evidence(item_id, remove_from_description=True)
        self._loading = True
        try:
            self.txt_desc.setPlainText(self._finding.description)
        finally:
            self._loading = False
        self._refresh_evidence_cards()
        self._emit_changed()

    def _on_evidence_caption_changed(self, item_id: str, new_caption: str) -> None:
        if not self._finding:
            return
        self._finding.update_evidence(item_id, caption=new_caption)
        self._loading = True
        try:
            self.txt_desc.setPlainText(self._finding.description)
        finally:
            self._loading = False
        self._emit_changed()

    def _on_apply_project_target(self) -> None:
        if not self._project_target_ip:
            return
        current = self.txt_target.text().strip()
        if not current:
            self.txt_target.setText(self._project_target_ip)
        elif self._project_target_ip not in current:
            self.txt_target.setText(f"{current}, {self._project_target_ip}")

    def _on_add_code_clicked(self) -> None:
        if not self._finding:
            return
        code_item = ReportEvidenceItem(
            id=f"{self._finding.id}-code-{uuid.uuid4().hex[:4]}",
            type="code",
            caption="Code Snippet",
            content="# PoC script / code snippet\nprint('Exploit executed')",
            source_loot_id=self._finding.id,
        )
        self.attach_evidence_item(code_item, insert_into_description=True)

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
        self.lbl_header_title.setText(updated.title or t("report.new_finding_default_title", "New Finding"))
        self.finding_changed.emit(updated)

    def _on_delete_clicked(self) -> None:
        if self._finding:
            self.finding_deleted.emit(self._finding.id)

    def _on_duplicate_clicked(self) -> None:
        if self._finding:
            self.finding_duplicated.emit(self._finding.id)

"""
Interactive Attack Path & Assessment Narrative Inspector for SpectreHUD Report Workspace.
Provides visual attack chain timelines, finding linkage, and auto-chain generation from session findings.
"""

from typing import List, Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
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
from core.phases import PHASES, get_phase
from core.reporting import (
    AttackPathStep,
    ReportAttackPath,
    ReportFindingItem,
    ReportWorkspaceDocument,
)
from ui.glass_panel import GlassPanel
from ui.styles.icons import icon

PHASE_COLORS = {
    "recon": "#58a6ff",
    "access": "#d29922",
    "privesc": "#f85149",
    "postex": "#bc8cff",
    "scripts": "#39d353",
    "misc": "#8b949e",
}

PHASE_ORDER = {
    "recon": 1,
    "access": 2,
    "privesc": 3,
    "postex": 4,
    "scripts": 5,
    "misc": 6,
}


class AttackStepCard(GlassPanel):
    """Visual card representing a single step in the attack chain."""

    step_changed = pyqtSignal()
    move_up_requested = pyqtSignal(int)
    move_down_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    finding_selected = pyqtSignal(str)

    def __init__(
        self,
        step: AttackPathStep,
        step_index: int,
        total_steps: int,
        findings: List[ReportFindingItem],
        language: str = "de",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.step = step
        self.step_index = step_index
        self.total_steps = total_steps
        self.findings = findings
        self.language = language
        self._loading = False

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header: Step badge, Phase combo, Title input, Navigation/Action buttons
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.lbl_step_num = QLabel(f"#{self.step_index + 1}")
        self.lbl_step_num.setStyleSheet(
            "font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 4px; "
            "background: rgba(0, 229, 255, 0.15); color: #00e5ff; border: 1px solid rgba(0, 229, 255, 0.35);"
        )
        top_row.addWidget(self.lbl_step_num)

        # Phase selector
        self.cmb_phase = QComboBox()
        self.cmb_phase.setStyleSheet(
            "QComboBox { background: #161b22; border: 1px solid #30363d; border-radius: 4px; color: #f0f6fc; padding: 2px 6px; font-weight: 500; } "
            "QComboBox:focus { border-color: #00e5ff; }"
        )
        for phase_obj in PHASES:
            self.cmb_phase.addItem(
                icon(phase_obj.icon, color=PHASE_COLORS.get(phase_obj.key, "#8b949e")),
                phase_obj.long,
                phase_obj.key,
            )

        cur_phase_idx = self.cmb_phase.findData(self.step.phase)
        if cur_phase_idx >= 0:
            self.cmb_phase.setCurrentIndex(cur_phase_idx)
        self.cmb_phase.currentIndexChanged.connect(self._on_phase_changed)
        top_row.addWidget(self.cmb_phase)

        # Title input
        self.edit_title = QLineEdit()
        self.edit_title.setText(self.step.title)
        self.edit_title.setPlaceholderText(t("report.step_title_placeholder", "Step title / attack technique..."))
        self.edit_title.setStyleSheet(
            "QLineEdit { background: #0d1117; border: 1px solid #30363d; border-radius: 4px; color: #f0f6fc; padding: 4px 8px; font-weight: bold; } "
            "QLineEdit:focus { border-color: #00e5ff; }"
        )
        self.edit_title.textChanged.connect(self._on_title_changed)
        top_row.addWidget(self.edit_title, stretch=1)

        # Reorder & Delete tools
        self.btn_up = QPushButton()
        self.btn_up.setIcon(icon("fa5s.arrow-up", color="#79c0ff"))
        self.btn_up.setToolTip(t("report.move_up", "Move step up"))
        self.btn_up.setEnabled(self.step_index > 0)
        self.btn_up.setStyleSheet("QPushButton { background: transparent; border: 1px solid #30363d; border-radius: 3px; padding: 2px 6px; }")
        self.btn_up.clicked.connect(lambda: self.move_up_requested.emit(self.step_index))
        top_row.addWidget(self.btn_up)

        self.btn_down = QPushButton()
        self.btn_down.setIcon(icon("fa5s.arrow-down", color="#79c0ff"))
        self.btn_down.setToolTip(t("report.move_down", "Move step down"))
        self.btn_down.setEnabled(self.step_index < self.total_steps - 1)
        self.btn_down.setStyleSheet("QPushButton { background: transparent; border: 1px solid #30363d; border-radius: 3px; padding: 2px 6px; }")
        self.btn_down.clicked.connect(lambda: self.move_down_requested.emit(self.step_index))
        top_row.addWidget(self.btn_down)

        self.btn_del = QPushButton()
        self.btn_del.setIcon(icon("fa5s.trash-alt", color="#f85149"))
        self.btn_del.setToolTip(t("report.delete_step", "Delete step"))
        self.btn_del.setStyleSheet(
            "QPushButton { background: rgba(248, 81, 73, 0.1); border: 1px solid rgba(248, 81, 73, 0.3); border-radius: 3px; padding: 2px 6px; } "
            "QPushButton:hover { background: rgba(248, 81, 73, 0.25); }"
        )
        self.btn_del.clicked.connect(lambda: self.delete_requested.emit(self.step_index))
        top_row.addWidget(self.btn_del)

        layout.addLayout(top_row)

        # Narrative / Description
        self.txt_desc = QPlainTextEdit()
        self.txt_desc.setPlainText(self.step.description)
        self.txt_desc.setPlaceholderText(
            t("report.step_desc_placeholder", "Execution narrative: how this step was executed, tools utilized, and outcome...")
        )
        self.txt_desc.setMaximumHeight(65)
        self.txt_desc.setStyleSheet(
            "QPlainTextEdit { background: #0d1117; border: 1px solid #30363d; border-radius: 4px; color: #c9d1d9; padding: 4px; } "
            "QPlainTextEdit:focus { border-color: #00e5ff; }"
        )
        self.txt_desc.textChanged.connect(self._on_desc_changed)
        layout.addWidget(self.txt_desc)

        # Bottom row: Link finding
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        lbl_link = QLabel(t("report.linked_finding_label", "Linked Finding:"))
        lbl_link.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 500;")
        bottom_row.addWidget(lbl_link)

        self.cmb_finding = QComboBox()
        self.cmb_finding.setStyleSheet(
            "QComboBox { background: #161b22; border: 1px solid #30363d; border-radius: 3px; color: #c9d1d9; padding: 2px 6px; font-size: 11px; } "
            "QComboBox:focus { border-color: #00e5ff; }"
        )
        self.cmb_finding.addItem(t("report.no_linked_finding", "— None —"), "")
        cur_find_idx = 0
        for idx, f in enumerate(self.findings, start=1):
            title = f.title or f.id
            self.cmb_finding.addItem(f"[{f.severity.upper()}] {title}", f.id)
            if self.step.finding_id == f.id or (self.step.finding_id and self.step.finding_id.strip().lower() == (f.title or "").strip().lower()):
                cur_find_idx = idx
                self.step.finding_id = f.id

        self.cmb_finding.setCurrentIndex(cur_find_idx)
        self.cmb_finding.currentIndexChanged.connect(self._on_finding_link_changed)
        bottom_row.addWidget(self.cmb_finding, stretch=1)

        self.btn_jump = QPushButton()
        self.btn_jump.setIcon(icon("fa5s.arrow-right", color="#00e5ff"))
        self.btn_jump.setToolTip(t("report.jump_to_finding_tip", "Inspect linked finding details"))
        self.btn_jump.setEnabled(bool(self.step.finding_id))
        self.btn_jump.setStyleSheet(
            "QPushButton { background: rgba(0, 229, 255, 0.1); border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 3px; padding: 2px 6px; } "
            "QPushButton:hover { background: rgba(0, 229, 255, 0.25); }"
        )
        self.btn_jump.clicked.connect(self._on_jump_clicked)
        bottom_row.addWidget(self.btn_jump)

        layout.addLayout(bottom_row)

    def _on_phase_changed(self) -> None:
        self.step.phase = self.cmb_phase.currentData()
        self.step_changed.emit()

    def _on_title_changed(self, text: str) -> None:
        self.step.title = text.strip()
        self.step_changed.emit()

    def _on_desc_changed(self) -> None:
        self.step.description = self.txt_desc.toPlainText().strip()
        self.step_changed.emit()

    def _on_finding_link_changed(self) -> None:
        fid = self.cmb_finding.currentData() or None
        self.step.finding_id = fid
        self.btn_jump.setEnabled(bool(fid))
        self.step_changed.emit()

    def _on_jump_clicked(self) -> None:
        if self.step.finding_id:
            self.finding_selected.emit(self.step.finding_id)


class ReportAttackPathInspector(QWidget):
    """Interactive Attack Path and Assessment Narrative Cockpit."""

    attack_path_changed = pyqtSignal(ReportAttackPath)
    finding_selected = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportAttackPathInspector")
        self._path = ReportAttackPath()
        self._findings: List[ReportFindingItem] = []
        self._language = "de"
        self._loading = False

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._emit_changed)

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
        lbl_icon.setPixmap(icon("fa5s.route", color="#00e5ff").pixmap(20, 20))
        h_layout.addWidget(lbl_icon)

        self.lbl_title = QLabel(t("report.inspector_attack_path_title", "Attack Path / Assessment Narrative"))
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f0f6fc;")
        h_layout.addWidget(self.lbl_title)
        h_layout.addStretch()

        self.lbl_steps_badge = QLabel()
        self.lbl_steps_badge.setStyleSheet(
            "font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; "
            "background: rgba(0, 229, 255, 0.15); color: #00e5ff; border: 1px solid rgba(0, 229, 255, 0.35);"
        )
        h_layout.addWidget(self.lbl_steps_badge)

        self.btn_auto_generate = QPushButton(t("report.auto_generate_chain", "Generate Chain from Findings"))
        self.btn_auto_generate.setIcon(icon("fa5s.magic", color="#79c0ff"))
        self.btn_auto_generate.setStyleSheet(
            "QPushButton { background: rgba(121, 192, 255, 0.15); border: 1px solid rgba(121, 192, 255, 0.35); border-radius: 4px; color: #79c0ff; font-weight: bold; padding: 4px 10px; font-size: 11px; } "
            "QPushButton:hover { background: rgba(121, 192, 255, 0.28); }"
        )
        self.btn_auto_generate.clicked.connect(self._on_auto_generate_clicked)
        h_layout.addWidget(self.btn_auto_generate)

        self.btn_add_step = QPushButton(t("report.add_attack_step", "+ Add Step"))
        self.btn_add_step.setIcon(icon("fa5s.plus", color="#00e5ff"))
        self.btn_add_step.setStyleSheet(
            "QPushButton { background: rgba(0, 229, 255, 0.15); border: 1px solid rgba(0, 229, 255, 0.35); border-radius: 4px; color: #00e5ff; font-weight: bold; padding: 4px 10px; font-size: 11px; } "
            "QPushButton:hover { background: rgba(0, 229, 255, 0.28); }"
        )
        self.btn_add_step.clicked.connect(self._on_add_step_clicked)
        h_layout.addWidget(self.btn_add_step)

        main_layout.addWidget(self.header_card)

        # 2. Scroll Area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(12, 8, 12, 12)
        self.content_layout.setSpacing(10)

        # Narrative Storyline Card
        intro_card = GlassPanel(content_widget)
        intro_layout = QVBoxLayout(intro_card)
        intro_layout.setContentsMargins(12, 10, 12, 10)
        intro_layout.setSpacing(6)

        lbl_intro_title = QLabel(t("report.attack_storyline_title", "Assessment Narrative & Storyline"))
        lbl_intro_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #f0f6fc;")
        intro_layout.addWidget(lbl_intro_title)

        self.txt_intro = QPlainTextEdit()
        self.txt_intro.setPlaceholderText(
            t("report.attack_storyline_placeholder", "High-level penetration testing storyline describing the attacker's progression, pivot points, and impact...")
        )
        self.txt_intro.setMaximumHeight(75)
        self.txt_intro.textChanged.connect(self._on_field_changed)
        intro_layout.addWidget(self.txt_intro)

        self.content_layout.addWidget(intro_card)

        # Steps Timeline Header
        lbl_timeline_title = QLabel(t("report.attack_chain_timeline_title", "Attack Chain Timeline"))
        lbl_timeline_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #8b949e; margin-top: 4px;")
        self.content_layout.addWidget(lbl_timeline_title)

        # Container for step cards
        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.setSpacing(8)
        self.content_layout.addWidget(self.steps_container)

        self.content_layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, stretch=1)

    def load_attack_path(self, doc: ReportWorkspaceDocument) -> None:
        """Loads structured attack path and session findings."""
        self._loading = True
        try:
            self._findings = list(doc.findings)
            self._path = doc.get_attack_path()
            self._language = doc.language

            # Resolve any step finding_ids that match finding titles (e.g. from human-edited markdown)
            for s in self._path.steps:
                if s.finding_id and s.finding_id not in [f.id for f in self._findings]:
                    matched = next(
                        (f for f in self._findings if (f.title or "").strip().lower() == s.finding_id.strip().lower()),
                        None,
                    )
                    if matched:
                        s.finding_id = matched.id

            self.lbl_title.setText(self._path.title or t("report.inspector_attack_path_title", "Attack Path / Assessment Narrative"))
            self.txt_intro.setPlainText(self._path.narrative_intro)

            self._refresh_step_cards()
        finally:
            self._loading = False

    def _refresh_step_cards(self) -> None:
        # Clear existing cards
        while self.steps_layout.count() > 0:
            child = self.steps_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        total = len(self._path.steps)
        self.lbl_steps_badge.setText(
            t("report.steps_count", "{count} Steps", count=total) if self._language != "de" else f"{total} Schritte"
        )

        for idx, step in enumerate(self._path.steps):
            step.step_number = idx + 1
            card = AttackStepCard(
                step=step,
                step_index=idx,
                total_steps=total,
                findings=self._findings,
                language=self._language,
                parent=self.steps_container,
            )
            card.step_changed.connect(self._on_field_changed)
            card.move_up_requested.connect(self._on_move_up)
            card.move_down_requested.connect(self._on_move_down)
            card.delete_requested.connect(self._on_delete_step)
            card.finding_selected.connect(self.finding_selected.emit)
            self.steps_layout.addWidget(card)

    def _on_move_up(self, index: int) -> None:
        if index > 0 and index < len(self._path.steps):
            self._path.steps[index - 1], self._path.steps[index] = self._path.steps[index], self._path.steps[index - 1]
            self._refresh_step_cards()
            self._on_field_changed()

    def _on_move_down(self, index: int) -> None:
        if index >= 0 and index < len(self._path.steps) - 1:
            self._path.steps[index], self._path.steps[index + 1] = self._path.steps[index + 1], self._path.steps[index]
            self._refresh_step_cards()
            self._on_field_changed()

    def _on_delete_step(self, index: int) -> None:
        if 0 <= index < len(self._path.steps):
            self._path.steps.pop(index)
            self._refresh_step_cards()
            self._on_field_changed()

    def _on_add_step_clicked(self) -> None:
        new_step = AttackPathStep(
            step_number=len(self._path.steps) + 1,
            phase="access",
            title=t("report.new_step_default_title", "New Attack Step"),
            description="",
            finding_id=None,
        )
        self._path.steps.append(new_step)
        self._refresh_step_cards()
        self._on_field_changed()

    def _on_auto_generate_clicked(self) -> None:
        """Generates sequential kill chain steps from current findings ordered by phase."""
        if not self._findings:
            return

        sorted_findings = sorted(
            self._findings,
            key=lambda f: PHASE_ORDER.get(f.phase, 99),
        )

        steps: List[AttackPathStep] = []
        for idx, f in enumerate(sorted_findings, start=1):
            p_obj = get_phase(f.phase)
            steps.append(
                AttackPathStep(
                    step_number=idx,
                    phase=f.phase,
                    title=f.title or p_obj.short,
                    description=f.description[:250].strip() if f.description else "",
                    finding_id=f.id,
                )
            )

        self._path.steps = steps
        self._refresh_step_cards()
        self._on_field_changed()

    def _on_field_changed(self) -> None:
        if self._loading:
            return
        self._debounce_timer.start()

    def _emit_changed(self) -> None:
        self._path.narrative_intro = self.txt_intro.toPlainText().strip()
        self.attack_path_changed.emit(self._path)

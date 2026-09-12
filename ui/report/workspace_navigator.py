"""
SpectreHUD Report Workspace Navigator.

Provides a tree-based semantic structure navigator for the 3-column Report Workspace,
displaying metadata, narrative sections, and findings with QtAwesome severity icons.
"""

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.reporting import ReportWorkspaceDocument
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


class ReportWorkspaceNavigator(QWidget):
    """Left-column structure navigator for the SpectreHUD Report Workspace."""

    navigate_requested = pyqtSignal(str, object)  # view_type: str, item_id: Optional[str]
    add_finding_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportWorkspaceNavigator")
        self._doc: Optional[ReportWorkspaceDocument] = None
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Header panel
        self.header_panel = GlassPanel(self)
        self.header_panel.setObjectName("NavHeaderPanel")
        h_layout = QVBoxLayout(self.header_panel)
        h_layout.setContentsMargins(8, 8, 8, 8)
        h_layout.setSpacing(4)

        top_row = QHBoxLayout()
        self.lbl_project = QLabel(t("report.workspace_no_project", "Kein Projekt"))
        self.lbl_project.setProperty("class", "WorkspaceNavProjectLabel")
        self.lbl_project.setStyleSheet("font-weight: bold; font-size: 13px; color: #f0f6fc;")
        top_row.addWidget(self.lbl_project)
        top_row.addStretch()

        self.btn_add_finding = QPushButton()
        self.btn_add_finding.setObjectName("btn_nav_add_finding")
        self.btn_add_finding.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_add_finding.setToolTip(t("report.add_finding", "Neues Finding anlegen"))
        self.btn_add_finding.setIcon(icon("fa5s.plus", color="#00e5ff"))
        self.btn_add_finding.clicked.connect(self.add_finding_requested.emit)
        top_row.addWidget(self.btn_add_finding)

        h_layout.addLayout(top_row)

        self.lbl_scope = QLabel("")
        self.lbl_scope.setStyleSheet("font-size: 11px; color: #8b949e;")
        h_layout.addWidget(self.lbl_scope)

        main_layout.addWidget(self.header_panel)

        # Tree navigation
        self.tree = QTreeWidget(self)
        self.tree.setObjectName("WorkspaceNavTree")
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.setStyleSheet(
            """
            QTreeWidget#WorkspaceNavTree {
                background-color: rgba(13, 17, 23, 0.7);
                border: 1px solid rgba(48, 54, 61, 0.6);
                border-radius: 6px;
                color: #c9d1d9;
                font-size: 12px;
                padding: 4px;
            }
            QTreeWidget#WorkspaceNavTree::item {
                padding: 5px 8px;
                border-radius: 4px;
            }
            QTreeWidget#WorkspaceNavTree::item:hover {
                background-color: rgba(22, 27, 34, 0.9);
                color: #f0f6fc;
            }
            QTreeWidget#WorkspaceNavTree::item:selected {
                background-color: #1f293d;
                color: #00e5ff;
                font-weight: bold;
            }
            """
        )
        self.tree.itemClicked.connect(self._on_item_clicked)
        main_layout.addWidget(self.tree, stretch=1)

    def load_document(
        self,
        doc: ReportWorkspaceDocument,
        project_name: str = "",
        target_ip: str = "",
    ) -> None:
        self._doc = doc
        pname = project_name or doc.metadata.client or "Bericht"
        self.lbl_project.setText(pname)
        scope_text = target_ip or doc.metadata.target_scope
        self.lbl_scope.setText(f"Scope: {scope_text}" if scope_text else "")

        self.tree.clear()

        # 1. Metadaten
        item_meta = QTreeWidgetItem(self.tree)
        item_meta.setText(0, t("report.section_metadata", "Metadaten"))
        item_meta.setIcon(0, icon("fa5s.clipboard-list", color="#79c0ff"))
        item_meta.setData(0, Qt.ItemDataRole.UserRole, ("metadata", None))

        # 2. Narrativ Sektionen
        item_narrative_root = QTreeWidgetItem(self.tree)
        item_narrative_root.setText(0, t("report.group_narrative", "NARRATIV"))
        item_narrative_root.setFlags(item_narrative_root.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        item_narrative_root.setForeground(0, Qt.GlobalColor.gray)

        # Executive Summary
        item_exec = QTreeWidgetItem(item_narrative_root)
        item_exec.setText(0, t("report.section_exec_summary", "Executive Summary"))
        item_exec.setIcon(0, icon("fa5s.align-left", color="#79c0ff"))
        item_exec.setData(0, Qt.ItemDataRole.UserRole, ("section", "executive_summary"))

        # Scope & Methodik
        item_scope = QTreeWidgetItem(item_narrative_root)
        item_scope.setText(0, t("report.section_scope", "Scope & Methodik"))
        item_scope.setIcon(0, icon("fa5s.bullseye", color="#79c0ff"))
        item_scope.setData(0, Qt.ItemDataRole.UserRole, ("section", "scope_limitations"))

        # Angriffspfad
        item_attack = QTreeWidgetItem(item_narrative_root)
        item_attack.setText(0, t("report.section_attack_path", "Angriffspfad"))
        item_attack.setIcon(0, icon("fa5s.route", color="#79c0ff"))
        item_attack.setData(0, Qt.ItemDataRole.UserRole, ("section", "attack_path"))

        item_narrative_root.setExpanded(True)

        # 3. Findings
        findings_count = len(doc.findings)
        item_findings_root = QTreeWidgetItem(self.tree)
        item_findings_root.setText(0, f"{t('report.group_findings', 'FINDINGS')} ({findings_count})")
        item_findings_root.setIcon(0, icon("fa5s.shield-alt", color="#00e5ff"))
        item_findings_root.setData(0, Qt.ItemDataRole.UserRole, ("findings_overview", None))

        for f in doc.findings:
            item_f = QTreeWidgetItem(item_findings_root)
            item_f.setText(0, f.title or "Unbenanntes Finding")
            sev = (f.severity or "medium").lower()
            ic_name = SEV_ICONS.get(sev, "fa5s.circle")
            color = SEV_COLORS.get(sev, "#d29922")
            item_f.setIcon(0, icon(ic_name, color=color))
            tooltip = f"[{sev.upper()}] {f.title}\nStatus: {f.status}\nPhase: {f.phase}"
            item_f.setToolTip(0, tooltip)
            item_f.setData(0, Qt.ItemDataRole.UserRole, ("finding", f.id))

        item_findings_root.setExpanded(True)

        # 4. Remediation & Anhang
        item_remed = QTreeWidgetItem(self.tree)
        item_remed.setText(0, t("report.section_remediation", "Remediation & Plan"))
        item_remed.setIcon(0, icon("fa5s.tasks", color="#79c0ff"))
        item_remed.setData(0, Qt.ItemDataRole.UserRole, ("section", "remediation_table"))

        item_appendix = QTreeWidgetItem(self.tree)
        item_appendix.setText(0, t("report.section_appendix", "Anhang & Nachweise"))
        item_appendix.setIcon(0, icon("fa5s.paperclip", color="#79c0ff"))
        item_appendix.setData(0, Qt.ItemDataRole.UserRole, ("section", "appendix"))

        # 5. Raw Markdown
        item_raw = QTreeWidgetItem(self.tree)
        item_raw.setText(0, t("report.section_raw_markdown", "Gesamt-Markdown (Raw)"))
        item_raw.setIcon(0, icon("fa5s.code", color="#c9d1d9"))
        item_raw.setData(0, Qt.ItemDataRole.UserRole, ("raw_markdown", None))

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            view_type, item_id = data
            self.navigate_requested.emit(view_type, item_id)

    def select_item(self, view_type: str, item_id: Optional[str] = None) -> None:
        """Selects the tree item matching view_type and item_id."""
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top.data(0, Qt.ItemDataRole.UserRole) == (view_type, item_id):
                self.tree.setCurrentItem(top)
                return
            for j in range(top.childCount()):
                child = top.child(j)
                if child.data(0, Qt.ItemDataRole.UserRole) == (view_type, item_id):
                    self.tree.setCurrentItem(child)
                    return

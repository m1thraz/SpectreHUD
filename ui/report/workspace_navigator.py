"""
SpectreHUD Report Workspace Navigator.

Provides a structured tree navigation of report sections and findings,
aligned with SpectreHUD's Loot phases (Recon, Access, PrivEsc, PostEx, Misc),
with 1-click Loot synchronization and quick navigation.
"""

from typing import Optional

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
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
from core.phases import normalize_phase_key
from core.reporting import ReportWorkspaceDocument, assess_report_readiness
from ui.glass_panel import GlassPanel
from ui.report.navigation import ReportLocation
from ui.styles.icons import get_theme_color, icon

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

PHASE_META = {
    "recon": ("Reconnaissance", "fa5s.search", "#79c0ff"),
    "access": ("Initial Access", "fa5s.door-open", "#f85149"),
    "privesc": ("Privilege Escalation", "fa5s.key", "#d29922"),
    "postex": ("Post-Exploitation", "fa5s.network-wired", "#bc8cff"),
    "scripts": ("Scripts & Automation", "fa5s.code", "#7ee787"),
    "misc": ("Miscellaneous", "fa5s.folder", "#8b949e"),
}


class ReportWorkspaceNavigator(QWidget):
    """Collapsible structure navigator for the SpectreHUD Report Workspace."""

    navigate_requested = pyqtSignal(object)  # ReportLocation
    add_finding_requested = pyqtSignal()
    promote_finding_requested = pyqtSignal()
    sync_loot_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportWorkspaceNavigator")
        self._doc: Optional[ReportWorkspaceDocument] = None
        self._project_name: str = ""
        self._target_ip: str = ""
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
        self.lbl_project = QLabel(t("report.workspace_no_project", "No Project"))
        self.lbl_project.setProperty("class", "WorkspaceNavProjectLabel")
        top_row.addWidget(self.lbl_project)
        top_row.addStretch()

        h_layout.addLayout(top_row)

        self.lbl_scope = QLabel("")
        self.lbl_scope.setProperty("class", "WorkspaceNavScopeLabel")
        h_layout.addWidget(self.lbl_scope)

        self.lbl_sync_state = QLabel(t("report.loot_sync_unknown", "Loot status unavailable"))
        self.lbl_sync_state.setProperty("class", "WorkspaceSyncState")
        self.lbl_sync_state.setProperty("syncState", "unknown")
        h_layout.addWidget(self.lbl_sync_state)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        self.btn_sync_loot = QPushButton(t("report.sync_loot_short", "Sync Loot"))
        self.btn_sync_loot.setObjectName("btn_nav_sync_loot")
        self.btn_sync_loot.setProperty("class", "SecondaryBtn AppendLootBtn")
        self.btn_sync_loot.setToolTip(t("report.sync_from_loot", "Sync / append from Loot"))
        self.btn_sync_loot.setIcon(icon("fa5s.sync-alt", color=get_theme_color("STATUS_SUCCESS")))
        self.btn_sync_loot.clicked.connect(self.sync_loot_requested.emit)
        action_row.addWidget(self.btn_sync_loot, stretch=1)

        self.btn_add_finding = QPushButton(t("report.add_finding_short", "Finding"))
        self.btn_add_finding.setObjectName("btn_nav_add_finding")
        self.btn_add_finding.setProperty("class", "SecondaryBtn")
        self.btn_add_finding.setToolTip(t("report.add_finding", "Add new finding"))
        self.btn_add_finding.setIcon(icon("fa5s.plus", color=get_theme_color("CYBER_CYAN")))
        self.btn_add_finding.clicked.connect(self.add_finding_requested.emit)
        action_row.addWidget(self.btn_add_finding, stretch=1)

        self.btn_promote_finding = QPushButton(
            t("report.promote_loot_short", "Loot → Finding")
        )
        self.btn_promote_finding.setObjectName("btn_nav_promote_finding")
        self.btn_promote_finding.setProperty("class", "SecondaryBtn")
        self.btn_promote_finding.setToolTip(
            t(
                "report.promote_loot_tip",
                "Create a finding from one Loot entry and attach additional Loot as evidence",
            )
        )
        self.btn_promote_finding.setIcon(
            icon("fa5s.file-medical", color=get_theme_color("STATUS_SUCCESS"))
        )
        self.btn_promote_finding.clicked.connect(self.promote_finding_requested.emit)
        action_row.addWidget(self.btn_promote_finding, stretch=1)

        h_layout.addLayout(action_row)

        main_layout.addWidget(self.header_panel)

        # Tree navigation
        self.tree = QTreeWidget(self)
        self.tree.setObjectName("WorkspaceNavTree")
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        main_layout.addWidget(self.tree, stretch=1)

    def load_document(
        self,
        doc: ReportWorkspaceDocument,
        project_name: str = "",
        target_ip: str = "",
    ) -> None:
        self._doc = doc
        self._project_name = project_name
        self._target_ip = target_ip
        self.lbl_project.setText(project_name or t("report.workspace_no_project", "Kein Projekt"))
        scope_text = target_ip or doc.metadata.target_scope
        self.lbl_scope.setText(f"Scope: {scope_text}" if scope_text else "")

        self.tree.clear()

        nav_color = get_theme_color("CYBER_BLUE_LIGHT")
        accent_cyan = get_theme_color("CYBER_CYAN")

        readiness = assess_report_readiness(doc)
        if readiness.status == "incomplete":
            readiness_text = t(
                "report.readiness_nav_incomplete",
                "Readiness · {count} required",
                count=len(readiness.blockers),
            )
            readiness_icon = "fa5s.exclamation-circle"
            readiness_color = get_theme_color("STATUS_ERROR")
        elif readiness.status == "review":
            readiness_text = t(
                "report.readiness_nav_review",
                "Readiness · {count} to review",
                count=len(readiness.review_items),
            )
            readiness_icon = "fa5s.search"
            readiness_color = get_theme_color("STATUS_WARNING")
        else:
            readiness_text = t("report.readiness_nav_ready", "Readiness · Ready")
            readiness_icon = "fa5s.check-circle"
            readiness_color = get_theme_color("STATUS_SUCCESS")

        item_readiness = QTreeWidgetItem(self.tree)
        item_readiness.setText(0, readiness_text)
        item_readiness.setIcon(0, icon(readiness_icon, color=readiness_color))
        item_readiness.setData(0, Qt.ItemDataRole.UserRole, ("readiness", None))
        item_readiness.setToolTip(
            0,
            t(
                "report.readiness_nav_tip",
                "Review missing required fields and advisory items before export.",
            ),
        )

        # 1. Metadaten
        item_meta = QTreeWidgetItem(self.tree)
        item_meta.setText(0, t("report.section_metadata", "Metadata & Scope"))
        item_meta.setIcon(0, icon("fa5s.clipboard-list", color=nav_color))
        item_meta.setData(0, Qt.ItemDataRole.UserRole, ("metadata", None))

        # 2. Narrativ Sektionen
        item_narrative_root = QTreeWidgetItem(self.tree)
        item_narrative_root.setText(0, t("report.group_narrative", "Report Sections"))
        item_narrative_root.setIcon(0, icon("fa5s.book-open", color=nav_color))
        item_narrative_root.setData(0, Qt.ItemDataRole.UserRole, ("narratives_root", None))

        # Executive Summary
        item_exec = QTreeWidgetItem(item_narrative_root)
        item_exec.setText(0, t("report.section_exec_summary", "Executive Summary"))
        item_exec.setIcon(0, icon("fa5s.align-left", color=nav_color))
        item_exec.setData(0, Qt.ItemDataRole.UserRole, ("section", "executive_summary"))

        # Scope & Methodik
        item_scope = QTreeWidgetItem(item_narrative_root)
        item_scope.setText(0, t("report.section_scope", "Scope & Methodology"))
        item_scope.setIcon(0, icon("fa5s.bullseye", color=nav_color))
        item_scope.setData(0, Qt.ItemDataRole.UserRole, ("section", "scope_limitations"))

        # Angriffspfad
        item_attack = QTreeWidgetItem(item_narrative_root)
        item_attack.setText(0, t("report.section_attack_path", "Attack Path"))
        item_attack.setIcon(0, icon("fa5s.route", color=nav_color))
        item_attack.setData(0, Qt.ItemDataRole.UserRole, ("section", "attack_path"))

        item_narrative_root.setExpanded(True)

        # 3. Findings (Gruppiert nach Loot-Phasen)
        findings_count = len(doc.findings)
        item_findings_root = QTreeWidgetItem(self.tree)
        item_findings_root.setText(0, f"{t('report.group_findings', 'Findings (Loot / Findings)')} ({findings_count})")
        item_findings_root.setIcon(0, icon("fa5s.shield-alt", color=accent_cyan))
        item_findings_root.setData(0, Qt.ItemDataRole.UserRole, ("findings_overview", None))

        # Group findings by phase
        by_phase = doc.get_findings_by_phase()
        for phase_key, (phase_name, phase_icon, phase_color) in PHASE_META.items():
            phase_findings = by_phase.get(phase_key, [])
            if not phase_findings:
                continue

            localized_phase_name = t(f"phases.{phase_key}", phase_name)
            item_phase = QTreeWidgetItem(item_findings_root)
            item_phase.setText(0, f"{localized_phase_name} ({len(phase_findings)})")
            item_phase.setIcon(0, icon(phase_icon, color=phase_color))
            item_phase.setData(0, Qt.ItemDataRole.UserRole, ("phase_group", phase_key))

            for f in phase_findings:
                item_f = QTreeWidgetItem(item_phase)
                item_f.setText(0, f.title or t("report.finding_unnamed", "Untitled Finding"))
                sev = (f.severity or "medium").lower()
                ic_name = SEV_ICONS.get(sev, "fa5s.circle")
                color = SEV_COLORS.get(sev, "#d29922")
                item_f.setIcon(0, icon(ic_name, color=color))
                tooltip = f"[{sev.upper()}] {f.title}\nStatus: {f.status}\nPhase: {f.phase}"
                item_f.setToolTip(0, tooltip)
                item_f.setData(0, Qt.ItemDataRole.UserRole, ("finding", f.id))

            item_phase.setExpanded(False)

        # Catch any findings with unknown phase
        known_phases = set(PHASE_META.keys())
        other_findings = [f for f in doc.findings if normalize_phase_key(f.phase) not in known_phases]
        if other_findings:
            item_other = QTreeWidgetItem(item_findings_root)
            item_other.setText(0, t("report.phase_other", "Other ({count})", count=len(other_findings)))
            item_other.setIcon(0, icon("fa5s.folder", color="#8b949e"))
            item_other.setData(0, Qt.ItemDataRole.UserRole, ("phase_group", "misc"))
            for f in other_findings:
                item_f = QTreeWidgetItem(item_other)
                item_f.setText(0, f.title or t("report.finding_unnamed", "Untitled Finding"))
                sev = (f.severity or "medium").lower()
                item_f.setIcon(0, icon(SEV_ICONS.get(sev, "fa5s.circle"), color=SEV_COLORS.get(sev, "#d29922")))
                item_f.setData(0, Qt.ItemDataRole.UserRole, ("finding", f.id))
            item_other.setExpanded(False)

        item_findings_root.setExpanded(False)

        # 4. Remediation & Anhang
        item_remed = QTreeWidgetItem(self.tree)
        item_remed.setText(0, t("report.section_remediation", "Remediation & Action Plan"))
        item_remed.setIcon(0, icon("fa5s.tasks", color=nav_color))
        item_remed.setData(0, Qt.ItemDataRole.UserRole, ("section", "remediation_table"))

        item_appendix = QTreeWidgetItem(self.tree)
        item_appendix.setText(0, t("report.section_appendix", "Appendix & Evidence"))
        item_appendix.setIcon(0, icon("fa5s.paperclip", color=nav_color))
        item_appendix.setData(0, Qt.ItemDataRole.UserRole, ("section", "appendix"))

        # 5. Raw Markdown
        item_raw = QTreeWidgetItem(self.tree)
        item_raw.setText(0, t("report.section_raw_markdown", "Raw Markdown (Source)"))
        item_raw.setIcon(0, icon("fa5s.code", color=nav_color))
        item_raw.setData(0, Qt.ItemDataRole.UserRole, ("raw_markdown", None))

    def set_loot_sync_state(
        self,
        missing_count: int,
        stale_count: int = 0,
        orphaned_count: int = 0,
    ) -> None:
        """Show the relationship between project Loot and report markers."""
        parts = []
        if missing_count:
            parts.append(t("report.loot_sync_missing", "New: {count}", count=missing_count))
        if stale_count:
            parts.append(t("report.loot_sync_stale", "Changed: {count}", count=stale_count))
        if orphaned_count:
            parts.append(
                t("report.loot_sync_orphaned", "Report only: {count}", count=orphaned_count)
            )

        if missing_count:
            sync_state = "pending"
            tooltip = t(
                "report.loot_sync_pending_tip",
                "Add new Loot entries without overwriting existing report text.",
            )
        elif stale_count or orphaned_count:
            sync_state = "diverged"
            tooltip = t(
                "report.loot_sync_diverged_tip",
                "Existing report content is preserved; additive sync does not overwrite changed entries.",
            )
        else:
            sync_state = "current"
            tooltip = t(
                "report.loot_sync_current_tip",
                "All project Loot entries are represented in the report.",
            )

        self.lbl_sync_state.setText(
            " · ".join(parts) if parts else t("report.loot_sync_current", "Loot up to date")
        )
        self.lbl_sync_state.setProperty("syncState", sync_state)
        self.lbl_sync_state.setToolTip(tooltip)
        self.btn_sync_loot.setEnabled(missing_count > 0)
        self.btn_sync_loot.setToolTip(tooltip)
        self.lbl_sync_state.style().unpolish(self.lbl_sync_state)
        self.lbl_sync_state.style().polish(self.lbl_sync_state)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            view_type, item_id = data
            self.navigate_requested.emit(ReportLocation.from_legacy(view_type, item_id))

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.childCount() > 0:
            item.setExpanded(not item.isExpanded())
        else:
            self._on_item_clicked(item, _column)

    def select_item(self, view_type: str, item_id: Optional[str] = None) -> None:
        """Compatibility adapter for callers not yet using ReportLocation."""
        self.select_location(ReportLocation.from_legacy(view_type, item_id))

    def select_location(self, location: ReportLocation) -> None:
        """Select the tree item matching a semantic report location."""
        target = location.as_legacy_tuple()

        def search_node(parent_item: QTreeWidgetItem) -> bool:
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole) == target:
                    p: Optional[QTreeWidgetItem] = child.parent()
                    while p is not None:
                        p.setExpanded(True)
                        p = p.parent()
                    self.tree.setCurrentItem(child)
                    self.tree.scrollToItem(child)
                    return True
                if search_node(child):
                    return True
            return False

        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top.data(0, Qt.ItemDataRole.UserRole) == target:
                self.tree.setCurrentItem(top)
                return
            if search_node(top):
                return

    def refresh_theme(self) -> None:
        """Re-applies theme colors to navigation icons and header buttons."""
        self.btn_sync_loot.setIcon(icon("fa5s.sync-alt", color=get_theme_color("STATUS_SUCCESS")))
        self.btn_add_finding.setIcon(icon("fa5s.plus", color=get_theme_color("CYBER_CYAN")))
        if self._doc is not None:
            self.load_document(self._doc, self._project_name, self._target_ip)

    def changeEvent(self, event: Optional[QEvent]) -> None:
        super().changeEvent(event)
        if event is not None and event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self.refresh_theme()


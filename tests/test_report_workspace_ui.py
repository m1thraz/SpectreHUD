"""Tests for Report Workspace UI components (Navigator, Inspectors, and Tab integration)."""

import os
from pathlib import Path
import unittest

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLineEdit,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTreeWidget,
    QWidget,
)

from core.clipboard_history import ClipboardHistory
from core.i18n import get_i18n, t
from ui.controllers.window_frame_manager import is_interactive_widget
from core.loot import LootManager
from core.project import ProjectManager
from core.reporting import (
    AttackPathStep,
    ReportAppendix,
    ReportAttackPath,
    ReportEvidenceItem,
    ReportExecutiveSummary,
    ReportFileManager,
    ReportFindingItem,
    ReportMetadata,
    ReportRemediationPlan,
    ReportScopeMethodology,
    ReportWorkspaceDocument,
    ScopeExclusionItem,
    ScopeTargetItem,
    assess_report_readiness,
)
from ui.report.dialogs import (
    ClipboardHistoryPickerDialog,
    LootEntryPickerDialog,
)
from ui.report.finding_inspector import ReportEvidenceCard, ReportFindingInspector
from ui.report.metadata_inspector import ReportMetadataInspector
from ui.report.readiness_inspector import ReportReadinessInspector
from ui.report.section_inspector import ReportSectionInspector
from ui.report.summary_inspector import ReportSummaryInspector
from ui.report.remediation_inspector import ReportRemediationInspector
from ui.report.attack_path_inspector import ReportAttackPathInspector
from ui.report.scope_inspector import ReportScopeInspector
from ui.report.appendix_inspector import CommandSnippetCard, ReportAppendixInspector, ScreenshotCard
from ui.report.workspace_navigator import ReportWorkspaceNavigator
from ui.report.navigation import ReportLocation, ReportLocationKind
from ui.report_editor_tab import ReportEditorTab, ViewMode

pytestmark = pytest.mark.integration


class TestReportWorkspaceUI(unittest.TestCase):
    def setUp(self):
        self.temp_path = Path(os.environ["SPECTRE_CONFIG_DIR"]).parent
        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.project_mgr.create_project("WorkspaceBox", target_ip="192.168.1.100")
        self.loot_mgr = LootManager(storage_file=self.temp_path / "config" / "loot.json")
        self.clip_watcher = ClipboardHistory(storage_file=self.temp_path / "config" / "clip.json")
        self.report_file_mgr = ReportFileManager(self.project_mgr)

    def test_workspace_navigator_population_and_selection(self):
        nav = ReportWorkspaceNavigator()
        doc = ReportWorkspaceDocument(
            metadata=ReportMetadata(client="TestCorp", target_scope="192.168.1.0/24"),
            findings=[
                ReportFindingItem(id="f1", title="SQLi", severity="critical", phase="access"),
                ReportFindingItem(id="f2", title="Open Port", severity="info", phase="recon"),
            ],
        )
        nav.load_document(doc, project_name="WorkspaceBox", target_ip="192.168.1.100")

        self.assertIn("WorkspaceBox", nav.lbl_project.text())
        self.assertIn("192.168.1.100", nav.lbl_scope.text())

        # Check tree nodes
        tree = nav.tree
        self.assertGreaterEqual(tree.topLevelItemCount(), 4)

        item_readiness = tree.topLevelItem(0)
        self.assertEqual(item_readiness.data(0, Qt.ItemDataRole.UserRole), ("readiness", None))
        self.assertIn("6", item_readiness.text(0))

        # Metadata follows the completion overview.
        item_meta = tree.topLevelItem(1)
        self.assertEqual(item_meta.data(0, Qt.ItemDataRole.UserRole), ("metadata", None))

        # Check signal emission on click
        clicked_events = []
        nav.navigate_requested.connect(
            lambda location: clicked_events.append(location.as_legacy_tuple())
        )
        nav._on_item_clicked(item_meta, 0)
        self.assertEqual(clicked_events, [("metadata", None)])

        # Check Add Finding button signal
        add_clicked = []
        nav.add_finding_requested.connect(lambda: add_clicked.append(True))
        nav.btn_add_finding.click()
        self.assertEqual(add_clicked, [True])

    def test_workspace_navigator_theme_dependent_icon_colors(self):
        """Verify that navigator section items use theme-dependent accent colors (e.g. violet on Dracula)."""
        from core.theme_loader import ThemeLoader
        from ui.styles.icons import get_theme_color, set_icon_palette

        theme_loader = ThemeLoader()
        cyber_palette = theme_loader.load_theme("cyber_dark")
        dracula_palette = theme_loader.load_theme("dracula")

        # Start on cyber dark
        set_icon_palette(cyber_palette)
        self.assertEqual(get_theme_color("CYBER_BLUE_LIGHT"), "#79c0ff")

        nav = ReportWorkspaceNavigator()
        doc = ReportWorkspaceDocument(
            metadata=ReportMetadata(client="TestCorp"),
            findings=[ReportFindingItem(id="f1", title="SQLi", severity="high", phase="access")],
        )
        nav.load_document(doc, project_name="Box", target_ip="10.10.10.10")

        # Verify initial load creates valid icons
        self.assertFalse(nav.tree.topLevelItem(0).icon(0).isNull())

        # Switch to Dracula theme (violet accent)
        set_icon_palette(dracula_palette)
        self.assertEqual(get_theme_color("CYBER_BLUE_LIGHT"), "#d6b3ff")

        # Refresh theme updates navigator icons
        nav.refresh_theme()
        self.assertFalse(nav.tree.topLevelItem(0).icon(0).isNull())

        # Cleanup: restore cyber dark
        set_icon_palette(cyber_palette)

    def test_workspace_navigator_enumeration_loot_grouping(self):
        """Verify that enumeration and German recon findings are categorized under Recon, never under Others."""
        nav = ReportWorkspaceNavigator()
        doc = ReportWorkspaceDocument(
            findings=[
                ReportFindingItem(id="e1", title="Nmap Scan", phase="enumeration"),
                ReportFindingItem(id="e2", title="Service Discovery", phase="Service Enumeration"),
                ReportFindingItem(id="e3", title="Port Enum", phase="Reconnaissance & Enumeration"),
                ReportFindingItem(id="e4", title="Web Enum", phase="Aufklärung & Enumeration"),
            ]
        )
        nav.load_document(doc, project_name="WorkspaceBox", target_ip="192.168.1.100")

        tree = nav.tree
        # Find Findings root item
        item_findings_root = None
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            role_data = it.data(0, Qt.ItemDataRole.UserRole)
            if role_data and role_data[0] == "findings_overview":
                item_findings_root = it
                break

        self.assertIsNotNone(item_findings_root)
        self.assertEqual(item_findings_root.childCount(), 1)  # Only Recon phase group!

        recon_child = item_findings_root.child(0)
        self.assertEqual(recon_child.data(0, Qt.ItemDataRole.UserRole), ("phase_group", "recon"))
        self.assertEqual(recon_child.childCount(), 4)

        # Ensure no 'other' group exists
        child_roles = [
            item_findings_root.child(j).data(0, Qt.ItemDataRole.UserRole)
            for j in range(item_findings_root.childCount())
        ]
        self.assertNotIn(("phase_group", "misc"), child_roles)

        # Ensure findings root and phase groups are collapsed by default
        self.assertFalse(item_findings_root.isExpanded())
        self.assertFalse(recon_child.isExpanded())

        # When select_item is called on a finding, parent hierarchy auto-expands
        finding_id = recon_child.child(0).data(0, Qt.ItemDataRole.UserRole)[1]
        nav.select_item("finding", finding_id)
        self.assertTrue(item_findings_root.isExpanded())
        self.assertTrue(recon_child.isExpanded())

    def test_metadata_inspector_edits(self):
        insp = ReportMetadataInspector()
        meta = ReportMetadata(
            title="Old Title",
            client="Old Client",
            tester="Old Tester",
            target_scope="10.0.0.1",
            version="v1.0",
        )
        insp.load_metadata(meta)
        self.assertEqual(insp.txt_client.text(), "Old Client")

        changed = []
        insp.metadata_changed.connect(lambda m: changed.append(m))

        insp.txt_client.setText("New Client AG")
        # Flush debounce timer
        insp._debounce_timer.timeout.emit()

        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0].client, "New Client AG")

    def test_all_inspectors_share_header_and_section_style_roles(self):
        inspectors = [
            ReportMetadataInspector(),
            ReportFindingInspector(),
            ReportSectionInspector(),
            ReportSummaryInspector(),
            ReportRemediationInspector(),
            ReportAttackPathInspector(),
            ReportScopeInspector(),
            ReportAppendixInspector(),
            ReportReadinessInspector(),
        ]
        try:
            for inspector in inspectors:
                self.assertIn(
                    "ReportInspectorHeader",
                    str(inspector.header_card.property("class") or "").split(),
                )
                self.assertIn(
                    "ReportInspectorTitle",
                    str(inspector.lbl_title.property("class") or "").split(),
                )
                self.assertEqual(inspector.lbl_title.styleSheet(), "")

            for inspector in inspectors[3:]:
                section_cards = [
                    child
                    for child in inspector.findChildren(QWidget)
                    if "ReportInspectorSection" in str(child.property("class") or "").split()
                ]
                self.assertTrue(section_cards, inspector.objectName())
        finally:
            for inspector in inspectors:
                inspector.deleteLater()

    def test_readiness_inspector_groups_issues_and_navigates(self):
        document = ReportWorkspaceDocument(
            metadata=ReportMetadata(client="Example", target_scope="10.10.10.42"),
            findings=[
                ReportFindingItem(
                    id="finding-1",
                    title="Exposed service",
                    description="Service is reachable.",
                )
            ],
        )
        inspector = ReportReadinessInspector()
        inspector.load_assessment(assess_report_readiness(document))

        self.assertEqual(inspector.lbl_status.property("readinessState"), "incomplete")
        self.assertEqual(inspector.lbl_findings.text(), "1")
        self.assertEqual(inspector.lbl_open.text(), "1")
        self.assertEqual(inspector.lbl_evidence.text(), "0")

        issue_buttons = [
            button
            for button in inspector.findChildren(QPushButton)
            if "ReadinessIssueBtn" in str(button.property("class") or "").split()
        ]
        self.assertEqual(len(issue_buttons), 5)
        blocker_buttons = [
            button for button in issue_buttons if button.property("readinessLevel") == "blocker"
        ]
        self.assertEqual(len(blocker_buttons), 3)

        navigated = []
        inspector.navigate_requested.connect(
            lambda location: navigated.append(location.as_legacy_tuple())
        )
        blocker_buttons[0].click()
        self.assertEqual(navigated[0][0], "metadata")

        inspector.deleteLater()

    def test_finding_inspector_edits_and_actions(self):
        insp = ReportFindingInspector()
        finding = ReportFindingItem(
            id="f-42",
            title="Broken Auth",
            severity="high",
            phase="access",
            status="open",
            description="JWT not verified",
            recommendation="Verify signature",
        )
        insp.load_finding(finding)
        self.assertEqual(insp.txt_title.text(), "Broken Auth")
        self.assertEqual(insp.cmb_severity.currentData(), "high")

        changed = []
        deleted = []
        duplicated = []
        insp.finding_changed.connect(lambda f: changed.append(f))
        insp.finding_deleted.connect(lambda fid: deleted.append(fid))
        insp.finding_duplicated.connect(lambda fid: duplicated.append(fid))

        insp.txt_title.setText("Broken JWT Auth")
        insp._debounce_timer.timeout.emit()
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0].title, "Broken JWT Auth")

        insp.btn_duplicate.click()
        self.assertEqual(duplicated, ["f-42"])

        insp.btn_delete.click()
        self.assertEqual(deleted, ["f-42"])

    def test_section_inspector_edits(self):
        insp = ReportSectionInspector()
        insp.load_section(
            identity="executive_summary",
            title="Executive Summary",
            content="Initial content",
        )
        self.assertEqual(insp.editor.toPlainText(), "Initial content")

        changed = []
        insp.section_changed.connect(lambda ident, text: changed.append((ident, text)))

        insp.editor.setPlainText("Updated summary text")
        insp._debounce_timer.timeout.emit()
        self.assertEqual(changed, [("executive_summary", "Updated summary text")])

    def test_report_editor_tab_workspace_integration(self):
        tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        tab.load_project("WorkspaceBox")
        tab.show()

        # Workspace is the primary report view with structured editing and preview.
        self.assertEqual(tab.view_mode, ViewMode.WORKSPACE)
        self.assertTrue(tab.workspace_shell.navigator_glass.isVisible())
        self.assertTrue(tab.workspace_shell.center_stack.isVisible())
        self.assertTrue(tab.workspace_shell.preview.isVisible())
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.metadata_inspector_glass,
        )
        self.assertTrue(tab.format_toolbar_widget.isHidden())
        self.assertTrue(tab.action_toolbar.view_actions[ViewMode.WORKSPACE].isChecked())

        # Add a finding through the workspace handler
        assert tab.workspace_document is not None
        initial_finding_count = len(tab.workspace_document.findings)
        tab.add_finding()
        self.assertEqual(len(tab.workspace_document.findings), initial_finding_count + 1)
        self.assertIn(
            t("report.new_finding_default_title", "New Finding"),
            tab.workspace_shell.editor.toPlainText(),
        )
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.finding_inspector_glass,
        )
        new_finding = tab.workspace_document.findings[-1]
        self.assertEqual(
            tab.workspace_shell.navigator.tree.currentItem().data(0, Qt.ItemDataRole.UserRole),
            ("finding", new_finding.id),
        )
        self.assertIn(new_finding.title, tab.workspace_shell.preview.textCursor().block().text())

        tab.duplicate_finding(new_finding.id)
        duplicated = tab.workspace_document.findings[-1]
        self.assertEqual(
            tab.workspace_shell.navigator.tree.currentItem().data(0, Qt.ItemDataRole.UserRole),
            ("finding", duplicated.id),
        )
        self.assertIn(duplicated.title, tab.workspace_shell.preview.textCursor().block().text())

        tab.delete_finding(duplicated.id)
        self.assertIsNone(tab.workspace_document.get_finding(duplicated.id))
        self.assertEqual(
            tab.workspace_shell.navigator.tree.currentItem().data(0, Qt.ItemDataRole.UserRole),
            ("finding", new_finding.id),
        )

        # Navigate to metadata
        tab.navigate_to(ReportLocation(ReportLocationKind.METADATA))
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.metadata_inspector_glass,
        )

        tab.navigate_to(ReportLocation(ReportLocationKind.READINESS))
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.readiness_inspector_glass,
        )
        self.assertEqual(
            tab.workspace_shell.navigator.tree.currentItem().data(0, Qt.ItemDataRole.UserRole),
            ("readiness", None),
        )

        # Navigate back to raw markdown
        tab.navigate_to(ReportLocation(ReportLocationKind.RAW_MARKDOWN))
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(), tab.workspace_shell.editor_glass
        )
        self.assertFalse(tab.format_toolbar_widget.isHidden())

        # When findings is empty, navigating to findings_overview displays finding_inspector_glass (empty state), NOT raw editor
        tab.workspace_document.findings.clear()
        tab.navigate_to(ReportLocation(ReportLocationKind.FINDINGS_OVERVIEW))
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.finding_inspector_glass,
        )
        self.assertIsNone(tab.workspace_shell.finding_inspector._finding)
        self.assertEqual(
            tab.workspace_shell.finding_inspector._stack.currentWidget(),
            tab.workspace_shell.finding_inspector.empty_widget,
        )

        tab.close()
        tab.deleteLater()

    def test_workspace_navigation_uses_semantic_preview_landmarks(self):
        tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        tab.load_project("WorkspaceBox")
        markdown = """<!-- spectre:section:start:header_metadata -->
# Shared Heading
<!-- spectre:section:end:header_metadata -->

<!-- spectre:section:start:executive_summary -->
## Shared Heading
<!-- spectre:section:end:executive_summary -->

<!-- spectre:section:start:appendix -->
## Shared Heading
Appendix body
<!-- spectre:section:end:appendix -->
"""
        tab.workspace_shell.editor.setPlainText(markdown)
        tab.replace_markdown(markdown)
        tab.sync_workspace_from_markdown()
        tab.refresh_preview()

        tab.navigate_to(ReportLocation(ReportLocationKind.SECTION, "appendix"))

        appendix_target = ("section", "appendix")
        self.assertEqual(tab.preview_controller.active_target, appendix_target)
        self.assertEqual(
            tab.workspace_shell.preview.textCursor().position(),
            tab.preview_controller.landmarks[appendix_target],
        )
        self.assertGreater(
            tab.preview_controller.landmarks[appendix_target],
            tab.preview_controller.landmarks[("section", "executive_summary")],
        )
        self.assertEqual(len(tab.workspace_shell.preview.extraSelections()), 1)
        self.assertNotIn("SPECTRE_NAV_PREVIEW_", tab.workspace_shell.preview.toPlainText())

        tab.refresh_preview()
        self.assertEqual(
            tab.workspace_shell.preview.textCursor().position(),
            tab.preview_controller.landmarks[appendix_target],
        )
        self.assertEqual(len(tab.workspace_shell.preview.extraSelections()), 1)

        tab.navigate_to(ReportLocation(ReportLocationKind.RAW_MARKDOWN))
        self.assertIsNone(tab.preview_controller.active_target)
        self.assertEqual(tab.workspace_shell.preview.extraSelections(), [])

        tab.close()
        tab.deleteLater()

    def test_finding_inspector_empty_state_and_signals(self):
        insp = ReportFindingInspector()
        # Default state is empty state
        self.assertIsNone(insp._finding)
        self.assertEqual(insp._stack.currentWidget(), insp.empty_widget)

        created = []
        synced = []
        insp.request_create_finding.connect(lambda: created.append(True))
        insp.request_loot_sync.connect(lambda: synced.append(True))

        insp.btn_empty_create.click()
        self.assertEqual(created, [True])

        insp.btn_empty_sync.click()
        self.assertEqual(synced, [True])

        # Loading finding switches to editor widget
        f = ReportFindingItem(id="f-1", title="Test Finding")
        insp.load_finding(f)
        self.assertEqual(insp._stack.currentWidget(), insp.editor_widget)
        self.assertEqual(insp.txt_title.text(), "Test Finding")

        # Loading None switches back to empty state
        insp.load_finding(None)
        self.assertIsNone(insp._finding)
        self.assertEqual(insp._stack.currentWidget(), insp.empty_widget)

    def test_finding_inspector_evidence_drawer_and_cards(self):
        insp = ReportFindingInspector()
        insp.set_project_target_ip("10.10.10.42")
        insp.btn_apply_target.click()
        self.assertEqual(insp.txt_target.text(), "10.10.10.42")

        finding = ReportFindingItem(
            id="f-100",
            title="Evidence Test Finding",
            description="Initial text.",
        )
        insp.load_finding(finding)
        self.assertEqual(insp.lbl_evidence_count.text(), "(0)")

        # Attach a screenshot evidence item
        sc_item = ReportEvidenceItem(
            id="ev-sc-1",
            type="screenshot",
            caption="Proof Screenshot",
            content="screenshots/proof.png",
        )
        insp.attach_evidence_item(sc_item, insert_into_description=True)
        self.assertEqual(insp.lbl_evidence_count.text(), "(1)")
        self.assertIn("![Proof Screenshot](screenshots/proof.png)", insp.txt_desc.toPlainText())

        # Check evidence card exists
        card = insp.evidence_container.findChild(ReportEvidenceCard)
        self.assertIsNotNone(card)
        self.assertEqual(card.txt_caption.text(), "Proof Screenshot")

        # Edit caption via card
        card.txt_caption.setText("Updated Proof")
        self.assertEqual(insp._finding.evidence_items[0].caption, "Updated Proof")
        self.assertIn("![Updated Proof](screenshots/proof.png)", insp.txt_desc.toPlainText())

        # Attach terminal code
        insp._on_add_code_clicked()
        self.assertEqual(insp.lbl_evidence_count.text(), "(2)")
        self.assertIn("```", insp.txt_desc.toPlainText())

        # Delete evidence card
        card._on_caption_edited("Updated Proof")
        insp._on_delete_evidence("ev-sc-1")
        self.assertEqual(insp.lbl_evidence_count.text(), "(1)")
        self.assertNotIn("screenshots/proof.png", insp.txt_desc.toPlainText())

        insp.deleteLater()

    def test_loot_entry_picker_dialog(self):
        entries = [
            {
                "id": "loot-1",
                "type": "credential",
                "category": "creds",
                "title": "Admin Password",
                "content": "admin:SuperSecret123",
                "target_ip": "10.10.10.5",
                "severity": "high",
                "timestamp": "2026-09-12 12:00",
            },
            {
                "id": "loot-2",
                "type": "flag",
                "category": "flag",
                "title": "Root Flag",
                "content": "HTB{root_flag_here}",
                "target_ip": "10.10.10.5",
                "severity": "info",
                "timestamp": "2026-09-12 12:30",
            },
        ]
        dialog = LootEntryPickerDialog(entries)
        dialog.show()

        self.assertEqual(dialog.list_widget.count(), 2)
        self.assertIsNotNone(dialog.selected_entry)
        self.assertEqual(dialog.selected_entry["id"], "loot-1")
        self.assertIn("admin:SuperSecret123", dialog.txt_preview.toPlainText())

        # Filter by category
        dialog.cmb_category.setCurrentIndex(dialog.cmb_category.findData("flag"))
        self.assertEqual(dialog.list_widget.count(), 1)
        self.assertEqual(dialog.selected_entry["id"], "loot-2")

        dialog.accept()
        dialog.deleteLater()

    def test_clipboard_history_picker_dialog(self):
        history = [
            {
                "id": "clip-1",
                "text": "nmap -sC -sV -p- 10.10.10.5\nStarting Nmap 7.94...",
                "target_ip": "10.10.10.5",
                "timestamp": "2026-09-12 10:00",
            },
            {
                "id": "clip-2",
                "text": "cat /etc/passwd\nroot:x:0:0:root:/root:/bin/bash",
                "target_ip": "10.10.10.5",
                "timestamp": "2026-09-12 10:30",
            },
        ]
        dialog = ClipboardHistoryPickerDialog(history)
        dialog.show()

        self.assertEqual(dialog.list_widget.count(), 2)
        self.assertIsNotNone(dialog.selected_entry)
        self.assertEqual(dialog.selected_entry["id"], "clip-1")
        self.assertIn("Starting Nmap", dialog.txt_preview.toPlainText())

        # Filter by search
        dialog.search_edit.setText("passwd")
        self.assertEqual(dialog.list_widget.count(), 1)
        self.assertEqual(dialog.selected_entry["id"], "clip-2")

        dialog.accept()
        dialog.deleteLater()

    def test_window_frame_manager_interactive_widgets(self):
        from PyQt6.QtWidgets import QSplitter, QTextEdit

        tree = QTreeWidget()
        list_widget = QListWidget()
        table = QTableWidget()
        header = tree.header()
        splitter = QSplitter()
        splitter.addWidget(QTextEdit())
        splitter.addWidget(QTextEdit())
        handle = splitter.handle(1)

        self.assertTrue(is_interactive_widget(tree))
        self.assertTrue(is_interactive_widget(list_widget))
        self.assertTrue(is_interactive_widget(table))
        self.assertTrue(is_interactive_widget(header))
        self.assertTrue(is_interactive_widget(handle))
        tree.deleteLater()
        list_widget.deleteLater()
        table.deleteLater()
        splitter.deleteLater()

    def test_navigator_grouping_by_loot_phases(self):
        nav = ReportWorkspaceNavigator()
        doc = ReportWorkspaceDocument(
            findings=[
                ReportFindingItem(id="f1", title="Nmap Scan", severity="info", phase="recon"),
                ReportFindingItem(id="f2", title="SSH Bruteforce", severity="high", phase="access"),
                ReportFindingItem(
                    id="f3", title="Kernel Exploit", severity="critical", phase="privesc"
                ),
            ]
        )
        nav.load_document(doc)

        findings_root = next(
            nav.tree.topLevelItem(index)
            for index in range(nav.tree.topLevelItemCount())
            if nav.tree.topLevelItem(index).data(0, Qt.ItemDataRole.UserRole)
            == ("findings_overview", None)
        )
        self.assertIn("Loot", findings_root.text(0))

        phase_keys = [
            findings_root.child(i).data(0, Qt.ItemDataRole.UserRole)[1]
            for i in range(findings_root.childCount())
        ]
        self.assertIn("recon", phase_keys)
        self.assertIn("access", phase_keys)
        self.assertIn("privesc", phase_keys)

        recon_item = next(
            findings_root.child(i)
            for i in range(findings_root.childCount())
            if findings_root.child(i).data(0, Qt.ItemDataRole.UserRole)[1] == "recon"
        )
        self.assertEqual(recon_item.childCount(), 1)
        self.assertEqual(recon_item.child(0).text(0), "Nmap Scan")

        sync_called = []
        nav.sync_loot_requested.connect(lambda: sync_called.append(True))
        nav.btn_sync_loot.click()
        self.assertEqual(sync_called, [True])

        nav.set_loot_sync_state(2, 1, 0)
        self.assertEqual(nav.lbl_sync_state.property("syncState"), "pending")
        self.assertIn("2", nav.lbl_sync_state.text())
        self.assertIn("1", nav.lbl_sync_state.text())
        self.assertTrue(nav.btn_sync_loot.isEnabled())

        nav.set_loot_sync_state(0, 1, 1)
        self.assertEqual(nav.lbl_sync_state.property("syncState"), "diverged")
        self.assertFalse(nav.btn_sync_loot.isEnabled())

        nav.set_loot_sync_state(0, 0, 0)
        self.assertEqual(nav.lbl_sync_state.property("syncState"), "current")
        self.assertIn("Loot", nav.lbl_sync_state.text())
        nav.deleteLater()

    def test_report_editor_tab_collapsible_navigator_and_raw_toggle(self):
        tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        tab.load_project("WorkspaceBox")
        tab.show()
        tab.set_view_mode(ViewMode.SPLIT)

        # In Split view, navigator starts hidden for 2-column layout
        self.assertFalse(tab.workspace_shell.navigator_glass.isVisible())
        self.assertFalse(tab.action_toolbar.btn_navigator.isChecked())

        # Toggle on demand
        tab.action_toolbar.btn_navigator.click()
        self.assertTrue(tab.workspace_shell.navigator_glass.isVisible())
        self.assertTrue(tab.action_toolbar.btn_navigator.isChecked())

        # Toggle off
        tab.action_toolbar.btn_navigator.click()
        self.assertFalse(tab.workspace_shell.navigator_glass.isVisible())
        self.assertFalse(tab.action_toolbar.btn_navigator.isChecked())

        # Toggle raw markdown vs inspector
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(), tab.workspace_shell.editor_glass
        )
        tab.action_toolbar.btn_toggle_raw.click()
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.metadata_inspector_glass,
        )
        tab.action_toolbar.btn_toggle_raw.click()
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(), tab.workspace_shell.editor_glass
        )

        tab.close()
        tab.deleteLater()

    def test_workspace_translations_de_en(self):
        i18n = get_i18n()
        saved_locale = i18n.current_locale

        try:
            # Test English translations
            i18n.set_locale("en")
            self.assertEqual(t("report.new_finding_default_title"), "New Finding")
            self.assertEqual(t("report.navigator"), "Navigator")
            self.assertEqual(t("report.section_metadata"), "Metadata & Scope")
            self.assertEqual(t("report.inspector_finding_title"), "Finding Details")
            self.assertEqual(t("report.finding_desc"), "Description & Proof of Concept")

            # Test German translations
            i18n.set_locale("de")
            self.assertEqual(t("report.new_finding_default_title"), "Neue Schwachstelle")
            self.assertEqual(t("report.navigator"), "Navigator")
            self.assertEqual(t("report.section_metadata"), "Metadaten & Scope")
            self.assertEqual(t("report.inspector_finding_title"), "Schwachstellen-Details")
            self.assertEqual(t("report.finding_desc"), "Beschreibung & Proof of Concept")
        finally:
            i18n.set_locale(saved_locale)

    def test_summary_inspector_ui_and_interactions(self):
        inspector = ReportSummaryInspector()

        f1 = ReportFindingItem(
            id="f-1",
            title="Sudo NOPASSWD /usr/bin/less",
            severity="CRITICAL",
            phase="privesc",
            status="Open",
        )
        f2 = ReportFindingItem(
            id="f-2",
            title="FTP Anonymous Access",
            severity="HIGH",
            phase="recon",
            status="Resolved",
        )
        doc = ReportWorkspaceDocument(
            metadata=ReportMetadata(),
            findings=[f1, f2],
        )
        summary = ReportExecutiveSummary(
            intro_text="Executive summary intro text.",
            initial_access="Phishing vector",
            privilege_escalation="Sudo misconfiguration",
            business_impact="Full domain compromise",
            remediation_summary="Patch sudoers and restrict FTP",
        )
        doc.set_executive_summary(summary)

        inspector.load_summary(doc)

        # Check posture and scorecard pills
        self.assertIn("CRITICAL", inspector.lbl_posture_val.text())
        self.assertIn("1", inspector.pill_crit.text())
        self.assertIn("1", inspector.pill_high.text())
        self.assertIn("0", inspector.pill_med.text())
        self.assertIn("2 Total", inspector.lbl_status_val.text())
        self.assertIn("1 Open", inspector.lbl_status_val.text())
        self.assertIn("1 Remediated", inspector.lbl_status_val.text())

        # Check table contents
        self.assertEqual(inspector.tbl_matrix.rowCount(), 2)
        item_title = inspector.tbl_matrix.item(0, 2)
        self.assertIsNotNone(item_title)
        self.assertEqual(item_title.text(), "Sudo NOPASSWD /usr/bin/less")

        # Check text inputs
        self.assertEqual(inspector.txt_intro.toPlainText(), "Executive summary intro text.")
        self.assertEqual(inspector.txt_initial_access.toPlainText(), "Phishing vector")
        self.assertEqual(inspector.txt_privesc.toPlainText(), "Sudo misconfiguration")
        self.assertEqual(inspector.txt_business_impact.toPlainText(), "Full domain compromise")
        self.assertEqual(inspector.txt_remediation.toPlainText(), "Patch sudoers and restrict FTP")

        # Check signals
        selected_finding_ids = []
        inspector.finding_selected.connect(selected_finding_ids.append)
        inspector.tbl_matrix.cellDoubleClicked.emit(0, 2)
        self.assertEqual(selected_finding_ids, ["f-1"])

        changes = []
        inspector.summary_changed.connect(changes.append)
        inspector.txt_initial_access.setPlainText("Updated vector")
        inspector._debounce_timer.stop()
        inspector._emit_changed()
        self.assertTrue(len(changes) > 0)
        self.assertEqual(changes[-1].initial_access, "Updated vector")

        inspector.close()
        inspector.deleteLater()

    def test_report_editor_tab_summary_navigation(self):
        tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        tab.load_project("WorkspaceBox")

        f1 = ReportFindingItem(
            id="f-test-1",
            title="Test Finding 1",
            severity="HIGH",
            phase="privesc",
            status="Open",
        )
        assert tab.workspace_document is not None
        tab.workspace_document.findings.append(f1)
        tab.apply_workspace_document()

        # Navigate to executive summary section
        tab.navigate_to(ReportLocation(ReportLocationKind.SECTION, "executive_summary"))
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.summary_inspector_glass,
        )
        self.assertEqual(tab.workspace_shell.summary_inspector.tbl_matrix.rowCount(), 1)

        # Click navigation from summary matrix to finding
        tab.workspace_shell.summary_inspector.finding_selected.emit("f-test-1")
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.finding_inspector_glass,
        )
        self.assertEqual(tab.workspace_shell.finding_inspector._finding.id, "f-test-1")

        tab.close()
        tab.deleteLater()

    def test_remediation_inspector_ui_and_interactions(self):
        inspector = ReportRemediationInspector()

        f1 = ReportFindingItem(
            id="f-med",
            title="FTP Anonymous Access",
            severity="medium",
            phase="recon",
            status="open",
            recommendation="Disable anonymous access",
        )
        f2 = ReportFindingItem(
            id="f-crit",
            title="Sudo NOPASSWD /usr/bin/less",
            severity="critical",
            phase="privesc",
            status="open",
            recommendation="Remove sudoers rule",
        )
        f3 = ReportFindingItem(
            id="f-high",
            title="Outdated Web Server",
            severity="high",
            phase="access",
            status="resolved",
            recommendation="Update nginx package",
        )

        plan = ReportRemediationPlan(
            title="Remediation & Maßnahmenplan",
            strategic_guidance="Prioritize external perimeter patches.",
        )
        doc = ReportWorkspaceDocument(
            metadata=ReportMetadata(),
            findings=[f1, f2, f3],
        )
        doc.set_remediation_plan(plan)

        inspector.load_remediation(doc)

        # Check title and guidance
        self.assertEqual(inspector.lbl_title.text(), "Remediation & Maßnahmenplan")
        self.assertEqual(
            inspector.txt_guidance.toPlainText(), "Prioritize external perimeter patches."
        )

        # Check progress badge (1 of 3 resolved = 33%)
        self.assertIn("1 / 3 Resolved", inspector.lbl_progress_badge.text())

        # Check priority sorting: Critical is row 0, High is row 1, Medium is row 2
        self.assertEqual(inspector.tbl_actions.rowCount(), 3)
        item_sev_row0 = inspector.tbl_actions.item(0, 0)
        self.assertEqual(item_sev_row0.text(), "CRITICAL")
        self.assertEqual(item_sev_row0.data(Qt.ItemDataRole.UserRole), "f-crit")

        item_sev_row1 = inspector.tbl_actions.item(1, 0)
        self.assertEqual(item_sev_row1.text(), "HIGH")
        self.assertEqual(item_sev_row1.data(Qt.ItemDataRole.UserRole), "f-high")

        item_sev_row2 = inspector.tbl_actions.item(2, 0)
        self.assertEqual(item_sev_row2.text(), "MEDIUM")
        self.assertEqual(item_sev_row2.data(Qt.ItemDataRole.UserRole), "f-med")

        # Check filter buttons
        inspector.btn_filter_open.click()
        self.assertEqual(inspector.tbl_actions.rowCount(), 2)

        inspector.btn_filter_resolved.click()
        self.assertEqual(inspector.tbl_actions.rowCount(), 1)
        self.assertEqual(inspector.tbl_actions.item(0, 0).text(), "HIGH")

        inspector.btn_filter_all.click()
        self.assertEqual(inspector.tbl_actions.rowCount(), 3)

        # Test in-place editing of recommendation
        action_events = []
        inspector.finding_action_changed.connect(
            lambda fid, rec, st: action_events.append((fid, rec, st))
        )

        edit_action = inspector.tbl_actions.cellWidget(0, 2)
        self.assertIsNotNone(edit_action)
        self.assertEqual(edit_action.text(), "Remove sudoers rule")
        edit_action.setText("Remove sudoers rule immediately")
        edit_action.editingFinished.emit()

        self.assertEqual(len(action_events), 1)
        self.assertEqual(action_events[0], ("f-crit", "Remove sudoers rule immediately", "open"))

        # Test status combo change
        cmb_status = inspector.tbl_actions.cellWidget(0, 3)
        self.assertIsNotNone(cmb_status)
        resolved_idx = cmb_status.findData("resolved")
        self.assertGreaterEqual(resolved_idx, 0)
        cmb_status.setCurrentIndex(resolved_idx)

        self.assertEqual(len(action_events), 2)
        self.assertEqual(
            action_events[1], ("f-crit", "Remove sudoers rule immediately", "resolved")
        )
        self.assertIn("2 / 3 Resolved", inspector.lbl_progress_badge.text())

        # Test double-click jumps to finding
        selected_findings = []
        inspector.finding_selected.connect(selected_findings.append)
        inspector.tbl_actions.cellDoubleClicked.emit(0, 0)
        self.assertEqual(selected_findings, ["f-crit"])

        inspector.close()
        inspector.deleteLater()

    def test_report_editor_tab_remediation_navigation(self):
        tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        tab.load_project("WorkspaceBox")

        f1 = ReportFindingItem(
            id="f-action-test",
            title="Action Test Finding",
            severity="HIGH",
            phase="privesc",
            status="open",
            recommendation="Test action",
        )
        assert tab.workspace_document is not None
        tab.workspace_document.findings.append(f1)
        tab.apply_workspace_document()

        # Navigate to remediation table section
        tab.navigate_to(ReportLocation(ReportLocationKind.SECTION, "remediation_table"))
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.remediation_inspector_glass,
        )
        self.assertEqual(tab.workspace_shell.remediation_inspector.tbl_actions.rowCount(), 1)

        # Click navigation from remediation table to finding details
        tab.workspace_shell.remediation_inspector.finding_selected.emit("f-action-test")
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.finding_inspector_glass,
        )
        self.assertEqual(tab.workspace_shell.finding_inspector._finding.id, "f-action-test")

        tab.close()
        tab.deleteLater()

    def test_attack_path_inspector_ui_and_interactions(self):
        inspector = ReportAttackPathInspector()

        f1 = ReportFindingItem(
            id="f-probe",
            title="Initial Access via Probe Script",
            severity="high",
            phase="access",
            status="open",
        )
        f2 = ReportFindingItem(
            id="f-priv",
            title="Sudo NOPASSWD /usr/bin/less",
            severity="critical",
            phase="privesc",
            status="open",
        )

        path = ReportAttackPath(
            title="Angriffspfad / Assessment-Verlauf",
            narrative_intro="Assessment narrative overview.",
            steps=[
                AttackPathStep(
                    step_number=1,
                    phase="access",
                    title="Probe Script Exploitation",
                    description="Triggered calibration script",
                    finding_id="f-probe",
                ),
            ],
        )

        doc = ReportWorkspaceDocument(
            metadata=ReportMetadata(),
            findings=[f1, f2],
        )
        doc.set_attack_path(path)

        inspector.load_attack_path(doc)

        # Check title, storyline, and steps count
        self.assertEqual(inspector.lbl_title.text(), "Angriffspfad / Assessment-Verlauf")
        self.assertEqual(inspector.txt_intro.toPlainText(), "Assessment narrative overview.")
        self.assertEqual(inspector.steps_layout.count(), 1)
        self.assertIn("1 Schritte", inspector.lbl_steps_badge.text())

        # Check step card widgets
        card = inspector.steps_layout.itemAt(0).widget()
        self.assertEqual(card.edit_title.text(), "Probe Script Exploitation")
        self.assertEqual(card.txt_desc.toPlainText(), "Triggered calibration script")
        self.assertEqual(card.cmb_finding.currentData(), "f-probe")

        # Test adding a step
        inspector.btn_add_step.click()
        self.assertEqual(inspector.steps_layout.count(), 2)
        self.assertIn("2 Schritte", inspector.lbl_steps_badge.text())

        # Test auto-generate from findings
        inspector.btn_auto_generate.click()
        self.assertEqual(inspector.steps_layout.count(), 2)
        # First step is access, second is privesc
        step0_card = inspector.steps_layout.itemAt(0).widget()
        self.assertEqual(step0_card.cmb_phase.currentData(), "access")
        self.assertEqual(step0_card.step.finding_id, "f-probe")

        step1_card = inspector.steps_layout.itemAt(1).widget()
        self.assertEqual(step1_card.cmb_phase.currentData(), "privesc")
        self.assertEqual(step1_card.step.finding_id, "f-priv")

        # Test jump to finding signal
        jumped_ids = []
        inspector.finding_selected.connect(jumped_ids.append)
        step0_card.btn_jump.click()
        self.assertEqual(jumped_ids, ["f-probe"])

        # Test deleting a step
        step1_card.btn_del.click()
        self.assertEqual(inspector.steps_layout.count(), 1)

        inspector.close()
        inspector.deleteLater()

    def test_report_editor_tab_attack_path_navigation(self):
        tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        tab.load_project("WorkspaceBox")

        f1 = ReportFindingItem(
            id="f-attack-test",
            title="Attack Finding",
            severity="HIGH",
            phase="access",
            status="open",
        )
        assert tab.workspace_document is not None
        tab.workspace_document.findings.append(f1)
        tab.apply_workspace_document()

        # Navigate to attack_path section
        tab.navigate_to(ReportLocation(ReportLocationKind.SECTION, "attack_path"))
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.attack_path_inspector_glass,
        )

        # Click navigation from attack path to finding details
        tab.workspace_shell.attack_path_inspector.finding_selected.emit("f-attack-test")
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.finding_inspector_glass,
        )
        self.assertEqual(tab.workspace_shell.finding_inspector._finding.id, "f-attack-test")

        tab.close()
        tab.deleteLater()

    def test_scope_inspector_ui_and_interactions(self):
        inspector = ReportScopeInspector()
        inspector.set_project_target_ip("10.10.10.50")

        scope = ReportScopeMethodology(
            title="Scope & Methodik",
            approach="whitebox",
            approach_details="Vollständige Einsicht.",
            in_scope_targets=[
                ScopeTargetItem(
                    target="10.10.10.0/24",
                    target_type="network",
                    environment="production",
                    description="Netzwerksegment",
                ),
            ],
            out_of_scope_targets=[
                ScopeExclusionItem(target="10.10.10.1", reason="Gateway"),
            ],
            restrictions=["no_dos", "no_social_engineering"],
            custom_rules="SOC Hotline Notfallkontakt",
        )

        doc = ReportWorkspaceDocument()
        doc.set_scope_methodology(scope)

        inspector.load_scope(doc)

        # Verify initial values
        self.assertEqual(inspector.lbl_title.text(), "Scope & Methodik")
        self.assertTrue(inspector.btn_whitebox.isChecked())
        self.assertEqual(inspector.txt_appr_details.text(), "Vollständige Einsicht.")
        self.assertEqual(inspector.tbl_in_targets.rowCount(), 1)
        self.assertEqual(inspector.tbl_out_targets.rowCount(), 1)
        self.assertEqual(
            inspector.tbl_in_targets.selectionMode(), QTableWidget.SelectionMode.NoSelection
        )
        self.assertEqual(
            inspector.tbl_out_targets.selectionMode(), QTableWidget.SelectionMode.NoSelection
        )
        self.assertEqual(inspector.tbl_in_targets.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertEqual(inspector.tbl_out_targets.focusPolicy(), Qt.FocusPolicy.NoFocus)

        edit_in_target = inspector.tbl_in_targets.cellWidget(0, 0)
        self.assertIsInstance(edit_in_target, QLineEdit)
        self.assertIn("#00e5ff", edit_in_target.styleSheet())
        self.assertIn("rgba(13, 17, 23", edit_in_target.styleSheet())

        self.assertTrue(inspector.chk_no_dos.isChecked())
        self.assertTrue(inspector.chk_no_social.isChecked())
        self.assertFalse(inspector.chk_no_data.isChecked())
        self.assertIn("1 In-Scope | 1 Out-of-Scope", inspector.lbl_badge.text())

        # Test switching approach
        inspector.btn_blackbox.click()
        self.assertEqual(inspector._scope.approach, "blackbox")

        # Test adding in-scope target
        inspector.btn_add_in.click()
        self.assertEqual(inspector.tbl_in_targets.rowCount(), 2)
        self.assertIn("2 In-Scope | 1 Out-of-Scope", inspector.lbl_badge.text())

        # Test import project target IP
        inspector.btn_import_target.click()
        # 10.10.10.50 should now be added
        self.assertEqual(inspector.tbl_in_targets.rowCount(), 3)
        self.assertIn("3 In-Scope | 1 Out-of-Scope", inspector.lbl_badge.text())

        # Test adding and deleting out-of-scope target
        inspector.btn_add_out.click()
        self.assertEqual(inspector.tbl_out_targets.rowCount(), 2)
        # Delete row 1
        btn_del = inspector.tbl_out_targets.cellWidget(1, 2)
        btn_del.click()
        self.assertEqual(inspector.tbl_out_targets.rowCount(), 1)

        inspector.close()
        inspector.deleteLater()

    def test_report_editor_tab_scope_navigation(self):
        tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        tab.load_project("WorkspaceBox")

        # Navigate to scope_limitations section
        tab.navigate_to(ReportLocation(ReportLocationKind.SECTION, "scope_limitations"))
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.scope_inspector_glass,
        )

        # Modify approach and verify doc sync
        tab.workspace_shell.scope_inspector.btn_blackbox.click()
        tab.workspace_shell.scope_inspector._emit_changed()

        assert tab.workspace_document is not None
        retrieved_scope = tab.workspace_document.get_scope_methodology()
        self.assertEqual(retrieved_scope.approach, "blackbox")

        tab.close()
        tab.deleteLater()

    def test_appendix_inspector_widgets_and_operations(self):
        inspector = ReportAppendixInspector()
        inspector.set_context(
            loot_manager=self.loot_mgr,
            clipboard_history=self.clip_watcher,
            project_dir=self.project_mgr.get_project_dir("WorkspaceBox"),
        )

        app = ReportAppendix(
            title="Anhang & Nachweise",
            command_snippets=[
                ReportEvidenceItem(
                    id="cmd1",
                    type="terminal",
                    caption="Nmap",
                    content="nmap -p- 10.10.10.1",
                    language="bash",
                ),
            ],
            screenshots=[
                ReportEvidenceItem(
                    id="sc1",
                    type="screenshot",
                    caption="Root Proof",
                    content="screenshots/proof.png",
                ),
            ],
            custom_notes="Nmap output raw...",
        )
        doc = ReportWorkspaceDocument(language="de")
        doc.set_appendix(app)

        inspector.load_appendix(doc)

        # Verify initial rendering
        self.assertIn("1 Befehle · 1 Nachweise", inspector.lbl_badge.text())
        self.assertEqual(inspector.snippets_layout.count(), 1)
        self.assertEqual(inspector.screenshots_layout.count(), 1)
        self.assertEqual(inspector.edit_notes.toPlainText(), "Nmap output raw...")

        # Add manual command snippet
        inspector.btn_add_cmd.click()
        self.assertEqual(inspector.snippets_layout.count(), 2)
        self.assertIn("2 Befehle · 1 Nachweise", inspector.lbl_badge.text())

        # Add manual image
        inspector.btn_add_img.click()
        self.assertEqual(inspector.screenshots_layout.count(), 2)
        self.assertIn("2 Befehle · 2 Nachweise", inspector.lbl_badge.text())

        # Delete first snippet
        item0 = inspector.snippets_layout.itemAt(0)
        assert item0 is not None
        card0 = item0.widget()
        assert isinstance(card0, CommandSnippetCard)
        card0.btn_delete.click()
        self.assertEqual(inspector.snippets_layout.count(), 1)

        # Delete first screenshot
        item_sc = inspector.screenshots_layout.itemAt(0)
        assert item_sc is not None
        sc0 = item_sc.widget()
        assert isinstance(sc0, ScreenshotCard)
        sc0.btn_delete.click()
        self.assertEqual(inspector.screenshots_layout.count(), 1)

        inspector.close()
        inspector.deleteLater()

    def test_report_editor_tab_appendix_navigation(self):
        tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        tab.load_project("WorkspaceBox")

        # Navigate to appendix section
        tab.navigate_to(ReportLocation(ReportLocationKind.SECTION, "appendix"))
        self.assertEqual(
            tab.workspace_shell.center_stack.currentWidget(),
            tab.workspace_shell.appendix_inspector_glass,
        )

        # Modify notes and trigger changed
        tab.workspace_shell.appendix_inspector.edit_notes.setPlainText(
            "Updated supplementary notes from inspector."
        )
        tab.workspace_shell.appendix_inspector._emit_changed()

        assert tab.workspace_document is not None
        retrieved_app = tab.workspace_document.get_appendix()
        self.assertEqual(retrieved_app.custom_notes, "Updated supplementary notes from inspector.")
        self.assertIn("Updated supplementary notes", tab.workspace_shell.editor.toPlainText())

        tab.close()
        tab.deleteLater()

    def test_appendix_inspector_responsiveness_and_compact_reflow(self):
        tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        tab.load_project("WorkspaceBox")
        tab.navigate_to(ReportLocation(ReportLocationKind.SECTION, "appendix"))
        inspector = tab.workspace_shell.appendix_inspector

        # 1. Verify minimum size hint allows narrow split view
        self.assertLessEqual(inspector.minimumSizeHint().width(), 240)

        # 2. Verify word wrap on section headers and empty labels to prevent layout blowup
        self.assertTrue(inspector.lbl_empty_cmd.wordWrap())
        self.assertTrue(inspector.lbl_empty_sc.wordWrap())
        self.assertTrue(inspector.lbl_title_a.wordWrap())
        self.assertTrue(inspector.lbl_title_b.wordWrap())
        self.assertTrue(inspector.lbl_title_c.wordWrap())

        # 3. Add items to test cards reflow
        inspector._on_add_cmd_clicked()
        inspector._on_add_img_clicked()

        snippet_card = inspector.snippets_layout.itemAt(0).widget()
        screenshot_card = inspector.screenshots_layout.itemAt(0).widget()

        # 4. Reflow in normal/wide mode (>= 480px)
        inspector._reflow_ui(600)
        self.assertEqual(snippet_card.combo_lang.maximumWidth(), 130)
        self.assertEqual(screenshot_card.lbl_thumb.width(), 110)
        self.assertEqual(screenshot_card.lbl_thumb.height(), 75)

        # 5. Reflow in compact mode (< 450px)
        inspector._reflow_ui(360)
        self.assertEqual(snippet_card.combo_lang.maximumWidth(), 85)
        self.assertEqual(screenshot_card.lbl_thumb.width(), 70)
        self.assertEqual(screenshot_card.lbl_thumb.height(), 48)

        # Button texts should switch to short versions
        self.assertIn("History", inspector.btn_pick_history.text())
        self.assertNotIn("wählen", inspector.btn_pick_history.text())

        tab.close()
        tab.deleteLater()

    def test_summary_inspector_responsiveness_and_intermediate_reflow(self):
        from PyQt6.QtWidgets import QFormLayout

        tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        tab.load_project("WorkspaceBox")
        tab.navigate_to(ReportLocation(ReportLocationKind.SECTION, "summary"))
        inspector = tab.workspace_shell.summary_inspector

        # 1. Minimum size hint
        self.assertLessEqual(inspector.minimumSizeHint().width(), 240)

        # 2. Word wrap on labels
        self.assertTrue(inspector.lbl_title.wordWrap())
        self.assertTrue(inspector.lbl_matrix_title.wordWrap())
        self.assertTrue(inspector.lbl_matrix_hint.wordWrap())
        self.assertTrue(inspector.lbl_posture_val.wordWrap())
        self.assertTrue(inspector.lbl_status_val.wordWrap())

        # 3. Wide mode (>= 720px)
        inspector._reflow_summary(750)
        self.assertEqual(inspector._current_grid_mode, "wide")
        self.assertFalse(inspector._current_two_rows)
        self.assertEqual(inspector.form.rowWrapPolicy(), QFormLayout.RowWrapPolicy.DontWrapRows)
        self.assertFalse(inspector.lbl_matrix_hint.isHidden())
        self.assertFalse(inspector.tbl_matrix.isColumnHidden(3))
        self.assertFalse(inspector.tbl_matrix.isColumnHidden(4))

        # 4. Intermediate mode (480px - 719px)
        inspector._reflow_summary(520)
        self.assertEqual(inspector._current_grid_mode, "intermediate")
        self.assertFalse(inspector._current_two_rows)
        self.assertEqual(inspector.form.rowWrapPolicy(), QFormLayout.RowWrapPolicy.WrapAllRows)
        self.assertFalse(inspector.lbl_matrix_hint.isHidden())
        self.assertTrue(inspector.tbl_matrix.isColumnHidden(3))  # Phase hidden in intermediate
        self.assertFalse(inspector.tbl_matrix.isColumnHidden(4))  # Status visible

        # 5. Narrow mode (< 480px)
        inspector._reflow_summary(380)
        self.assertEqual(inspector._current_grid_mode, "narrow")
        self.assertTrue(inspector._current_two_rows)
        self.assertEqual(inspector.form.rowWrapPolicy(), QFormLayout.RowWrapPolicy.WrapAllRows)
        self.assertTrue(inspector.lbl_matrix_hint.isHidden())
        self.assertTrue(inspector.tbl_matrix.isColumnHidden(3))
        self.assertTrue(inspector.tbl_matrix.isColumnHidden(4))

        tab.close()
        tab.deleteLater()

    def test_workspace_splitter_interactivity_and_responsiveness(self):
        """Verify that splitter handles are interactive, non-collapsing, and responsive across all inspectors."""
        tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        tab.resize(1400, 800)
        tab.show()
        tab.load_project("WorkspaceBox")

        # 1. Non-collapsible splitter with 6px grab handles
        self.assertFalse(tab.workspace_shell.splitter.childrenCollapsible())
        self.assertEqual(tab.workspace_shell.splitter.handleWidth(), 6)

        # 2. Free dragging in SPLIT view
        tab.set_view_mode(ViewMode.SPLIT)
        tab.workspace_shell.splitter.moveSplitter(500, 2)
        sizes_split = tab.workspace_shell.splitter.sizes()
        self.assertLessEqual(abs(sizes_split[1] - 500), tab.workspace_shell.splitter.handleWidth())
        self.assertGreater(sizes_split[2], 500)

        tab.workspace_shell.splitter.moveSplitter(900, 2)
        sizes_split2 = tab.workspace_shell.splitter.sizes()
        self.assertLessEqual(abs(sizes_split2[1] - 900), tab.workspace_shell.splitter.handleWidth())

        # 3. Free dragging in WORKSPACE view
        tab.set_view_mode(ViewMode.WORKSPACE)
        tab.workspace_shell.splitter.moveSplitter(300, 1)
        sizes_ws1 = tab.workspace_shell.splitter.sizes()
        self.assertLessEqual(abs(sizes_ws1[0] - 300), tab.workspace_shell.splitter.handleWidth())

        tab.workspace_shell.splitter.moveSplitter(800, 2)
        sizes_ws2 = tab.workspace_shell.splitter.sizes()
        self.assertGreaterEqual(sizes_ws2[0], 180)
        self.assertGreaterEqual(sizes_ws2[1], 200)
        self.assertGreaterEqual(sizes_ws2[2], 150)

        # 4. Responsive center stack: minimum width is <= 320 across all stacked pages
        for idx in range(tab.workspace_shell.center_stack.count()):
            tab.workspace_shell.center_stack.setCurrentIndex(idx)
            min_w = tab.workspace_shell.center_stack.minimumSizeHint().width()
            self.assertLessEqual(min_w, 320)

        tab.close()
        tab.deleteLater()

    def test_clipboard_history_picker_dialog_filter_and_marking(self):
        history = [
            {
                "id": "c1",
                "text": "nmap -sV target",
                "target_ip": "10.10.10.1",
                "include_in_report": True,
            },
            {
                "id": "c2",
                "text": "ls -la /tmp",
                "target_ip": "10.10.10.1",
                "include_in_report": False,
            },
        ]
        dlg = ClipboardHistoryPickerDialog(history)
        self.assertEqual(dlg.list_widget.count(), 2)
        # Check that marked item has [Report] prefix
        self.assertIn("[Report]", dlg.list_widget.item(0).text())
        self.assertNotIn("[Report]", dlg.list_widget.item(1).text())

        # Toggle filter for report only
        dlg.chk_only_report.setChecked(True)
        self.assertEqual(dlg.list_widget.count(), 1)
        self.assertIn("nmap -sV target", dlg.list_widget.item(0).text())

        # Select first item and verify preview
        dlg.list_widget.setCurrentRow(0)
        self.assertEqual(dlg.selected_entry["id"], "c1")
        self.assertIn("nmap -sV target", dlg.txt_preview.toPlainText())

        dlg.close()
        dlg.deleteLater()

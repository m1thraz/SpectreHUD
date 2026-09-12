"""Tests for Report Workspace UI components (Navigator, Inspectors, and Tab integration)."""

import os
from pathlib import Path
import unittest

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidget, QTableWidget, QTreeWidget

from core.clipboard_history import ClipboardHistory
from core.i18n import get_i18n, t
from ui.controllers.window_frame_manager import is_interactive_widget
from core.loot import LootManager
from core.project import ProjectManager
from core.reporting import (
    ReportEvidenceItem,
    ReportFileManager,
    ReportFindingItem,
    ReportMetadata,
    ReportWorkspaceDocument,
)
from ui.report.dialogs import (
    ClipboardHistoryPickerDialog,
    LootEntryPickerDialog,
)
from ui.report.finding_inspector import ReportEvidenceCard, ReportFindingInspector
from ui.report.metadata_inspector import ReportMetadataInspector
from ui.report.section_inspector import ReportSectionInspector
from ui.report.workspace_navigator import ReportWorkspaceNavigator
from ui.report_editor_tab import ReportEditorTab, ViewMode

pytestmark = pytest.mark.integration


class TestReportWorkspaceUI(unittest.TestCase):
    def setUp(self):
        self.temp_path = Path(os.environ["SPECTRE_CONFIG_DIR"]).parent
        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.project_mgr.create_project("WorkspaceBox", target_ip="192.168.1.100")
        self.loot_mgr = LootManager(storage_file=self.temp_path / "config" / "loot.json")
        self.clip_watcher = ClipboardHistory(
            storage_file=self.temp_path / "config" / "clip.json"
        )
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

        # First top-level is Metadata
        item_meta = tree.topLevelItem(0)
        self.assertEqual(item_meta.data(0, Qt.ItemDataRole.UserRole), ("metadata", None))

        # Check signal emission on click
        clicked_events = []
        nav.navigate_requested.connect(lambda v, i: clicked_events.append((v, i)))
        nav._on_item_clicked(item_meta, 0)
        self.assertEqual(clicked_events, [("metadata", None)])

        # Check Add Finding button signal
        add_clicked = []
        nav.add_finding_requested.connect(lambda: add_clicked.append(True))
        nav.btn_add_finding.click()
        self.assertEqual(add_clicked, [True])

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

        # Initial view is SPLIT: navigator is hidden, editor & preview visible
        self.assertEqual(tab._view_mode, ViewMode.SPLIT)
        self.assertFalse(tab.navigator_glass.isVisible())
        self.assertTrue(tab.editor.isVisible())
        self.assertTrue(tab.preview.isVisible())

        # Switch to WORKSPACE mode: navigator, center stack, and preview all visible
        tab._set_view_mode(ViewMode.WORKSPACE)
        self.assertEqual(tab._view_mode, ViewMode.WORKSPACE)
        self.assertTrue(tab.navigator_glass.isVisible())
        self.assertTrue(tab.center_stack.isVisible())
        self.assertTrue(tab.preview.isVisible())

        # Add a finding through the workspace handler
        initial_finding_count = len(tab._workspace_doc.findings) if tab._workspace_doc else 0
        tab._on_add_finding_requested()
        self.assertEqual(len(tab._workspace_doc.findings), initial_finding_count + 1)
        self.assertIn(t("report.new_finding_default_title", "New Finding"), tab.editor.toPlainText())
        self.assertEqual(tab.center_stack.currentWidget(), tab.finding_inspector_glass)

        # Navigate to metadata
        tab._on_navigate_requested("metadata", None)
        self.assertEqual(tab.center_stack.currentWidget(), tab.metadata_inspector_glass)

        # Navigate back to raw markdown
        tab._on_navigate_requested("raw_markdown", None)
        self.assertEqual(tab.center_stack.currentWidget(), tab.editor_glass)

        tab.close()
        tab.deleteLater()

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
        tree = QTreeWidget()
        list_widget = QListWidget()
        table = QTableWidget()
        header = tree.header()

        self.assertTrue(is_interactive_widget(tree))
        self.assertTrue(is_interactive_widget(list_widget))
        self.assertTrue(is_interactive_widget(table))
        self.assertTrue(is_interactive_widget(header))
        tree.deleteLater()
        list_widget.deleteLater()
        table.deleteLater()

    def test_navigator_grouping_by_loot_phases(self):
        nav = ReportWorkspaceNavigator()
        doc = ReportWorkspaceDocument(
            findings=[
                ReportFindingItem(id="f1", title="Nmap Scan", severity="info", phase="recon"),
                ReportFindingItem(id="f2", title="SSH Bruteforce", severity="high", phase="access"),
                ReportFindingItem(id="f3", title="Kernel Exploit", severity="critical", phase="privesc"),
            ]
        )
        nav.load_document(doc)

        findings_root = nav.tree.topLevelItem(2)
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
        nav.deleteLater()

    def test_report_editor_tab_collapsible_navigator_and_raw_toggle(self):
        tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        tab.load_project("WorkspaceBox")
        tab.show()

        # In Split view, navigator starts hidden for 2-column layout
        self.assertFalse(tab.navigator_glass.isVisible())
        self.assertFalse(tab.btn_navigator.isChecked())

        # Toggle on demand
        tab._toggle_navigator()
        self.assertTrue(tab.navigator_glass.isVisible())
        self.assertTrue(tab.btn_navigator.isChecked())

        # Toggle off
        tab._toggle_navigator()
        self.assertFalse(tab.navigator_glass.isVisible())
        self.assertFalse(tab.btn_navigator.isChecked())

        # Toggle raw markdown vs inspector
        self.assertEqual(tab.center_stack.currentWidget(), tab.editor_glass)
        tab._toggle_inspector_raw()
        self.assertEqual(tab.center_stack.currentWidget(), tab.finding_inspector_glass)
        tab._toggle_inspector_raw()
        self.assertEqual(tab.center_stack.currentWidget(), tab.editor_glass)

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

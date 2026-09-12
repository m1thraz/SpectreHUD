"""Tests for Report Workspace UI components (Navigator, Inspectors, and Tab integration)."""

import os
from pathlib import Path
import unittest

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt

from core.clipboard_history import ClipboardHistory
from core.loot import LootManager
from core.project import ProjectManager
from core.reporting import (
    ReportFileManager,
    ReportFindingItem,
    ReportMetadata,
    ReportWorkspaceDocument,
)
from ui.report.finding_inspector import ReportFindingInspector
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
        self.assertIn("Neue Schwachstelle", tab.editor.toPlainText())
        self.assertEqual(tab.center_stack.currentWidget(), tab.finding_inspector_glass)

        # Navigate to metadata
        tab._on_navigate_requested("metadata", None)
        self.assertEqual(tab.center_stack.currentWidget(), tab.metadata_inspector_glass)

        # Navigate back to raw markdown
        tab._on_navigate_requested("raw_markdown", None)
        self.assertEqual(tab.center_stack.currentWidget(), tab.editor_glass)

        tab.close()
        tab.deleteLater()

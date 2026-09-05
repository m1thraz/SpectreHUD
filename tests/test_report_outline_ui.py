"""Tests for report heading outline navigation and jump-to-section."""

import unittest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication

from core.reporting.file_manager import ReportFileManager
from ui.report_editor_tab import ReportEditorTab

app = QApplication.instance() or QApplication([])


class TestReportOutlineUI(unittest.TestCase):
    def setUp(self):
        self.mock_rfm = MagicMock(spec=ReportFileManager)
        self.mock_rfm.load.return_value = (
            "# Executive Summary\n"
            "High-level findings summary.\n\n"
            "## 1. Reconnaissance\n"
            "Port 80 and 443 open.\n\n"
            "### Nmap Results\n"
            "Detailed nmap output.\n\n"
            "## 2. Exploitation\n"
            "Gained shell.\n\n"
            "## 3. Privilege Escalation\n"
            "Root access obtained.\n"
        )
        self.mock_rfm.project_manager = MagicMock()
        self.mock_rfm.project_manager.get_project_dir.return_value = MagicMock()

        self.tab = ReportEditorTab(
            report_file_manager=self.mock_rfm,
            loot_manager=MagicMock(),
            clipboard_history=MagicMock(),
        )
        self.tab.load_project("TestBox")

    def tearDown(self):
        self.tab.deleteLater()

    def test_btn_outline_exists_in_toolbar(self):
        self.assertTrue(hasattr(self.tab, "btn_outline"))
        self.assertTrue(hasattr(self.tab, "outline_menu"))
        self.assertIn("OutlineDropdownBtn", self.tab.btn_outline.property("class"))

    def test_outline_menu_populates_headings(self):
        self.tab._populate_outline_menu()
        actions = self.tab.outline_menu.actions()
        self.assertEqual(len(actions), 5)
        self.assertIn("# Executive Summary", actions[0].text())
        self.assertIn("## 1. Reconnaissance", actions[1].text())
        self.assertIn("### Nmap Results", actions[2].text())
        self.assertIn("## 2. Exploitation", actions[3].text())
        self.assertIn("## 3. Privilege Escalation", actions[4].text())

    def test_outline_menu_empty_document(self):
        self.tab.editor.setPlainText("No headings here, just raw text.")
        self.tab._populate_outline_menu()
        actions = self.tab.outline_menu.actions()
        self.assertEqual(len(actions), 1)
        self.assertFalse(actions[0].isEnabled())

    def test_jump_to_heading_moves_cursor(self):
        self.tab._populate_outline_menu()
        actions = self.tab.outline_menu.actions()

        # Trigger "## 3. Privilege Escalation" (last action, line 14)
        actions[4].trigger()

        cursor = self.tab.editor.textCursor()
        self.assertEqual(cursor.blockNumber(), 12)  # 0-based block for 13th line
        self.assertIn("Privilege Escalation", cursor.block().text())


if __name__ == "__main__":
    unittest.main()

"""Regression coverage for replacing the heading outline with semantic navigation."""

import unittest
from unittest.mock import MagicMock

from core.reporting import ReportFileManager
from ui.report_editor_tab import ReportEditorTab

class TestReportNavigatorReplacement(unittest.TestCase):
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

    def test_toolbar_keeps_only_semantic_navigator(self):
        self.assertFalse(hasattr(self.tab, "btn_outline"))
        self.assertFalse(hasattr(self.tab, "outline_menu"))
        self.assertTrue(hasattr(self.tab, "btn_navigator"))
        self.assertTrue(hasattr(self.tab, "navigator_menu"))

    def test_legacy_report_has_safe_empty_navigator(self):
        self.tab._populate_navigator_menu()
        actions = self.tab.navigator_menu.actions()
        self.assertEqual(len(actions), 1)
        self.assertFalse(actions[0].isEnabled())


if __name__ == "__main__":
    unittest.main()

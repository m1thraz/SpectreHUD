"""Tests for bi-directional scroll synchronization in Split View."""

import unittest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication

from core.report_file_manager import ReportFileManager
from ui.report_editor_tab import ReportEditorTab, ViewMode

app = QApplication.instance() or QApplication([])


class TestReportScrollSync(unittest.TestCase):
    def setUp(self):
        self.mock_rfm = MagicMock(spec=ReportFileManager)
        self.mock_rfm.load.return_value = (
            "# Large Document\n\n" + "\n\n".join(f"Paragraph {i}\nMore text here." for i in range(100))
        )
        self.mock_rfm.project_manager = MagicMock()
        self.mock_rfm.project_manager.get_project_dir.return_value = MagicMock()

        self.tab = ReportEditorTab(
            report_file_manager=self.mock_rfm,
            loot_manager=MagicMock(),
            clipboard_history=MagicMock(),
        )
        self.tab.load_project("TestBox")
        self.tab._set_view_mode(ViewMode.SPLIT)
        self.tab.resize(800, 600)
        self.tab.show()

    def tearDown(self):
        self.tab.deleteLater()

    def test_scroll_sync_editor_to_preview(self):
        """Verify scrolling editor updates preview scrollbar proportionally in Split mode."""
        ed_bar = self.tab.editor.verticalScrollBar()
        pr_bar = self.tab.preview.verticalScrollBar()

        self.assertGreater(ed_bar.maximum(), 0)
        self.assertGreater(pr_bar.maximum(), 0)

        target_ed = ed_bar.maximum() // 2
        ed_bar.setValue(target_ed)

        expected_pr = int((target_ed / ed_bar.maximum()) * pr_bar.maximum())
        self.assertAlmostEqual(pr_bar.value(), expected_pr, delta=2)

    def test_scroll_sync_preview_to_editor(self):
        """Verify scrolling preview updates editor scrollbar proportionally in Split mode."""
        ed_bar = self.tab.editor.verticalScrollBar()
        pr_bar = self.tab.preview.verticalScrollBar()

        self.assertGreater(ed_bar.maximum(), 0)
        self.assertGreater(pr_bar.maximum(), 0)

        target_pr = pr_bar.maximum() // 4
        pr_bar.setValue(target_pr)

        expected_ed = int((target_pr / pr_bar.maximum()) * ed_bar.maximum())
        self.assertAlmostEqual(ed_bar.value(), expected_ed, delta=2)

    def test_scroll_sync_ignored_in_non_split_mode(self):
        """Verify scroll sync is skipped when not in Split mode."""
        self.tab._set_view_mode(ViewMode.EDITOR)

        ed_bar = self.tab.editor.verticalScrollBar()
        pr_bar = self.tab.preview.verticalScrollBar()
        ed_bar.setRange(0, 1000)
        pr_bar.setRange(0, 2000)
        pr_bar.setValue(0)

        ed_bar.setValue(500)
        # Preview should remain at 0 because mode is EDITOR
        self.assertEqual(pr_bar.value(), 0)


if __name__ == "__main__":
    unittest.main()

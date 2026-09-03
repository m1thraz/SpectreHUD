"""Unit tests for the restructured report formatting toolbar."""

import sys
import unittest
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication, QPushButton, QFrame

from ui.report.toolbar import build_format_toolbar

app = QApplication.instance() or QApplication(sys.argv)


class TestReportToolbar(unittest.TestCase):
    def setUp(self):
        self.callbacks = {f"heading_{i}": MagicMock() for i in range(1, 7)}
        self.callbacks.update({
            "bold": MagicMock(),
            "italic": MagicMock(),
            "strikethrough": MagicMock(),
            "code": MagicMock(),
            "code_block": MagicMock(),
            "list": MagicMock(),
            "numbered_list": MagicMock(),
            "quote": MagicMock(),
            "horizontal_rule": MagicMock(),
            "image": MagicMock(),
            "link": MagicMock(),
            "table": MagicMock(),
        })
        self.toolbar = build_format_toolbar(None, self.callbacks)

    def tearDown(self):
        self.toolbar.deleteLater()

    def test_toolbar_contains_dividers_and_zones(self):
        """Verifies visual dividers separate functional toolbar zones."""
        dividers = self.toolbar.findChildren(QFrame)
        divider_frames = [d for d in dividers if "ToolbarDivider" in (d.property("class") or "")]
        self.assertGreaterEqual(len(divider_frames), 2)

    def test_heading_dropdown_menu_invokes_callbacks(self):
        """Verifies the H ▾ button has a menu with H1-H6 actions calling callbacks."""
        buttons = self.toolbar.findChildren(QPushButton)
        h_btn = next((b for b in buttons if b.text() == "H ▾"), None)
        self.assertIsNotNone(h_btn)
        self.assertIsNotNone(h_btn.menu())

        actions = h_btn.menu().actions()
        self.assertEqual(len(actions), 6)

        actions[1].trigger()
        self.callbacks["heading_2"].assert_called_once()

        actions[4].trigger()
        self.callbacks["heading_5"].assert_called_once()

    def test_inline_and_insert_buttons_invoke_callbacks(self):
        """Verifies buttons trigger their mapped callbacks."""
        buttons = {b.text(): b for b in self.toolbar.findChildren(QPushButton)}

        self.assertIn("B", buttons)
        buttons["B"].click()
        self.callbacks["bold"].assert_called_once()

        self.assertIn("🖼️", buttons)
        buttons["🖼️"].click()
        self.callbacks["image"].assert_called_once()

        self.assertIn("❝", buttons)
        buttons["❝"].click()
        self.callbacks["quote"].assert_called_once()

        self.assertIn(">_", buttons)
        buttons[">_"].click()
        self.callbacks["code_block"].assert_called_once()


if __name__ == "__main__":
    unittest.main()

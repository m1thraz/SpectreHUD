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
            "icon": MagicMock(),
            "link": MagicMock(),
            "table": MagicMock(),
            "align_left": MagicMock(),
            "align_center": MagicMock(),
            "align_right": MagicMock(),
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

        icon_button = self.toolbar.findChild(QPushButton, "btn_insert_icon")
        self.assertIsNotNone(icon_button)
        self.assertFalse(icon_button.icon().isNull())
        icon_button.click()
        self.callbacks["icon"].assert_called_once()

        self.assertIn("❝", buttons)
        buttons["❝"].click()
        self.callbacks["quote"].assert_called_once()

        self.assertIn(">_", buttons)
        buttons[">_"].click()
        self.callbacks["code_block"].assert_called_once()

    def test_align_buttons_invoke_callbacks(self):
        """Verifies text alignment buttons trigger their mapped callbacks."""
        btn_left = self.toolbar.findChild(QPushButton, "btn_align_left")
        btn_center = self.toolbar.findChild(QPushButton, "btn_align_center")
        btn_right = self.toolbar.findChild(QPushButton, "btn_align_right")

        self.assertIsNotNone(btn_left)
        self.assertIsNotNone(btn_center)
        self.assertIsNotNone(btn_right)

        btn_left.click()
        self.callbacks["align_left"].assert_called_once()

        btn_center.click()
        self.callbacks["align_center"].assert_called_once()

        btn_right.click()
        self.callbacks["align_right"].assert_called_once()


    def test_toggle_button_collapses_and_expands_tools(self):
        """Verifies clicking the toggle button collapses and expands the formatting tools."""
        self.assertFalse(self.toolbar.tools_container.isHidden())
        self.assertEqual(self.toolbar.btn_toggle.text(), "▲")

        # Click to collapse
        self.toolbar.btn_toggle.click()
        self.assertTrue(self.toolbar.tools_container.isHidden())
        self.assertEqual(self.toolbar.btn_toggle.text(), "▼")

        # Click to expand
        self.toolbar.btn_toggle.click()
        self.assertFalse(self.toolbar.tools_container.isHidden())
        self.assertEqual(self.toolbar.btn_toggle.text(), "▲")

    def test_toggle_button_notifies_collapse_callback(self):
        """Verifies on_toggle_collapse callback receives boolean state."""
        events = []
        tb = build_format_toolbar(
            None, self.callbacks, on_toggle_collapse=lambda c: events.append(c)
        )
        try:
            self.assertFalse(tb.is_collapsed())
            tb.btn_toggle.click()
            self.assertTrue(tb.is_collapsed())
            self.assertEqual(events, [True])

            tb.set_collapsed(False)
            self.assertFalse(tb.is_collapsed())
            self.assertEqual(events, [True, False])
        finally:
            tb.deleteLater()


if __name__ == "__main__":
    unittest.main()

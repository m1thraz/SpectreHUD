import sys
import unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from core.platform.capabilities import detect_platform_capabilities
from ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


class TestCompositorMode(unittest.TestCase):
    """Tests adaptive window layout and transparency depending on compositor presence."""

    def test_platform_capabilities_compositor_override(self):
        # Override off
        caps_off = detect_platform_capabilities(
            system_name="linux",
            environ={"DISPLAY": ":0", "SPECTREHUD_COMPOSITOR": "0"},
        )
        self.assertFalse(caps_off.compositor)

        # Override on
        caps_on = detect_platform_capabilities(
            system_name="linux",
            environ={"DISPLAY": ":0", "SPECTREHUD_COMPOSITOR": "1"},
        )
        self.assertTrue(caps_on.compositor)

        # Windows is always composited
        caps_win = detect_platform_capabilities(system_name="windows")
        self.assertTrue(caps_win.compositor)

        # Wayland is always composited
        caps_wayland = detect_platform_capabilities(
            system_name="linux",
            environ={"WAYLAND_DISPLAY": "wayland-0"},
        )
        self.assertTrue(caps_wayland.compositor)

    def test_main_window_adaptive_margins_and_translucency(self):
        # 1. Non-composited mode
        with patch.object(MainWindow, "_detect_compositor", return_value=False):
            win_no_comp = MainWindow()
            self.assertFalse(win_no_comp.has_compositor)
            self.assertFalse(win_no_comp.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
            central = win_no_comp.centralWidget()
            margins = central.layout().contentsMargins()
            self.assertEqual((margins.left(), margins.top(), margins.right(), margins.bottom()), (0, 0, 0, 0))
            win_no_comp.close()

        # 2. Composited mode
        with patch.object(MainWindow, "_detect_compositor", return_value=True):
            win_comp = MainWindow()
            self.assertTrue(win_comp.has_compositor)
            self.assertTrue(win_comp.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
            central = win_comp.centralWidget()
            margins = central.layout().contentsMargins()
            self.assertEqual((margins.left(), margins.top(), margins.right(), margins.bottom()), (10, 10, 10, 10))
            win_comp.close()


if __name__ == "__main__":
    unittest.main()

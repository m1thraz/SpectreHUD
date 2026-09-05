import sys
import unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from core.platform.capabilities import detect_platform_capabilities
from ui.glass_panel import GlassPanel
from tests.window_factory import create_main_window

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

    def test_main_window_is_opaque_with_identical_margins(self):
        for enabled in ("0", "1"):
            with patch.dict("os.environ", {"SPECTREHUD_COMPOSITOR": enabled}):
                window = create_main_window()
                try:
                    self.assertFalse(
                        window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                    )
                    self.assertIsInstance(window.hud_frame, GlassPanel)
                    margins = window.centralWidget().layout().contentsMargins()
                    self.assertEqual(
                        (margins.left(), margins.top(), margins.right(), margins.bottom()),
                        (0, 0, 0, 0),
                    )
                finally:
                    window.close()


if __name__ == "__main__":
    unittest.main()

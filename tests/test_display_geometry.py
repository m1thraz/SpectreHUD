import unittest
from core.display_geometry import (
    ScreenGeometry,
    compute_virtual_desktop_bounding_box,
    compute_screen_paint_offset,
)


class TestDisplayGeometry(unittest.TestCase):
    """Unit tests for virtual desktop bounding box and screen paint offset calculations."""

    def test_single_monitor(self):
        """Single monitor at (0, 0) with 1920x1080."""
        screens = [ScreenGeometry(x=0, y=0, width=1920, height=1080)]
        bbox = compute_virtual_desktop_bounding_box(screens)

        self.assertEqual(bbox.min_x, 0)
        self.assertEqual(bbox.min_y, 0)
        self.assertEqual(bbox.width, 1920)
        self.assertEqual(bbox.height, 1080)
        self.assertEqual(bbox.to_tuple(), (0, 0, 1920, 1080))

        offset = compute_screen_paint_offset(screens[0], bbox)
        self.assertEqual(offset, (0, 0))

    def test_two_monitors_side_by_side(self):
        """Two identical 1920x1080 monitors side by side: (0, 0) and (1920, 0)."""
        s1 = ScreenGeometry(x=0, y=0, width=1920, height=1080)
        s2 = ScreenGeometry(x=1920, y=0, width=1920, height=1080)
        screens = [s1, s2]

        bbox = compute_virtual_desktop_bounding_box(screens)
        self.assertEqual(bbox.min_x, 0)
        self.assertEqual(bbox.min_y, 0)
        self.assertEqual(bbox.width, 3840)
        self.assertEqual(bbox.height, 1080)

        offset1 = compute_screen_paint_offset(s1, bbox)
        offset2 = compute_screen_paint_offset(s2, bbox)
        self.assertEqual(offset1, (0, 0))
        self.assertEqual(offset2, (1920, 0))

    def test_monitor_with_negative_x_offset(self):
        """Monitor 1 placed to the left of Primary (x = -1920), Primary at (0, 0)."""
        s_left = ScreenGeometry(x=-1920, y=0, width=1920, height=1080)
        s_primary = ScreenGeometry(x=0, y=0, width=2560, height=1440)
        screens = [s_left, s_primary]

        bbox = compute_virtual_desktop_bounding_box(screens)
        self.assertEqual(bbox.min_x, -1920)
        self.assertEqual(bbox.min_y, 0)
        self.assertEqual(bbox.width, 1920 + 2560)  # 4480
        self.assertEqual(bbox.height, 1440)

        offset_left = compute_screen_paint_offset(s_left, bbox)
        offset_prim = compute_screen_paint_offset(s_primary, bbox)
        self.assertEqual(offset_left, (0, 0))
        self.assertEqual(offset_prim, (1920, 0))

    def test_monitor_above_primary_negative_y_offset(self):
        """Monitor above primary: s_top at (0, -1080, 1920, 1080), s_bottom at (0, 0, 1920, 1080)."""
        s_top = ScreenGeometry(x=0, y=-1080, width=1920, height=1080)
        s_bottom = ScreenGeometry(x=0, y=0, width=1920, height=1080)
        screens = [s_top, s_bottom]

        bbox = compute_virtual_desktop_bounding_box(screens)
        self.assertEqual(bbox.min_x, 0)
        self.assertEqual(bbox.min_y, -1080)
        self.assertEqual(bbox.width, 1920)
        self.assertEqual(bbox.height, 2160)

        offset_top = compute_screen_paint_offset(s_top, bbox)
        offset_bot = compute_screen_paint_offset(s_bottom, bbox)
        self.assertEqual(offset_top, (0, 0))
        self.assertEqual(offset_bot, (0, 1080))

    def test_three_screens_mixed_resolutions_and_positions(self):
        """
        3 screens:
        - Left monitor: (-1920, 200, 1920, 1080)
        - Main monitor: (0, 0, 3840, 2160, dpr=2.0)
        - Right monitor: (3840, -500, 1440, 2560) (Vertical)
        """
        s_left = ScreenGeometry(x=-1920, y=200, width=1920, height=1080)
        s_main = ScreenGeometry(x=0, y=0, width=3840, height=2160, device_pixel_ratio=2.0)
        s_right = ScreenGeometry(x=3840, y=-500, width=1440, height=2560)
        screens = [s_left, s_main, s_right]

        bbox = compute_virtual_desktop_bounding_box(screens)
        # min_x = -1920, min_y = -500
        # max_x = 3840 + 1440 = 5280 -> width = 5280 - (-1920) = 7200
        # max_y = max(200+1080=1280, 0+2160=2160, -500+2560=2060) = 2160
        # height = 2160 - (-500) = 2660
        self.assertEqual(bbox.min_x, -1920)
        self.assertEqual(bbox.min_y, -500)
        self.assertEqual(bbox.width, 7200)
        self.assertEqual(bbox.height, 2660)

        self.assertEqual(compute_screen_paint_offset(s_left, bbox), (0, 700))
        self.assertEqual(compute_screen_paint_offset(s_main, bbox), (1920, 500))
        self.assertEqual(compute_screen_paint_offset(s_right, bbox), (5760, 0))

    def test_tuple_input_support(self):
        """Verifies function accepts plain tuples instead of ScreenGeometry objects."""
        raw_screens = [(-1000, 0, 1000, 800), (0, 0, 1920, 1080)]
        bbox = compute_virtual_desktop_bounding_box(raw_screens)
        self.assertEqual(bbox.min_x, -1000)
        self.assertEqual(bbox.width, 2920)
        self.assertEqual(bbox.height, 1080)

        offset = compute_screen_paint_offset((0, 0, 1920, 1080), bbox)
        self.assertEqual(offset, (1000, 0))

    def test_empty_screens_fallback(self):
        """Empty screens sequence returns zero-sized box."""
        bbox = compute_virtual_desktop_bounding_box([])
        self.assertEqual(bbox.to_tuple(), (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()

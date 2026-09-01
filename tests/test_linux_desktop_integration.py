"""
Tests for Linux Desktop Integration (Phase 9: Tickets 29, 30, 31).

Verifies:
- Ticket 29: Valid .desktop entry with mandatory standard desktop entry keys
- Ticket 30: Multi-resolution Linux hicolor icons (48x48, 128x128, 256x256, scalable SVG)
- Ticket 31: WM_CLASS / Wayland App ID consistency between desktop file and application metadata
"""

import configparser
import unittest
from pathlib import Path


class TestLinuxDesktopIntegration(unittest.TestCase):
    """Verifies Linux desktop integration assets and application identity configuration."""

    def setUp(self):
        self.root_dir = Path(__file__).resolve().parent.parent
        self.desktop_file = self.root_dir / "resources" / "linux" / "spectrehud.desktop"
        self.icons_dir = self.root_dir / "resources" / "linux" / "icons" / "hicolor"

    def test_desktop_file_structure_and_keys(self):
        """Ticket 29: .desktop file exists and contains valid standard Desktop Entry keys."""
        self.assertTrue(self.desktop_file.exists(), f"Missing desktop file at {self.desktop_file}")

        parser = configparser.ConfigParser(interpolation=None)
        # Preserve case sensitivity of keys
        parser.optionxform = str
        parser.read(self.desktop_file, encoding="utf-8")

        self.assertIn("Desktop Entry", parser.sections())
        entry = parser["Desktop Entry"]

        self.assertEqual(entry.get("Type"), "Application")
        self.assertEqual(entry.get("Name"), "SpectreHUD")
        self.assertEqual(entry.get("Exec"), "spectrehud")
        self.assertEqual(entry.get("Icon"), "spectrehud")
        self.assertEqual(entry.get("Terminal"), "false")
        self.assertEqual(entry.get("StartupWMClass"), "spectrehud")
        self.assertTrue(len(entry.get("Categories", "")) > 0)

    def test_linux_hicolor_icons_presence_and_sizes(self):
        """Ticket 30: PNG and scalable SVG icons are present in standard hicolor directories."""
        required_sizes = ["48x48", "128x128", "256x256"]
        for size in required_sizes:
            png_path = self.icons_dir / size / "apps" / "spectrehud.png"
            self.assertTrue(png_path.exists(), f"Missing icon: {png_path}")
            self.assertTrue(png_path.stat().st_size > 0, f"Icon {png_path} is empty")

        svg_path = self.icons_dir / "scalable" / "apps" / "spectrehud.svg"
        self.assertTrue(svg_path.exists(), f"Missing scalable SVG at {svg_path}")
        self.assertTrue(svg_path.stat().st_size > 0, f"Scalable SVG {svg_path} is empty")

    def test_application_name_and_desktop_file_match_startup_wmclass(self):
        """Ticket 31: Application identifiers in main.py match StartupWMClass and desktop filename."""
        main_py = (self.root_dir / "main.py").read_text(encoding="utf-8")

        # Parse StartupWMClass from desktop entry
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read(self.desktop_file, encoding="utf-8")
        wm_class = parser["Desktop Entry"]["StartupWMClass"]

        # Ensure applicationName matches wm_class
        self.assertIn(f'app.setApplicationName("{wm_class}")', main_py)
        # Ensure desktopFileName matches the desktop filename
        self.assertIn(f'app.setDesktopFileName("{self.desktop_file.name}")', main_py)
        # Ensure user-facing applicationDisplayName is set
        self.assertIn('app.setApplicationDisplayName("SpectreHUD")', main_py)


if __name__ == "__main__":
    unittest.main()

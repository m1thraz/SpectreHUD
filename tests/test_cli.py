import sys
import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path

import main


class TestCLI(unittest.TestCase):
    """Fast tests verifying CLI arguments (--help, --version) without packaging overhead."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).parent.parent.resolve()
        cls.main_script = cls.repo_root / "main.py"
        cls.launcher_script = cls.repo_root / "spectrehud_launcher.py"

    def test_cli_help(self):
        """Tests that invoking main.py --help exits with 0 and prints usage."""
        res = subprocess.run([sys.executable, str(self.main_script), "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("SpectreHUD", res.stdout)
        self.assertIn("Usage:", res.stdout)

    def test_cli_version(self):
        """Tests that invoking main.py --version exits with 0 and prints version."""
        res = subprocess.run([sys.executable, str(self.main_script), "--version"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("SpectreHUD 2.0.3", res.stdout)

    def test_cli_output_is_safe_when_windowed_exe_has_no_stdout(self):
        """PyInstaller windowed builds provide no stdout for CLI switches."""
        with patch.object(sys, "stdout", None):
            main._write_cli(["SpectreHUD 2.0.3"])

    def test_installed_entrypoint_path_handles_version_without_gui_bootstrap(self):
        res = subprocess.run(
            [sys.executable, str(self.launcher_script), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "SpectreHUD 2.0.3")


if __name__ == "__main__":
    unittest.main()

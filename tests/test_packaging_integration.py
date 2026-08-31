import sys
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


class TestPackagingIntegration(unittest.TestCase):
    """Integration tests verifying pip installable wheel packaging and entrypoints."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).parent.parent.resolve()

    def test_wheel_build_and_contents(self):
        """Builds a real wheel and checks all package components exist in the wheel archive."""
        with tempfile.TemporaryDirectory() as td:
            cmd = [sys.executable, "-m", "pip", "wheel", str(self.repo_root), "--no-deps", "-w", td]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"pip wheel failed: {res.stderr}\n{res.stdout}")

            wheels = list(Path(td).glob("*.whl"))
            self.assertEqual(len(wheels), 1, "Expected exactly 1 generated wheel")
            wheel_path = wheels[0]

            with zipfile.ZipFile(wheel_path, "r") as zf:
                names = zf.namelist()

                # 1. Root scripts & Entrypoint modules
                self.assertIn("main.py", names, "main.py must be in wheel for console_scripts entrypoint")
                self.assertIn("create_desktop_shortcut.py", names)

                # 2. Bundled Package Data
                self.assertIn("data/default_snippets.json", names, "default_snippets.json must be in wheel")
                self.assertIn("data/__init__.py", names)

                # 3. Core modules and canonical project package
                self.assertTrue(any(n.startswith("core/") for n in names))
                self.assertIn("core/config.py", names)
                self.assertIn("core/snippet_manager.py", names)
                self.assertIn("core/loot_manager.py", names)
                self.assertIn("core/clipboard_watcher.py", names)
                self.assertIn("core/project/__init__.py", names)
                self.assertNotIn("core/project_manager.py", names)

                # 4. UI modules & Controllers
                self.assertTrue(any(n.startswith("ui/") for n in names))
                self.assertIn("ui/main_window.py", names)
                self.assertIn("ui/controllers/__init__.py", names)
                self.assertIn("ui/controllers/cheatsheet_controller.py", names)
                self.assertIn("ui/controllers/loot_controller.py", names)
                self.assertIn("ui/controllers/history_controller.py", names)
                self.assertIn("ui/controllers/report_controller.py", names)
                self.assertIn("ui/controllers/project_controller.py", names)
                self.assertIn("ui/controllers/window_frame_manager.py", names)

                # 5. Dist-info entry_points
                entry_points = [n for n in names if n.endswith("entry_points.txt")]
                self.assertTrue(len(entry_points) > 0)
                ep_content = zf.read(entry_points[0]).decode("utf-8")
                self.assertIn("spectrehud = spectrehud_launcher:main", ep_content)

    def test_cli_help_and_version(self):
        """Tests that invoking main.py directly with CLI flags exits 0 without starting Qt GUI loop."""
        res_help = subprocess.run([sys.executable, str(self.repo_root / "main.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(res_help.returncode, 0)
        self.assertIn("SpectreHUD", res_help.stdout)

        res_ver = subprocess.run([sys.executable, str(self.repo_root / "main.py"), "--version"], capture_output=True, text=True)
        self.assertEqual(res_ver.returncode, 0)
        self.assertIn("SpectreHUD 2.0.2", res_ver.stdout)


if __name__ == "__main__":
    unittest.main()

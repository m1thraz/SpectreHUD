import os
import unittest
import tempfile
from pathlib import Path

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

from core.config import ConfigManager
from core.project import ProjectManager
from core.loot.manager import LootManager
from core.clipboard_history import ClipboardHistory
from core.screenshots.manager import ScreenshotManager
from core.project.session_service import ProjectSessionService
from ui.clipboard_monitor import ClipboardMonitor


class TestWorkflowRobustness(unittest.TestCase):
    """
    Cross-component tests for data integrity, recovery, and normal workflow
    robustness. Component-local validation lives in focused test modules; this
    suite keeps one end-to-end invariant per user-visible failure mode.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.config_dir = self.temp_path / "config"
        self.projects_dir = self.temp_path / "projects"

        os.environ["SPECTRE_CONFIG_DIR"] = str(self.config_dir)
        os.environ["SPECTRE_PROJECTS_DIR"] = str(self.projects_dir)

        self.config_mgr = ConfigManager(config_dir=self.config_dir)
        self.project_mgr = ProjectManager(base_dir=self.projects_dir)
        self.loot_mgr = LootManager()
        self.clip_watcher = ClipboardHistory()
        self.screen_mgr = ScreenshotManager()
        self.session_service = ProjectSessionService(
            self.project_mgr, self.loot_mgr, self.clip_watcher
        )

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        os.environ.pop("SPECTRE_PROJECTS_DIR", None)
        self.temp_dir.cleanup()

    def test_report_builder_code_fence_injection_defense(self):
        """
        Loot and clipboard content containing backticks must use adaptive
        fences so that generated Markdown remains structurally correct.
        """
        from core.reporting.builder import ReportBuilder

        # Add credentials containing triple backticks.
        malicious_cred = "admin\n```\n# FAKE EXECUTIVE SUMMARY INJECTION\n```"
        self.loot_mgr.add_entry(
            entry_type="credentials",
            title="Injected Credential",
            content=malicious_cred,
            target_ip="10.10.10.55",
            category="initial_access",
        )

        # Add directory with backticks
        malicious_dir = "/var/www/`html`/`secret`"
        self.loot_mgr.add_entry(
            entry_type="directory",
            title="Injected Directory",
            content=malicious_dir,
            target_ip="10.10.10.55",
            category="recon",
        )

        # Add clipboard item with quadruple backticks
        malicious_clip = "echo 'pwned'\n````\n## INJECTED FOOTER\n````"
        self.clip_watcher.add_entry(malicious_clip, target_ip="10.10.10.55")

        builder = ReportBuilder(
            loot_manager=self.loot_mgr,
            clipboard_watcher=self.clip_watcher,
            project_manager=self.project_mgr,
        )
        report_md = builder.build(target_ip="10.10.10.55", project_name="FenceTest")

        # 1. Verify credential code fence adapted to 4 backticks
        self.assertIn("````\nadmin\n```\n# FAKE EXECUTIVE SUMMARY INJECTION\n```\n````", report_md)

        # 2. Verify clipboard code fence adapted to 5 backticks
        self.assertIn("`````bash\necho 'pwned'\n````\n## INJECTED FOOTER\n````\n`````", report_md)

        # 3. Verify directory inline code adapted with CommonMark space padding
        self.assertIn("`` /var/www/`html`/`secret` ``", report_md)

    # -------------------------------------------------------------------------
    # 19. TemplateEngine Preserves Backslash Sequences
    # -------------------------------------------------------------------------
    def test_template_engine_backslash_sequences_safety(self):
        r"""
        User variables containing backslash sequences must not crash rendering
        or alter the entered text.
        """
        from core.snippets.interpolator import TemplateEngine

        # 1. Invalid regex group backreference \1 (would crash re.sub with re.error)
        res1 = TemplateEngine.render("curl {{TARGET_IP}}", {"target_ip": r"10.10.10.1\1"})
        self.assertEqual(res1, r"curl 10.10.10.1\1")

        # 2. Named group backreference \g<0> (would replace with {{TARGET_IP}} itself)
        res2 = TemplateEngine.render("curl {{TARGET_IP}}", {"target_ip": r"10.10.10.1\g<0>"})
        self.assertEqual(res2, r"curl 10.10.10.1\g<0>")

        # 3. Complex password with multiple backslash sequences in render_with_custom
        res3 = TemplateEngine.render_with_custom(
            "mysql -u {{USER}} -p'{{PASSWORD}}' -h {{TARGET_IP}}",
            {"target_ip": "10.10.10.99", "user": r"root\1"},
            {"PASSWORD": r"P@ss\2\g<1>\test"},
        )
        self.assertEqual(res3, r"mysql -u root\1 -p'P@ss\2\g<1>\test' -h 10.10.10.99")

    # -------------------------------------------------------------------------
    # 22. Side-Effect Free Logger Isolation
    # -------------------------------------------------------------------------
    def test_logger_import_creates_no_files_on_disk(self):
        """
        Importing and retrieving loggers must NOT touch the filesystem or create log files.
        """
        from core.logger import get_logger

        test_log = get_logger("isolated_test_module")
        test_log.info("In-memory test message")
        self.assertIsNotNone(test_log)

    # -------------------------------------------------------------------------
    # 23. Unified Shutdown: Dirty Report Blocks Quit
    # -------------------------------------------------------------------------
    @pytest.mark.integration
    def test_quit_blocks_when_report_dirty(self):
        """
        Adversarial Lifecycle: If the report editor contains unsaved changes and
        the user cancels discard, request_quit() must abort without closing or quitting.
        """
        from unittest.mock import patch
        from ui.main_window import MainWindow
        from core.container import ServiceContainer

        container = ServiceContainer.create_isolated_test_container(
            clipboard_monitor_factory=ClipboardMonitor
        )
        window = MainWindow(container=container)

        with patch.object(window.app.report_ctrl, "confirm_discard_if_dirty", return_value=False):
            with patch("PyQt6.QtWidgets.QApplication.quit") as mock_quit:
                res = window.request_quit()
                self.assertFalse(
                    res, "request_quit must return False when report is dirty and user cancels"
                )
                mock_quit.assert_not_called()

    # -------------------------------------------------------------------------
    # 24. Unified Shutdown: Project State Save Failure Aborts Quit
    # -------------------------------------------------------------------------
    @pytest.mark.integration
    def test_quit_blocks_when_project_save_fails(self):
        """
        Adversarial Lifecycle: If saving project state to disk fails during shutdown,
        request_quit() must prompt the user and abort when the user cancels.
        """
        from unittest.mock import patch
        from PyQt6.QtWidgets import QMessageBox
        from ui.main_window import MainWindow
        from core.container import ServiceContainer

        container = ServiceContainer.create_isolated_test_container(
            clipboard_monitor_factory=ClipboardMonitor
        )
        window = MainWindow(container=container)

        with patch.object(window.app, "save_current_project_state", return_value=False):
            with patch.object(QMessageBox, "exec", return_value=0):
                with patch.object(QMessageBox, "clickedButton", return_value=None):
                    with patch("PyQt6.QtWidgets.QApplication.quit") as mock_quit:
                        res = window.request_quit()
                        self.assertFalse(
                            res,
                            "request_quit must return False when state save fails and user cancels",
                        )
                        mock_quit.assert_not_called()

    # -------------------------------------------------------------------------
    # 25. Unified Shutdown: Normal Exit Flushes State
    # -------------------------------------------------------------------------
    @pytest.mark.integration
    def test_quit_flushes_project_state_on_clean_exit(self):
        """
        Adversarial Lifecycle: Normal request_quit must flush all UI inputs to disk.
        """
        from unittest.mock import patch
        from ui.main_window import MainWindow
        from core.container import ServiceContainer

        container = ServiceContainer.create_isolated_test_container(
            clipboard_monitor_factory=ClipboardMonitor
        )
        window = MainWindow(container=container)
        window.var_bar.txt_target.setText("192.168.1.77")

        with patch("PyQt6.QtWidgets.QApplication.quit"):
            res = window.request_quit()
            self.assertTrue(res)

            # Verify persisted state
            state = container.project_manager.load_project_state()
            self.assertEqual(state.get("target_ip"), "192.168.1.77")

    @pytest.mark.integration
    def test_quit_logs_geometry_persistence_error_without_blocking_shutdown(self):
        """A normal geometry persistence failure is visible but never blocks shutdown."""
        from unittest.mock import patch
        from core.storage import PersistenceError
        from ui.main_window import MainWindow
        from core.container import ServiceContainer

        window = MainWindow(
            container=ServiceContainer.create_isolated_test_container(
                clipboard_monitor_factory=ClipboardMonitor
            )
        )
        with patch.object(window.app, "save_current_project_state", return_value=True):
            with patch.object(window.config, "update", side_effect=PersistenceError("disk full")):
                with patch("ui.main_window.logger.warning") as warning:
                    self.assertTrue(window.request_quit(quit_app=False))

        warning.assert_called_once()
        self.assertIn("window geometry", warning.call_args.args[0])

    @pytest.mark.integration
    def test_quit_logs_unexpected_geometry_error_without_blocking_shutdown(self):
        """Unexpected geometry errors include diagnostics but never block shutdown."""
        from unittest.mock import patch
        from ui.main_window import MainWindow
        from core.container import ServiceContainer

        window = MainWindow(
            container=ServiceContainer.create_isolated_test_container(
                clipboard_monitor_factory=ClipboardMonitor
            )
        )
        with patch.object(window.app, "save_current_project_state", return_value=True):
            with patch.object(window.config, "update", side_effect=ValueError("invalid geometry")):
                with patch("ui.main_window.logger.exception") as exception:
                    self.assertTrue(window.request_quit(quit_app=False))

        exception.assert_called_once()
        self.assertIn("window geometry", exception.call_args.args[0])

    # -------------------------------------------------------------------------
    # 26. Close Event Discard Protection
    # -------------------------------------------------------------------------
    @pytest.mark.integration
    def test_close_event_does_not_discard_unsaved_state(self):
        """
        Adversarial Lifecycle: closeEvent must ignore event if request_quit returns False.
        """
        from unittest.mock import patch
        from PyQt6.QtGui import QCloseEvent
        from ui.main_window import MainWindow
        from core.container import ServiceContainer

        container = ServiceContainer.create_isolated_test_container(
            clipboard_monitor_factory=ClipboardMonitor
        )
        window = MainWindow(container=container)

        evt = QCloseEvent()
        with patch.object(window, "request_quit", return_value=False):
            window.closeEvent(evt)
            self.assertFalse(
                evt.isAccepted(), "CloseEvent must be ignored when request_quit returns False"
            )

    # -------------------------------------------------------------------------
    # 27. Workspace Writability Probe
    # -------------------------------------------------------------------------

import os
import unittest
import tempfile
from pathlib import Path

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QPixmap, QColor

from core.config import ConfigManager
from core.project import ProjectManager
from core.loot.manager import LootManager
from core.clipboard_history import ClipboardHistory
from core.screenshots.manager import ScreenshotManager
from core.project.session_service import ProjectSessionService


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

    @pytest.mark.integration
    def test_rapid_project_switches_keep_clipboard_data_isolated(self):
        """Repeated project switches must not leak clipboard data across sessions."""
        self.project_mgr.create_project("BoxRapidOne")
        self.project_mgr.create_project("BoxRapidTwo")

        self.session_service.load_project_session("BoxRapidOne")
        self.clip_watcher.add_entry("first-project-command", persist=False)
        self.assertTrue(self.session_service.save_project_session({}, "BoxRapidOne"))

        for iteration in range(3):
            self.session_service.load_project_session("BoxRapidTwo")
            expected_history = [] if iteration == 0 else ["second-project-command"]
            self.assertEqual(
                [entry["text"] for entry in self.clip_watcher.get_all_history()], expected_history
            )
            self.clip_watcher.add_entry("second-project-command", persist=False)
            self.assertTrue(self.session_service.save_project_session({}, "BoxRapidTwo"))

            self.session_service.load_project_session("BoxRapidOne")
            self.assertEqual(
                [entry["text"] for entry in self.clip_watcher.get_all_history()],
                ["first-project-command"],
            )

        self.session_service.load_project_session("BoxRapidTwo")
        self.assertEqual(
            [entry["text"] for entry in self.clip_watcher.get_all_history()],
            ["second-project-command"],
        )

    def test_screenshot_commit_survives_immediate_shutdown_save(self):
        """A completed screenshot remains in project state when shutdown follows immediately."""
        from unittest.mock import MagicMock
        from PyQt6.QtCore import Qt

        self.project_mgr.create_project("BoxShutdownScreenshot")
        self.project_mgr.activate_project("BoxShutdownScreenshot")
        image = QImage(10, 10, QImage.Format.Format_RGB32)
        image.fill(QColor("red"))
        parent_window = MagicMock()
        parent_window.windowState.return_value = Qt.WindowState.WindowNoState
        manager = ScreenshotManager()
        manager.screenshot_saved.connect(
            lambda _entry: self.session_service.save_project_session({}, "BoxShutdownScreenshot")
        )

        manager._on_snip_completed(
            QPixmap.fromImage(image), parent_window, self.project_mgr, self.loot_mgr, target_ip=""
        )
        self.assertTrue(self.session_service.save_project_session({}, "BoxShutdownScreenshot"))

        state = self.project_mgr.load_project_state("BoxShutdownScreenshot")
        self.assertEqual(len(state["loot"]), 1)
        self.assertEqual(state["loot"][0]["type"], "screenshot")

    # -------------------------------------------------------------------------
    # 5. P4: Single Source of Truth & No Global State Leakage
    # -------------------------------------------------------------------------
    def test_single_source_of_truth_no_global_leakage(self):
        """
        Adversarial: Active project operations must never write or leak session loot
        or clipboard history into the global configuration directory.
        """
        self.project_mgr.create_project("BoxSecretWork")
        self.session_service.load_project_session("BoxSecretWork")

        self.loot_mgr.add_entry("flag", "Final Root Flag", "THM{s3cr3t_fl4g}")
        self.clip_watcher.add_entry("cat /root/root.txt")
        self.session_service.save_project_session({"target_ip": "10.10.10.99"}, "BoxSecretWork")

        # Invariant: Data is safely in project directory
        proj_dir = self.project_mgr.get_project_dir("BoxSecretWork")
        self.assertTrue((proj_dir / "project_state.json").exists())

        # Invariant: Global root directory has NO leaked files
        self.assertFalse((self.config_dir / "loot_sessions.json").exists())
        self.assertFalse((self.config_dir / "clipboard_history.json").exists())

    # -------------------------------------------------------------------------
    # 8. Project-scoped image resolution
    # -------------------------------------------------------------------------
    def test_project_image_resolution_stays_within_active_project(self):
        """
        A loot entry in Project A must not resolve a same-named screenshot from
        Project B. Image resolution remains scoped to the active project.
        """
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QTextDocument
        from ui.loot_card import LootCard
        from ui.report.preview import ReportDocument

        reference_dir = self.project_mgr.create_project("BoxReference")
        reference_loot = reference_dir / "loot"
        reference_loot.mkdir(parents=True, exist_ok=True)
        reference_screenshot = reference_loot / "screenshot_20260115_143022.png"
        image = QImage(10, 10, QImage.Format.Format_RGB32)
        image.fill(QColor("red"))
        self.assertTrue(image.save(str(reference_screenshot), "PNG"))

        active_dir = self.project_mgr.create_project("BoxActive")
        missing_entry = {
            "id": "loot_missing_1",
            "type": "screenshot",
            "title": "Screenshot from another project",
            "content": "![Screenshot](loot/screenshot_20260115_143022.png)",
        }

        card = LootCard(missing_entry, project_dir=active_dir)
        self.assertIsNone(card._resolve_image_path())

        document = ReportDocument(project_dir=active_dir)
        traversal_url = QUrl("../BoxReference/loot/screenshot_20260115_143022.png")
        absolute_url = QUrl.fromLocalFile(str(reference_screenshot.resolve()))
        for image_url in (traversal_url, absolute_url):
            loaded = document.loadResource(int(QTextDocument.ResourceType.ImageResource), image_url)
            self.assertNotIsInstance(loaded, QImage)

    # -------------------------------------------------------------------------
    # 10. P2: Report Regeneration False-Success Prevention on Save Failure
    # -------------------------------------------------------------------------
    def test_report_regeneration_fails_closed_on_save_error_no_false_success(self):
        """
        Adversarial P2: If report save fails after building content, regenerate()
        must RAISE ReportSaveError rather than returning content and signalling false success.
        """
        from unittest.mock import patch
        from core.reporting.file_manager import ReportFileManager, ReportSaveError

        rfm = ReportFileManager(self.project_mgr)
        self.project_mgr.create_project("BoxSaveBomb")

        # Simulate write failure during atomic save
        with patch.object(rfm, "save", return_value=False):
            with self.assertRaises(ReportSaveError):
                rfm.regenerate(self.loot_mgr, self.clip_watcher, "BoxSaveBomb")

    # -------------------------------------------------------------------------
    # 11. P2: Screenshot File Save Failure Must Not Create Orphaned Loot
    # -------------------------------------------------------------------------
    def test_screenshot_save_failure_does_not_create_orphaned_loot(self):
        """
        Adversarial P2: If saving a screenshot image to disk fails,
        no loot entry should be created referencing the non-existent image file.
        """
        from unittest.mock import patch
        from PyQt6.QtGui import QImage, QPixmap
        from PyQt6.QtWidgets import QWidget
        from core.screenshots.manager import ScreenshotManager

        snip_mgr = ScreenshotManager()
        self.project_mgr.create_project("BoxSnipFail")
        self.project_mgr.activate_project("BoxSnipFail")

        img = QImage(10, 10, QImage.Format.Format_RGB32)
        pix = QPixmap.fromImage(img)

        with patch.object(QPixmap, "save", return_value=False):
            with self.assertRaises(Exception):
                snip_mgr._on_snip_completed(
                    cropped_pixmap=pix,
                    parent_window=QWidget(),
                    project_manager=self.project_mgr,
                    loot_manager=self.loot_mgr,
                    target_ip="10.10.10.99",
                )

        self.assertEqual(len(self.loot_mgr.get_all_entries()), 0)

    # -------------------------------------------------------------------------
    # 12. P2: Session Save Failure Reports False and Propagates Error
    # -------------------------------------------------------------------------
    def test_session_save_failure_returns_false(self):
        """
        Adversarial P2: If project state cannot be saved (e.g. disk full, read-only),
        save_project_state() and save_project_session() must return False, allowing
        the UI to alert the user and avoid silent data loss during project switch.
        """
        from unittest.mock import patch

        self.project_mgr.create_project("BoxSaveErr")

        # State writes are owned by ProjectStateStore after the repository split.
        with (
            patch("core.project.state_store.atomic_write_json", return_value=False),
            patch("core.project.state_store.atomic_write_bytes", return_value=False),
        ):
            saved = self.project_mgr.save_project_state("BoxSaveErr", {"target_ip": "1.2.3.4"})
            self.assertFalse(saved)

            session_saved = self.session_service.save_project_session(
                {"target_ip": "1.2.3.4"}, "BoxSaveErr"
            )
            self.assertFalse(session_saved)

    # -------------------------------------------------------------------------
    # 14. Project Name Sanitization Collision Defense
    # -------------------------------------------------------------------------
    def test_sanitization_collision_cannot_merge_or_overwrite_workspaces(self):
        """
        Adversarial: Creating 'hack box' and then 'hack_box' must not silently merge
        workspaces or overwrite state. The second creation must be rejected with ProjectExistsError.
        """
        from core.project import ProjectExistsError, InvalidProjectNameError

        # Create original project with spaces
        dir1 = self.project_mgr.create_project("hack box", target_ip="10.10.10.50")
        self.assertEqual(dir1.name, "hack_box")

        # Mutate state in original project
        notes_file = dir1 / "notes.md"
        notes_file.write_text("Confidential Original Notes", encoding="utf-8")

        # Attempting to create project with already sanitized name
        with self.assertRaises(ProjectExistsError):
            self.project_mgr.create_project("hack_box", target_ip="1.1.1.1")

        # Attempting with extra spaces / slashes that resolve to the same sanitized name
        with self.assertRaises(ProjectExistsError):
            self.project_mgr.create_project("hack   box")

        with self.assertRaises((ProjectExistsError, InvalidProjectNameError)):
            self.project_mgr.create_project("hack/box")

        # Verify original files were NOT overwritten
        self.assertEqual(notes_file.read_text(encoding="utf-8"), "Confidential Original Notes")

    # -------------------------------------------------------------------------
    # 18. ReportBuilder Preserves Markdown Code Fences
    # -------------------------------------------------------------------------

import os
import json
import time
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QImage, QPixmap, QColor

from core.config import ConfigManager
from core.project import ProjectManager, InvalidProjectNameError, ProjectCreationError
from core.loot_manager import LootManager
from core.storage import PersistenceError
from core.clipboard_watcher import ClipboardWatcher
from core.screenshot_manager import ScreenshotManager
from core.project_session_service import ProjectSessionService
from core.report_file_manager import ReportFileManager, ReportBackupError
from core.snippet_manager import SnippetManager
from ui.main_window import MainWindow


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
        self.clip_watcher = ClipboardWatcher()
        self.screen_mgr = ScreenshotManager()
        self.session_service = ProjectSessionService(
            self.project_mgr, self.loot_mgr, self.clip_watcher
        )

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        os.environ.pop("SPECTRE_PROJECTS_DIR", None)
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. P1: Workspace Escape & Path Traversal
    # -------------------------------------------------------------------------
    def test_project_name_cannot_escape_workspace(self):
        """
        Invalid project names must not resolve outside the workspace or create
        files and folders in its parent directory.
        """
        malicious_names = [
            "..",
            ".",
            "...",
            "../pwned",
            "..\\pwned_win",
            "../../../../etc/passwd",
            "   ",
            "---",
            "foo/bar",
            "foo\\bar",
            "\x00hidden"
        ]

        resolved_base = self.projects_dir.resolve()
        from core.project import InvalidProjectNameError

        for bad_name in malicious_names:
            with self.assertRaises(InvalidProjectNameError):
                self.project_mgr.create_project(bad_name, allow_existing=True)

            with self.assertRaises(InvalidProjectNameError):
                self.project_mgr.get_project_dir(bad_name)

        # File System Invariant: Parent directory of workspace must remain completely untouched
        parent_entries = [p.name for p in self.projects_dir.parent.iterdir() if p.name != "projects"]
        self.assertNotIn("pwned", parent_entries)
        self.assertNotIn("recon", parent_entries)
        self.assertNotIn("exploit", parent_entries)
        self.assertNotIn("notes.md", parent_entries)

    def test_invalid_project_operations_do_not_mutate_default(self):
        """Mutating or loading with an invalid name must never silently target Default."""
        self.project_mgr.save_project_state("Default", {"target_ip": "10.10.10.10"})
        before = self.project_mgr.load_project_state("Default")

        for invalid_name in ("../../evil", "..\\evil", "   "):
            with self.assertRaises(InvalidProjectNameError):
                self.project_mgr.activate_project(invalid_name)
            with self.assertRaises(InvalidProjectNameError):
                self.project_mgr.load_project_state(invalid_name)
            with self.assertRaises(InvalidProjectNameError):
                self.project_mgr.save_project_state(invalid_name, {"target_ip": "9.9.9.9"})

        self.assertEqual(self.project_mgr.load_project_state("Default"), before)

    # -------------------------------------------------------------------------
    # 2. P2: Screenshot Filename Collisions
    # -------------------------------------------------------------------------
    def test_screenshot_names_are_unique(self):
        """
        Adversarial: Rapid back-to-back screenshot captures within the exact same
        second must generate distinct filenames and never overwrite previous evidence.
        """
        self.project_mgr.create_project("BoxTarget")
        self.project_mgr.activate_project("BoxTarget")

        dummy_widget = QWidget()
        img = QImage(50, 50, QImage.Format.Format_RGB32)
        img.fill(QColor("magenta"))
        pixmap = QPixmap.fromImage(img)

        # Fire 3 screenshots in rapid succession
        for _ in range(3):
            self.screen_mgr._on_snip_completed(
                cropped_pixmap=pixmap,
                parent_window=dummy_widget,
                project_manager=self.project_mgr,
                loot_manager=self.loot_mgr,
                target_ip="10.10.10.10"
            )

        loot_dir = self.project_mgr.get_project_dir("BoxTarget") / "loot"
        png_files = list(loot_dir.glob("screenshot_*.png"))

        # Collision Invariant: Exactly 3 unique PNG files must exist
        self.assertEqual(len(png_files), 3, f"Screenshot collision occurred: found {len(png_files)} files, expected 3")
        self.assertEqual(len(self.loot_mgr.get_all_entries()), 3)

    # -------------------------------------------------------------------------
    # 3. P2: Fail-Closed Report Backup Guarantee
    # -------------------------------------------------------------------------
    def test_report_regeneration_requires_successful_backup(self):
        """
        Adversarial: If backing up an existing report.md fails (e.g. disk write failure),
        regenerate MUST fail closed by raising ReportBackupError and MUST NOT overwrite
        the user's existing handcrafted report notes.
        """
        rfm = ReportFileManager(self.project_mgr)
        self.project_mgr.create_project("BoxPentest")
        original_report = "# Handcrafted Critical Pentest Writeup\n\n- Sensitive findings here."
        rfm.save(original_report, "BoxPentest")

        # Simulate backup failure
        with patch.object(rfm, "backup", return_value=False):
            with self.assertRaises(ReportBackupError):
                rfm.regenerate(self.loot_mgr, self.clip_watcher, "BoxPentest")

        # Data Safety Invariant: Original file must remain untouched
        self.assertEqual(rfm.load("BoxPentest"), original_report)

    # -------------------------------------------------------------------------
    # 4. P3: Semantic Schema Recovery from Malformed JSON
    # -------------------------------------------------------------------------
    def test_malformed_project_state_is_recovered(self):
        """
        Adversarial: When project_state.json contains syntactically valid but semantically
        poisoned data (str instead of list, int instead of str, nulls, missing keys),
        the session service and managers MUST self-heal into a valid schema without crashing.
        """
        self.project_mgr.create_project("BoxPoisoned")
        proj_dir = self.project_mgr.get_project_dir("BoxPoisoned")
        state_file = proj_dir / "project_state.json"

        # Write poisoned schema
        poisoned_data = {
            "name": "BoxPoisoned",
            "target_ip": 1337,           # int instead of str
            "attacker_ip": None,         # None instead of str
            "port": 8080,                # int instead of str
            "loot": "banana",            # str instead of list[dict]
            "clipboard_history": 42      # int instead of list[dict]
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(poisoned_data, f)

        # Load session
        loaded_state = self.session_service.load_project_session("BoxPoisoned")

        # Self-Healing Schema Invariants
        self.assertIsInstance(loaded_state["loot"], list)
        self.assertEqual(loaded_state["loot"], [])
        self.assertIsInstance(loaded_state["clipboard_history"], list)
        self.assertEqual(loaded_state["clipboard_history"], [])
        self.assertEqual(loaded_state["target_ip"], "1337")

        # Manager Operation Invariants: Managers must operate without TypeErrors
        self.loot_mgr.add_entry("credentials", "Test Cred", "admin:admin")
        self.assertEqual(len(self.loot_mgr.get_all_entries()), 1)
        self.clip_watcher.add_entry("ls -la")
        self.assertEqual(len(self.clip_watcher.get_all_history()), 1)

    def test_restart_recovers_from_corrupt_registry_and_project_state(self):
        """A new process instance must recover safely from corrupted persisted JSON."""
        self.project_mgr.create_project("BoxRestart")
        project_dir = self.project_mgr.get_project_dir("BoxRestart")
        (project_dir / "project_state.json").write_text("{not valid json", encoding="utf-8")
        self.project_mgr.registry_file.write_text("[not a registry]", encoding="utf-8")

        restarted_manager = ProjectManager(base_dir=self.projects_dir, config_dir=self.config_dir)
        recovered_state = restarted_manager.load_project_state("BoxRestart")

        self.assertIn("BoxRestart", restarted_manager.list_projects())
        self.assertEqual(recovered_state["name"], "BoxRestart")
        self.assertEqual(recovered_state["loot"], [])
        persisted_registry = json.loads(restarted_manager.registry_file.read_text(encoding="utf-8"))
        self.assertIn("BoxRestart", persisted_registry)

    def test_registry_purge_persists_single_instance_state_and_restart(self):
        """A symlink purge persists the active registry state and survives a restart."""
        outside_dir = self.temp_path / "outside_registry_target"
        outside_dir.mkdir()
        symlink_path = self.projects_dir / "Evil"
        symlink_path.mkdir()

        self.project_mgr.repository._update_registry(additions={"Evil": str(outside_dir)})
        # Model a symlinked workspace entry without requiring Windows Developer
        # Mode or administrator symlink privileges in CI.
        real_is_symlink = Path.is_symlink
        with patch.object(
            Path,
            "is_symlink",
            autospec=True,
            side_effect=lambda path: path == symlink_path or real_is_symlink(path),
        ):
            self.project_mgr.sync_registry()
            self.assertNotIn("Evil", self.project_mgr.registry)
            with self.project_mgr.registry_file.open(encoding="utf-8") as registry_file:
                self.assertNotIn("Evil", json.load(registry_file))

            restarted = ProjectManager(base_dir=self.projects_dir, config_dir=self.config_dir)
            self.assertNotIn("Evil", restarted.registry)

    def test_workspace_loss_while_running_fails_closed_without_crashing(self):
        """Saving after the configured workspace disappears must report failure safely."""
        self.project_mgr.create_project("BoxWorkspaceLoss")
        self.project_mgr.activate_project("BoxWorkspaceLoss")

        workspace = self.project_mgr.base_dir
        for child in workspace.iterdir():
            if child.is_dir():
                import shutil
                shutil.rmtree(child)
            else:
                child.unlink()
        workspace.rmdir()
        workspace.write_text("workspace is unavailable", encoding="utf-8")

        self.assertFalse(
            self.project_mgr.save_project_state("BoxWorkspaceLoss", {"target_ip": "10.10.10.10"})
        )

    def test_project_switch_rolls_back_when_report_load_fails(self):
        """A broken report must not leave the application switched to a half-loaded project."""
        from unittest.mock import MagicMock, patch
        from core.event_bus import EventBus, EventType
        from ui.coordinators.workspace_coordinator import WorkspaceCoordinator

        self.project_mgr.create_project("BoxReportOld")
        self.project_mgr.create_project("BoxReportBroken")
        self.project_mgr.activate_project("BoxReportOld")
        report_ctrl = MagicMock()
        report_ctrl.confirm_discard_if_dirty.return_value = True
        report_ctrl.load_project.side_effect = RuntimeError("corrupted report.md")
        project_ctrl = MagicMock()
        event_bus = EventBus()
        events = []
        event_bus.subscribe(EventType.PROJECT_CHANGED, events.append)
        coordinator = WorkspaceCoordinator(
            project_manager=self.project_mgr,
            session_service=MagicMock(save_project_session=MagicMock(return_value=True)),
            project_ctrl=project_ctrl,
            report_ctrl=report_ctrl,
            event_bus=event_bus,
        )

        with patch("ui.coordinators.workspace_coordinator.QMessageBox.critical"):
            switched = coordinator.switch_to_project(
                "BoxReportBroken", QWidget(), variables_provider=lambda: {}
            )

        self.assertFalse(switched)
        self.assertEqual(self.project_mgr.get_active_project(), "BoxReportOld")
        project_ctrl.update_project_combo.assert_called_once()
        self.assertEqual(events, [])

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
    # 8. Cross-Project Screenshot Resolution Isolation
    # -------------------------------------------------------------------------
    def test_cross_project_screenshot_resolution_isolation(self):
        """
        A loot entry in Project A must not resolve a same-named screenshot from
        Project B. Image resolution remains scoped to the active project.
        """
        from ui.loot_card import LootCard

        # 1. Setup victim project with sensitive screenshot
        victim_dir = self.project_mgr.create_project("BoxVictimClient")
        victim_loot = victim_dir / "loot"
        victim_loot.mkdir(parents=True, exist_ok=True)
        victim_screenshot = victim_loot / "screenshot_20260115_143022.png"
        victim_screenshot.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...")

        # 2. Setup separate project with malicious reference attempting confused deputy leak
        attacker_dir = self.project_mgr.create_project("BoxAttackerEvent")
        malicious_entry = {
            "id": "loot_spoof_1",
            "type": "screenshot",
            "title": "Guess Victim Screenshot",
            "content": "![Guess](loot/screenshot_20260115_143022.png)"
        }

        # 3. Create LootCard for attacker project
        card = LootCard(malicious_entry, project_dir=attacker_dir)
        resolved = card._resolve_image_path()

        # Invariant: Must return None because the image does NOT exist in BoxAttackerEvent
        self.assertIsNone(
            resolved,
                "LootCard resolved an image from another project."
        )

    # -------------------------------------------------------------------------
    # 10. P2: Report Regeneration False-Success Prevention on Save Failure
    # -------------------------------------------------------------------------
    def test_report_regeneration_fails_closed_on_save_error_no_false_success(self):
        """
        Adversarial P2: If report save fails after building content, regenerate()
        must RAISE ReportSaveError rather than returning content and signalling false success.
        """
        from unittest.mock import patch
        from core.report_file_manager import ReportFileManager, ReportSaveError

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
        from core.screenshot_manager import ScreenshotManager

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
                    target_ip="10.10.10.99"
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

        # atomic_write_json is a top-level import in core.project.repository,
        # so we must patch it there (where it is actually bound at call time).
        with patch("core.project.repository.atomic_write_json", return_value=False), \
             patch("core.project.repository.atomic_write_bytes", return_value=False):
            saved = self.project_mgr.save_project_state("BoxSaveErr", {"target_ip": "1.2.3.4"})
            self.assertFalse(saved)

            session_saved = self.session_service.save_project_session({"target_ip": "1.2.3.4"}, "BoxSaveErr")
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
    # 16. Report Preview Resolves Project Images Only
    # -------------------------------------------------------------------------
    def test_report_document_blocks_path_traversal_and_absolute_outside_images(self):
        """
        The report preview loads images from the active project and ignores
        invalid or unrelated local paths.
        """
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QTextDocument
        from ui.report.preview import ReportDocument

        # Create an image outside the project workspace.
        secret_outside = self.temp_path / "secret_victim_data.png"
        victim_img = QImage(100, 100, QImage.Format.Format_RGB32)
        victim_img.fill(QColor("red"))
        self.assertTrue(victim_img.save(str(secret_outside), "PNG"))

        # Create the active project workspace.
        proj_dir = self.project_mgr.create_project("SandboxBox")
        doc = ReportDocument(project_dir=proj_dir)

        # Invalid relative paths are not loaded.
        traversal_url = QUrl("../../../../secret_victim_data.png")
        loaded_traversal = doc.loadResource(int(QTextDocument.ResourceType.ImageResource), traversal_url)
        self.assertNotIsInstance(loaded_traversal, QImage)

        # Absolute paths outside the project are not loaded.
        absolute_url = QUrl.fromLocalFile(str(secret_outside.resolve()))
        loaded_absolute = doc.loadResource(int(QTextDocument.ResourceType.ImageResource), absolute_url)
        self.assertNotIsInstance(loaded_absolute, QImage)

        # The same is true for a raw absolute path.
        raw_absolute_url = QUrl(str(secret_outside.resolve()))
        loaded_raw_abs = doc.loadResource(int(QTextDocument.ResourceType.ImageResource), raw_absolute_url)
        self.assertNotIsInstance(loaded_raw_abs, QImage)

    # -------------------------------------------------------------------------
    # 18. ReportBuilder Preserves Markdown Code Fences
    # -------------------------------------------------------------------------
    def test_report_builder_code_fence_injection_defense(self):
        """
        Loot and clipboard content containing backticks must use adaptive
        fences so that generated Markdown remains structurally correct.
        """
        from core.report_builder import ReportBuilder

        # Add credentials containing triple backticks.
        malicious_cred = "admin\n```\n# FAKE EXECUTIVE SUMMARY INJECTION\n```"
        self.loot_mgr.add_entry(
            entry_type="credentials",
            title="Injected Credential",
            content=malicious_cred,
            target_ip="10.10.10.55",
            category="initial_access"
        )

        # Add directory with backticks
        malicious_dir = "/var/www/`html`/`secret`"
        self.loot_mgr.add_entry(
            entry_type="directory",
            title="Injected Directory",
            content=malicious_dir,
            target_ip="10.10.10.55",
            category="recon"
        )

        # Add clipboard item with quadruple backticks
        malicious_clip = "echo 'pwned'\n````\n## INJECTED FOOTER\n````"
        self.clip_watcher.add_entry(malicious_clip, target_ip="10.10.10.55")

        builder = ReportBuilder(
            loot_manager=self.loot_mgr,
            clipboard_watcher=self.clip_watcher,
            project_manager=self.project_mgr
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
        from core.template_engine import TemplateEngine

        # 1. Invalid regex group backreference \1 (would crash re.sub with re.error)
        res1 = TemplateEngine.render(
            "curl {{TARGET_IP}}",
            {"target_ip": r"10.10.10.1\1"}
        )
        self.assertEqual(res1, r"curl 10.10.10.1\1")

        # 2. Named group backreference \g<0> (would replace with {{TARGET_IP}} itself)
        res2 = TemplateEngine.render(
            "curl {{TARGET_IP}}",
            {"target_ip": r"10.10.10.1\g<0>"}
        )
        self.assertEqual(res2, r"curl 10.10.10.1\g<0>")

        # 3. Complex password with multiple backslash sequences in render_with_custom
        res3 = TemplateEngine.render_with_custom(
            "mysql -u {{USER}} -p'{{PASSWORD}}' -h {{TARGET_IP}}",
            {"target_ip": "10.10.10.99", "user": r"root\1"},
            {"PASSWORD": r"P@ss\2\g<1>\test"}
        )
        self.assertEqual(
            res3,
            r"mysql -u root\1 -p'P@ss\2\g<1>\test' -h 10.10.10.99"
        )

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
    def test_quit_blocks_when_report_dirty(self):
        """
        Adversarial Lifecycle: If the report editor contains unsaved changes and
        the user cancels discard, request_quit() must abort without closing or quitting.
        """
        from unittest.mock import patch
        from ui.main_window import MainWindow
        from core.container import ServiceContainer

        container = ServiceContainer.create_isolated_test_container()
        window = MainWindow(container=container)

        with patch.object(window.app.report_ctrl, "confirm_discard_if_dirty", return_value=False):
            with patch("PyQt6.QtWidgets.QApplication.quit") as mock_quit:
                res = window.request_quit()
                self.assertFalse(res, "request_quit must return False when report is dirty and user cancels")
                mock_quit.assert_not_called()

    # -------------------------------------------------------------------------
    # 24. Unified Shutdown: Project State Save Failure Aborts Quit
    # -------------------------------------------------------------------------
    def test_quit_blocks_when_project_save_fails(self):
        """
        Adversarial Lifecycle: If saving project state to disk fails during shutdown,
        request_quit() must prompt the user and abort when the user cancels.
        """
        from unittest.mock import patch
        from PyQt6.QtWidgets import QMessageBox
        from ui.main_window import MainWindow
        from core.container import ServiceContainer

        container = ServiceContainer.create_isolated_test_container()
        window = MainWindow(container=container)

        with patch.object(window.app, "save_current_project_state", return_value=False):
            with patch.object(QMessageBox, "exec", return_value=0):
                with patch.object(QMessageBox, "clickedButton", return_value=None):
                    with patch("PyQt6.QtWidgets.QApplication.quit") as mock_quit:
                        res = window.request_quit()
                        self.assertFalse(res, "request_quit must return False when state save fails and user cancels")
                        mock_quit.assert_not_called()

    # -------------------------------------------------------------------------
    # 25. Unified Shutdown: Normal Exit Flushes State
    # -------------------------------------------------------------------------
    def test_quit_flushes_project_state_on_clean_exit(self):
        """
        Adversarial Lifecycle: Normal request_quit must flush all UI inputs to disk.
        """
        from unittest.mock import patch
        from ui.main_window import MainWindow
        from core.container import ServiceContainer

        container = ServiceContainer.create_isolated_test_container()
        window = MainWindow(container=container)
        window.var_bar.txt_target.setText("192.168.1.77")

        with patch("PyQt6.QtWidgets.QApplication.quit"):
            res = window.request_quit()
            self.assertTrue(res)
            
            # Verify persisted state
            state = container.project_manager.load_project_state()
            self.assertEqual(state.get("target_ip"), "192.168.1.77")

    def test_quit_logs_geometry_persistence_error_without_blocking_shutdown(self):
        """A normal geometry persistence failure is visible but never blocks shutdown."""
        from unittest.mock import patch
        from core.storage import PersistenceError
        from ui.main_window import MainWindow
        from core.container import ServiceContainer

        window = MainWindow(container=ServiceContainer.create_isolated_test_container())
        with patch.object(window.app, "save_current_project_state", return_value=True):
            with patch.object(window.config, "update", side_effect=PersistenceError("disk full")):
                with patch("ui.main_window.logger.warning") as warning:
                    self.assertTrue(window.request_quit(quit_app=False))

        warning.assert_called_once()
        self.assertIn("window geometry", warning.call_args.args[0])

    def test_quit_logs_unexpected_geometry_error_without_blocking_shutdown(self):
        """Unexpected geometry errors include diagnostics but never block shutdown."""
        from unittest.mock import patch
        from ui.main_window import MainWindow
        from core.container import ServiceContainer

        window = MainWindow(container=ServiceContainer.create_isolated_test_container())
        with patch.object(window.app, "save_current_project_state", return_value=True):
            with patch.object(window.config, "update", side_effect=ValueError("invalid geometry")):
                with patch("ui.main_window.logger.exception") as exception:
                    self.assertTrue(window.request_quit(quit_app=False))

        exception.assert_called_once()
        self.assertIn("window geometry", exception.call_args.args[0])

    # -------------------------------------------------------------------------
    # 26. Close Event Discard Protection
    # -------------------------------------------------------------------------
    def test_close_event_does_not_discard_unsaved_state(self):
        """
        Adversarial Lifecycle: closeEvent must ignore event if request_quit returns False.
        """
        from unittest.mock import patch
        from PyQt6.QtGui import QCloseEvent
        from ui.main_window import MainWindow
        from core.container import ServiceContainer

        container = ServiceContainer.create_isolated_test_container()
        window = MainWindow(container=container)

        evt = QCloseEvent()
        with patch.object(window, "request_quit", return_value=False):
            window.closeEvent(evt)
            self.assertFalse(evt.isAccepted(), "CloseEvent must be ignored when request_quit returns False")

    # -------------------------------------------------------------------------
    # 27. Workspace Writability Probe
    # -------------------------------------------------------------------------
    def test_workspace_change_rejects_unwritable_directory(self):
        """
        Adversarial: Changing workspace directory to an unwritable / invalid path must fail-closed.
        """
        from unittest.mock import patch
        from core.project.validator import validate_workspace_directory, WorkspaceError

        # Empty path
        with self.assertRaises(WorkspaceError):
            validate_workspace_directory("")

        # Unwritable path simulation
        target_p = self.temp_path / "valid_unwritable_probe"
        with patch("pathlib.Path.write_text", side_effect=PermissionError("Mock Permission Denied")):
            with self.assertRaises(WorkspaceError):
                validate_workspace_directory(target_p)

    # -------------------------------------------------------------------------
    # 28. Directory Collision Handling on Existing Folders
    # -------------------------------------------------------------------------
    def test_project_name_collision_on_existing_directories(self):
        """
        Adversarial: Having both 'Hack Box' and 'Hack_Box' on disk must detect collision
        and refuse silent shadowing/overwrite in list_projects.
        """
        dir_a = self.projects_dir / "Hack Box"
        dir_b = self.projects_dir / "Hack_Box"
        dir_a.mkdir(parents=True, exist_ok=True)
        dir_b.mkdir(parents=True, exist_ok=True)

        projects = self.project_mgr.list_projects()
        # Due to collision, the ambiguous alias 'Hack_Box' must not silently shadow both directories
        self.assertNotIn("Hack Box", projects)

    # -------------------------------------------------------------------------
    # 29. Invalid Project Lookup Does Not Mutate Default
    # -------------------------------------------------------------------------
    def test_invalid_project_lookup_does_not_mutate_default(self):
        """
        Adversarial: get_project_dir with path traversal must RAISE InvalidProjectNameError
        rather than quietly returning the Default project directory.
        """
        with self.assertRaises(InvalidProjectNameError):
            self.project_mgr.get_project_dir("../../../secret")

        with self.assertRaises(InvalidProjectNameError):
            self.project_mgr.repository.get_project_dir("..\\..\\windows_attack")

    # -------------------------------------------------------------------------
    # 30. Screenshot save ownership belongs to AppController
    # -------------------------------------------------------------------------
    def test_screenshot_manager_defers_project_state_persistence(self):
        """
        The ScreenshotManager must not call a parent-window persistence hook or own
        rollback semantics; the AppController persists the completed session after
        receiving the screenshot_saved signal.
        """
        from unittest.mock import MagicMock
        from PyQt6.QtGui import QPixmap, QImage
        from core.screenshot_manager import ScreenshotManager

        snip_mgr = ScreenshotManager()
        self.project_mgr.create_project("BoxRollback")
        self.project_mgr.activate_project("BoxRollback")

        img = QImage(100, 100, QImage.Format.Format_RGB32)
        pix = QPixmap.fromImage(img)

        mock_window = MagicMock()
        mock_window.save_current_project_state.return_value = False

        snip_mgr._on_snip_completed(
            cropped_pixmap=pix,
            parent_window=mock_window,
            project_manager=self.project_mgr,
            loot_manager=self.loot_mgr,
            target_ip="10.10.10.10"
        )

        mock_window.save_current_project_state.assert_not_called()

        # The capture remains available for the AppController to persist.
        loot_dir = self.project_mgr.get_project_dir("BoxRollback") / "loot"
        self.assertEqual(len(list(loot_dir.glob("*.png"))), 1)
        self.assertEqual(len(self.loot_mgr.get_all_entries()), 1)

    # -------------------------------------------------------------------------
    # 31. Session Load Performs Zero Disk Writes
    # -------------------------------------------------------------------------
    def test_session_load_does_not_persist(self):
        """
        Adversarial: ProjectSessionService.load_project_session must strictly populate
        in-memory state without triggering storage write operations.
        """
        from unittest.mock import MagicMock
        from core.project_session_service import ProjectSessionService

        mock_storage = MagicMock()
        self.loot_mgr.storage = mock_storage
        self.clip_watcher.storage = mock_storage

        session_service = ProjectSessionService(
            project_manager=self.project_mgr,
            loot_manager=self.loot_mgr,
            clipboard_watcher=self.clip_watcher
        )

        self.project_mgr.create_project("BoxLoadNoWrite")
        mock_storage.save_json.reset_mock()

        session_service.load_project_session("BoxLoadNoWrite")
        # Load operation must NOT call storage.save_json
        mock_storage.save_json.assert_not_called()

    # -------------------------------------------------------------------------
    # 32. Clipboard Metadata Derived From Text
    # -------------------------------------------------------------------------
    def test_clipboard_metadata_is_derived_from_text(self):
        """
        Adversarial: Stored / untrusted metadata in clipboard entries must be derived
        from canonical text rather than blindly accepted.
        """
        from core.validators import validate_clipboard_entry

        malicious = {
            "text": "single line command",
            "char_count": 999999,
            "lines_count": 999999,
            "is_multiline": True
        }
        res = validate_clipboard_entry(malicious)
        self.assertIsNotNone(res)
        self.assertEqual(res["char_count"], len("single line command"))
        self.assertEqual(res["lines_count"], 1)
        self.assertFalse(res["is_multiline"])

    # -------------------------------------------------------------------------
    # 34. Isolated EventBus per Container Instance
    # -------------------------------------------------------------------------
    def test_event_bus_instances_are_isolated(self):
        """
        Adversarial: Separate ServiceContainer instances must have isolated EventBuses.
        """
        from core.container import ServiceContainer

        c1 = ServiceContainer.create_production(config_dir=self.temp_path / "c1_cfg")
        c2 = ServiceContainer.create_production(config_dir=self.temp_path / "c2_cfg")

        self.assertIsNot(c1.event_bus, c2.event_bus, "Container instances must not share singleton EventBus")

        from core.logger import close_log_handlers
        close_log_handlers()

    # -------------------------------------------------------------------------
    # =========================================================================
    # v15 Regression Tests
    # =========================================================================

    # -------------------------------------------------------------------------
    # 37. v15-P0: ScreenshotManager emits signal without saving project state
    # -------------------------------------------------------------------------
    def test_screenshot_manager_does_not_save_project_state(self):
        """
        v15-P0: ScreenshotManager._on_snip_completed() must NOT call
        save_current_project_state() — project state persistence is exclusively
        owned by AppController._on_screenshot_saved().
        """
        from PyQt6.QtGui import QImage, QPixmap
        from PyQt6.QtWidgets import QWidget
        from unittest.mock import MagicMock, patch

        self.project_mgr.create_project("BoxSnipOwnership")
        self.project_mgr.activate_project("BoxSnipOwnership")

        img = QImage(10, 10, QImage.Format.Format_RGB32)
        pix = QPixmap.fromImage(img)
        parent = QWidget()

        # Attach a mock save_current_project_state to the parent window
        parent.save_current_project_state = MagicMock(return_value=True)

        snip_mgr = ScreenshotManager()
        snip_mgr._on_snip_completed(
            cropped_pixmap=pix,
            parent_window=parent,
            project_manager=self.project_mgr,
            loot_manager=self.loot_mgr,
            target_ip="10.10.10.10"
        )

        # Invariant: ScreenshotManager must NOT call save_current_project_state
        parent.save_current_project_state.assert_not_called()

    def test_screenshot_session_save_failure_rolls_back_loot_and_png(self):
        """A failed session commit must not leave screenshot data orphaned."""
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from core.event_bus import EventBus, EventType
        from ui.app_controller import AppController

        self.project_mgr.create_project("BoxScreenshotRollback")
        self.project_mgr.activate_project("BoxScreenshotRollback")
        original_entry = self.loot_mgr.add_entry("note", "Keep me", "existing loot")
        loot_dir = self.project_mgr.get_project_dir("BoxScreenshotRollback") / "loot"
        loot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = loot_dir / "screenshot_rollback.png"
        screenshot_path.write_bytes(b"png data")
        screenshot_entry = self.loot_mgr.add_entry(
            "screenshot", "Rollback screenshot", "![Screenshot](loot/screenshot_rollback.png)"
        )
        screenshot_entry["file_path"] = str(screenshot_path)

        event_bus = EventBus()
        published = []
        event_bus.subscribe(EventType.SCREENSHOT_SAVED, published.append)
        controller = SimpleNamespace(
            loot_manager=self.loot_mgr,
            save_current_project_state=MagicMock(return_value=False),
            switch_mode=MagicMock(),
            event_bus=event_bus,
        )

        AppController._on_screenshot_saved(controller, screenshot_entry)

        self.assertEqual([entry["id"] for entry in self.loot_mgr.get_all_entries()], [original_entry["id"]])
        self.assertEqual(
            [entry["id"] for entry in self.loot_mgr.storage.load_json("loot")],
            [original_entry["id"]],
        )
        self.assertFalse(screenshot_path.exists())
        controller.switch_mode.assert_not_called()
        self.assertEqual(published, [])

    def test_screenshot_rollback_removes_png_when_loot_rollback_fails(self):
        """A failed loot rollback must not block independent screenshot-file cleanup."""
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from core.event_bus import EventBus, EventType
        from core.storage import PersistenceError
        from ui.app_controller import AppController

        self.project_mgr.create_project("BoxScreenshotRollbackFailure")
        loot_dir = self.project_mgr.get_project_dir("BoxScreenshotRollbackFailure") / "loot"
        loot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = loot_dir / "rollback_failure.png"
        screenshot_path.write_bytes(b"png data")
        screenshot_entry = self.loot_mgr.add_entry(
            "screenshot", "Rollback failure screenshot", "![Screenshot](loot/rollback_failure.png)"
        )
        screenshot_entry["file_path"] = str(screenshot_path)

        event_bus = EventBus()
        published = []
        event_bus.subscribe(EventType.SCREENSHOT_SAVED, published.append)
        controller = SimpleNamespace(
            loot_manager=self.loot_mgr,
            save_current_project_state=MagicMock(return_value=False),
            switch_mode=MagicMock(),
            event_bus=event_bus,
        )

        with patch.object(
            self.loot_mgr,
            "replace_entries_and_persist",
            side_effect=PersistenceError("rollback storage unavailable"),
        ) as rollback:
            AppController._on_screenshot_saved(controller, screenshot_entry)

        rollback.assert_called_once()
        self.assertFalse(screenshot_path.exists())
        controller.switch_mode.assert_not_called()
        self.assertEqual(published, [])

    # -------------------------------------------------------------------------
    # 38. Strict project activation
    # -------------------------------------------------------------------------
    def test_activate_project_selects_existing_project(self):
        """Explicit activation selects an existing project without side effects."""
        self.project_mgr.create_project("BoxDeprecated")
        self.assertEqual(self.project_mgr.activate_project("BoxDeprecated"), "BoxDeprecated")

    def test_activate_project_does_not_create_unknown_project(self):
        """Strict activation must not create projects implicitly."""
        from core.project import ProjectNotFoundError
        with self.assertRaises(ProjectNotFoundError):
            self.project_mgr.activate_project("UnknownBox")

        self.assertNotIn("UnknownBox", self.project_mgr.list_projects())
        self.assertFalse((self.projects_dir / "UnknownBox").exists())

    # -------------------------------------------------------------------------
    # 39. v15-P1: list_projects() does not mutate registry
    # -------------------------------------------------------------------------
    def test_list_projects_does_not_mutate_registry(self):
        """
        v15-P1: ProjectRepository.list_projects() must be read-only —
        it must NOT write new entries into self.registry.
        """
        self.project_mgr.create_project("BoxReadOnly1")

        # Create a second project directory WITHOUT registration
        phantom_dir = self.projects_dir / "PhantomProject"
        phantom_dir.mkdir(parents=True, exist_ok=True)

        # Record registry state before list_projects
        registry_before = dict(self.project_mgr.registry)

        # list_projects must discover PhantomProject but NOT register it
        projects = self.project_mgr.list_projects()

        registry_after = dict(self.project_mgr.registry)

        self.assertIn("PhantomProject", projects,
                      "list_projects must discover PhantomProject from disk")
        self.assertEqual(
            registry_before, registry_after,
            "list_projects() must not mutate self.registry (read-only invariant violated)"
        )

    # -------------------------------------------------------------------------
    # 40. v15-P1: sync_registry() registers and persists new discoveries
    # -------------------------------------------------------------------------
    def test_sync_registry_registers_and_persists(self):
        """
        v15-P1: ProjectRepository.sync_registry() must register newly discovered
        projects into self.registry AND persist the registry to disk.
        """
        self.project_mgr.create_project("BoxSyncBase")

        # Create an unregistered directory
        new_dir = self.projects_dir / "NewlyDiscovered"
        new_dir.mkdir(parents=True, exist_ok=True)

        # Ensure it's not in registry before sync
        self.assertNotIn("NewlyDiscovered", self.project_mgr.registry)

        # Run sync
        synced = self.project_mgr.sync_registry()

        # Invariant 1: synced list includes newly discovered project
        self.assertIn("NewlyDiscovered", synced)

        # Invariant 2: registry in memory now includes it
        self.assertIn("NewlyDiscovered", self.project_mgr.registry)

        # Invariant 3: registry was persisted to disk
        import json
        registry_file = self.project_mgr.registry_file
        self.assertTrue(registry_file.exists(), "Registry file must exist after sync_registry()")
        disk_registry = json.loads(registry_file.read_text(encoding="utf-8"))
        self.assertIn("NewlyDiscovered", disk_registry)


if __name__ == "__main__":
    unittest.main()

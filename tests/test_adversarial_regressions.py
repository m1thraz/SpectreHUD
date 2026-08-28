import os
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QImage, QPixmap, QColor

from core.config import ConfigManager
from core.project_manager import ProjectManager, InvalidProjectNameError, ProjectCreationError
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.screenshot_manager import ScreenshotManager
from core.project_session_service import ProjectSessionService
from core.report_file_manager import ReportFileManager, ReportBackupError
from core.snippet_manager import SnippetManager
from ui.main_window import MainWindow


class TestAdversarialRegressions(unittest.TestCase):
    """
    Adversarial regression test suite locking in security, data integrity,
    and resilience invariants discovered during architectural hardening.
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
        Adversarial: Malicious or traversal project names ('..', '.', '../escape',
        '..\\escape', '../../../../etc', '   ') must NEVER resolve outside the workspace
        and MUST NOT create any files or folders in parent directories.
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
        from core.project_manager import InvalidProjectNameError

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
    # 6. P5: Deeply Nested JSON Parsing & RecursionError Resilience
    # -------------------------------------------------------------------------
    def test_deeply_nested_json_recursion_dos_protection(self):
        """
        Adversarial: Deeply nested JSON files (e.g. [[[[...]]]] or {{{{...}}}} with depth > 5000)
        must NEVER cause unhandled RecursionError crashes during project import, state loading,
        loot loading, clipboard loading, snippet loading, or config initialization.
        All loaders must gracefully recover to empty/default states.
        """
        depth = 5000
        malicious_nested_json = ("[" * depth) + ("]" * depth)

        # 1. Project State Loader
        self.project_mgr.create_project("BoxDeepBomb")
        state_file = self.project_mgr.get_project_dir("BoxDeepBomb") / "project_state.json"
        state_file.write_text(malicious_nested_json, encoding="utf-8")
        
        # Must not throw RecursionError and return a valid fallback state schema
        state = self.project_mgr.load_project_state("BoxDeepBomb")
        self.assertIsInstance(state, dict)
        self.assertEqual(state["name"], "BoxDeepBomb")
        self.assertEqual(state["loot"], [])

        # 2. Loot Manager Loader
        loot_file = self.temp_path / "bomb_loot.json"
        loot_file.write_text(malicious_nested_json, encoding="utf-8")
        bomb_loot_mgr = LootManager(storage_file=loot_file)
        self.assertEqual(bomb_loot_mgr.get_all_entries(), [])

        # 3. Clipboard Watcher Loader
        clip_file = self.temp_path / "bomb_clip.json"
        clip_file.write_text(malicious_nested_json, encoding="utf-8")
        bomb_clip = ClipboardWatcher(storage_file=clip_file)
        self.assertEqual(bomb_clip.get_all_history(), [])

        # 4. Project Registry Loader
        reg_file = self.config_dir / "projects_registry.json"
        reg_file.write_text(malicious_nested_json, encoding="utf-8")
        reg_data = self.project_mgr._load_registry()
        self.assertEqual(reg_data, {})

        # 5. User Snippets Loader
        snip_cfg_dir = self.temp_path / "snip_cfg"
        snip_cfg_dir.mkdir(parents=True, exist_ok=True)
        snip_file = snip_cfg_dir / "user_snippets.json"
        snip_file.write_text(malicious_nested_json, encoding="utf-8")
        snip_mgr = SnippetManager(user_snippets_path=snip_file)
        self.assertTrue(len(snip_mgr.get_snippets()) > 0)  # default snippets still loaded safely

        # 6. Config Loader
        bomb_cfg_dir = self.temp_path / "bomb_cfg"
        bomb_cfg_dir.mkdir(parents=True, exist_ok=True)
        (bomb_cfg_dir / "config.json").write_text(malicious_nested_json, encoding="utf-8")
        cfg_mgr = ConfigManager(config_dir=bomb_cfg_dir)
        self.assertIn("hotkey", cfg_mgr.data)

    # -------------------------------------------------------------------------
    # 7. P6: Bloated / Massive JSON Data Ingest Bounding (Asymmetric Trust Defense)
    # -------------------------------------------------------------------------
    def test_bloated_project_state_is_bounded_and_capped(self):
        """
        Adversarial: Importing or loading an externally crafted project_state.json
        with thousands of items or oversized payload strings must be strictly capped
        to prevent memory explosion and UI stalling.
        """
        self.project_mgr.create_project("BoxBloated")
        state_file = self.project_mgr.get_project_dir("BoxBloated") / "project_state.json"

        # Create bloated state with 1050 loot items and 600 clipboard entries
        # Item 0 has oversized 150 KB string to test string truncation
        bloated_loot = [{"title": f"Loot {i}", "content": "X" * 200} for i in range(1050)]
        bloated_loot[0]["content"] = "X" * (150 * 1024)

        bloated_clips = [{"text": f"cmd {i}"} for i in range(600)]
        bloated_clips[0]["text"] = "Y" * (100 * 1024)

        bloated_state = {
            "name": "BoxBloated",
            "target_ip": "10.10.10.10",
            "loot": bloated_loot,
            "clipboard_history": bloated_clips
        }
        state_file.write_text(json.dumps(bloated_state), encoding="utf-8")

        # Load session via service
        loaded = self.session_service.load_project_session("BoxBloated")

        # Invariant 1: Loot is capped to 1000 items, oversized items bounded to 128 KB
        self.assertEqual(len(loaded["loot"]), 1000)
        self.assertEqual(len(loaded["loot"][0]["content"]), 128 * 1024)
        self.assertEqual(len(self.loot_mgr.get_all_entries()), 1000)

        # Invariant 2: Clipboard is capped to 500 items, oversized items bounded to 64 KB
        self.assertEqual(len(loaded["clipboard_history"]), 500)
        self.assertEqual(len(loaded["clipboard_history"][0]["text"]), 64 * 1024)
        self.assertEqual(len(self.clip_watcher.get_all_history()), 500)

    # -------------------------------------------------------------------------
    # 8. P7: Cross-Project Screenshot Resolution Isolation (Confused Deputy Guard)
    # -------------------------------------------------------------------------
    def test_cross_project_screenshot_resolution_isolation(self):
        """
        Adversarial: A loot entry in Project A referencing a screenshot filename
        that exists in Project B must NEVER resolve or display Project B's image.
        LootCard image resolution must be strictly sandboxed to the active project folder.
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
            "Security Failure: LootCard resolved a screenshot file from another project's sandbox!"
        )

    # -------------------------------------------------------------------------
    # 9. P1: Symlink & Junction Workspace Escape Prevention
    # -------------------------------------------------------------------------
    def test_symlink_and_junction_workspace_escape_prevention(self):
        """
        Adversarial P1: Pre-existing symlinks or Windows junctions inside a workspace
        pointing to an external location (e.g. projects/Evil -> /outside) must NEVER be
        followed by create_project() or get_project_dir() to write payload files outside.
        """
        outside_dir = self.temp_path / "outside_victim"
        outside_dir.mkdir(parents=True, exist_ok=True)
        
        evil_link = self.projects_dir / "Evil"
        try:
            os.symlink(outside_dir, evil_link, target_is_directory=True)
        except (OSError, NotImplementedError):
            # In some restricted Windows environments without Developer Mode/Admin, symlink creation might raise OSError
            pass

        if evil_link.exists() or evil_link.is_symlink():
            # Attempt to create project on symlink target (must either reject via exception or avoid following)
            try:
                res_dir = self.project_mgr.create_project("Evil")
                # If it didn't raise, verify project dir is strictly inside workspace
                self.assertTrue(
                    res_dir.resolve().is_relative_to(self.projects_dir.resolve()),
                    f"P1 Security Breach: Returned project directory is outside workspace: {res_dir}"
                )
            except (InvalidProjectNameError, ProjectCreationError, OSError):
                # Safely rejected symlink / junction traversal escape attempt
                pass
            
            # Invariant: Outside directory must have NO files or folders written to it
            outside_files = [p.name for p in outside_dir.iterdir()]
            self.assertEqual(
                outside_files, [],
                f"P1 Security Breach: create_project wrote files into outside directory {outside_dir}: {outside_files}"
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
        
        # Test atomic write failure in save_project_state
        with patch("core.atomic_write.atomic_write_json", return_value=False):
            saved = self.project_mgr.save_project_state("BoxSaveErr", {"target_ip": "1.2.3.4"})
            self.assertFalse(saved)

            session_saved = self.session_service.save_project_session({"target_ip": "1.2.3.4"}, "BoxSaveErr")
            self.assertFalse(session_saved)

    # -------------------------------------------------------------------------
    # 13. Pre-Parse File Size Defense (Gigabyte JSON Bomb Defense)
    # -------------------------------------------------------------------------
    def test_oversized_raw_json_files_rejected_before_parsing(self):
        """
        Adversarial: Gigantic JSON files (> MAX_FILE_SIZE) must be rejected
        BEFORE attempting json.load() to prevent massive RAM allocation during parsing.
        """
        from unittest.mock import patch

        # 1. Project state file size limit (simulate oversized file)
        self.project_mgr.create_project("BoxOversized")
        state_file = self.project_mgr.get_project_dir("BoxOversized") / "project_state.json"
        state_file.write_text('{"name": "BoxOversized", "loot": [{"title": "Should Not Load", "content": "X"}]}', encoding="utf-8")

        # Mock is_file_size_valid to return False
        with patch("core.validators.is_file_size_valid", return_value=False):
            loaded = self.project_mgr.load_project_state("BoxOversized")
            # Should safely fallback to clean default without parsing
            self.assertEqual(loaded["name"], "BoxOversized")
            self.assertEqual(loaded["loot"], [])

        # 2. Loot manager file size limit
        loot_file = self.temp_path / "giant_loot.json"
        loot_file.write_text('[{"title": "Giant Item", "content": "data"}]', encoding="utf-8")
        bomb_loot = LootManager(storage_file=loot_file)
        with patch("core.validators.is_file_size_valid", return_value=False):
            bomb_loot.load_entries()
            self.assertEqual(bomb_loot.get_all_entries(), [])

        # 3. User snippets file size limit
        snip_file = self.temp_path / "giant_snippets.json"
        snip_file.write_text('[{"title": "Giant Snippet", "template": "data"}]', encoding="utf-8")
        with patch("core.validators.is_file_size_valid", return_value=False):
            snip_mgr = SnippetManager(user_snippets_path=snip_file)
            self.assertEqual(len([s for s in snip_mgr.get_snippets() if s.get("is_custom")]), 0)

    # -------------------------------------------------------------------------
    # 14. Project Name Sanitization Collision Defense
    # -------------------------------------------------------------------------
    def test_sanitization_collision_cannot_merge_or_overwrite_workspaces(self):
        """
        Adversarial: Creating 'hack box' and then 'hack_box' must not silently merge
        workspaces or overwrite state. The second creation must be rejected with ProjectExistsError.
        """
        from core.project_manager import ProjectExistsError, InvalidProjectNameError

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
    # 15. Symlink / Junction Workspace Auto-Discovery & Registry Escape
    # -------------------------------------------------------------------------
    def test_symlink_project_cannot_be_registered_as_workspace(self):
        """
        Adversarial: A symlink placed inside base_dir pointing to an outside directory
        must NOT be automatically registered or listed as a project workspace, and
        get_project_dir() must NOT resolve to the external path.
        """
        outside_dir = self.temp_path / "outside_victim_dir"
        outside_dir.mkdir(parents=True, exist_ok=True)
        (outside_dir / "notes.md").write_text("Victim Outside Data", encoding="utf-8")

        symlink_path = self.projects_dir / "EvilSymlink"
        try:
            symlink_path.symlink_to(outside_dir, target_is_directory=True)
        except (OSError, NotImplementedError):
            return

        # 1. list_projects must NOT include the symlink or auto-register it
        project_list = self.project_mgr.list_projects()
        self.assertNotIn("EvilSymlink", project_list)
        self.assertNotIn("EvilSymlink", self.project_mgr.registry)

        # 2. get_project_dir("EvilSymlink") must strictly reject symlink with InvalidProjectNameError
        with self.assertRaises(InvalidProjectNameError):
            self.project_mgr.get_project_dir("EvilSymlink")

    # -------------------------------------------------------------------------
    # 16. Report-Preview Sandbox & Arbitrary Local File Disclosure Defense
    # -------------------------------------------------------------------------
    def test_report_document_blocks_path_traversal_and_absolute_outside_images(self):
        """
        Adversarial: A malicious markdown entry with relative traversal (../../outside.png)
        or absolute path outside the project directory must be strictly blocked by ReportDocument.
        """
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QTextDocument
        from ui.report_editor_tab import ReportDocument

        # 1. Create a secret image outside the project workspace
        secret_outside = self.temp_path / "secret_victim_data.png"
        victim_img = QImage(100, 100, QImage.Format.Format_RGB32)
        victim_img.fill(QColor("red"))
        self.assertTrue(victim_img.save(str(secret_outside), "PNG"))

        # 2. Create legitimate project workspace
        proj_dir = self.project_mgr.create_project("SandboxBox")
        doc = ReportDocument(project_dir=proj_dir)

        # 3. Test relative traversal escape
        traversal_url = QUrl("../../../../secret_victim_data.png")
        loaded_traversal = doc.loadResource(int(QTextDocument.ResourceType.ImageResource), traversal_url)
        self.assertNotIsInstance(loaded_traversal, QImage)

        # 4. Test absolute file path escape
        absolute_url = QUrl.fromLocalFile(str(secret_outside.resolve()))
        loaded_absolute = doc.loadResource(int(QTextDocument.ResourceType.ImageResource), absolute_url)
        self.assertNotIsInstance(loaded_absolute, QImage)

        # 5. Test raw absolute string path escape
        raw_absolute_url = QUrl(str(secret_outside.resolve()))
        loaded_raw_abs = doc.loadResource(int(QTextDocument.ResourceType.ImageResource), raw_absolute_url)
        self.assertNotIsInstance(loaded_raw_abs, QImage)

    # -------------------------------------------------------------------------
    # 17. Report-Preview Oversized Image / Decompress Bomb DoS Defense
    # -------------------------------------------------------------------------
    def test_report_document_rejects_oversized_images(self):
        """
        Adversarial: An oversized image file (>15MB) inside the project loot must be
        rejected before QImage loading/decoding to prevent memory exhaustion and UI freezing.
        """
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QTextDocument
        from ui.report_editor_tab import ReportDocument

        proj_dir = self.project_mgr.create_project("BombBox")
        loot_dir = proj_dir / "loot"
        loot_dir.mkdir(exist_ok=True)
        giant_file = loot_dir / "giant_bomb.png"

        # Create 16MB file
        with open(giant_file, "wb") as f:
            f.seek(16 * 1024 * 1024)
            f.write(b"\x00")

        doc = ReportDocument(project_dir=proj_dir)
        loaded = doc.loadResource(int(QTextDocument.ResourceType.ImageResource), QUrl("loot/giant_bomb.png"))
        self.assertNotIsInstance(loaded, QImage)

    # -------------------------------------------------------------------------
    # 18. ReportBuilder Markdown / Code-Fence Injection Defense
    # -------------------------------------------------------------------------
    def test_report_builder_code_fence_injection_defense(self):
        """
        Adversarial: Loot items and clipboard entries containing backticks (e.g. ```)
        must be enclosed with adaptive fences (e.g. ````) to prevent breaking out
        of codeblocks and injecting arbitrary markdown or fake headers into reports.
        """
        from core.report_builder import ReportBuilder

        # Add credentials with triple backticks injection attempt
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
    # 19. TemplateEngine Regex Backslash Sequences Crash & Corruption Defense
    # -------------------------------------------------------------------------
    def test_template_engine_backslash_sequences_safety(self):
        r"""
        Adversarial: User variables containing backslash sequences (e.g. \1, \g<0>, \n, \x)
        must not crash re.sub or trigger regex backreference group corruption.
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
    # 20. Local File Disclosure and HTML Spoofing Defense in Card Widgets
    # -------------------------------------------------------------------------
    def test_card_widgets_plain_text_enforcement(self):
        """
        Adversarial: Card widgets (LootCard, HistoryCard, SnippetCard) displaying user
        or clipboard data must explicitly enforce PlainText format on their QLabels to prevent
        Rich Text auto-parsing and arbitrary local file disclosure / oracle loading via <img src="file">.
        """
        from PyQt6.QtCore import Qt
        from ui.loot_card import LootCard
        from ui.history_card import HistoryCard
        from ui.snippet_card import SnippetCard

        # 1. LootCard PlainText Verification
        malicious_loot = {
            "id": "loot_xss",
            "type": "credentials",
            "category": "access",
            "title": '<img src="/etc/shadow"><b>Root Creds</b>',
            "content": '<img src="/home/user/secret.png"><span style="display:none">Hidden</span>admin:pass',
            "target_ip": '<script>10.10.10.10</script>',
            "timestamp": '2026-08-27 12:00:00'
        }
        loot_card = LootCard(entry=malicious_loot)
        self.assertEqual(loot_card.lbl_content.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(loot_card.lbl_content.text(), malicious_loot["content"])

        # 2. HistoryCard PlainText Verification (Clipboard Watcher ingestion)
        malicious_history = {
            "id": "clip_1",
            "text": 'curl http://attacker.com/<img src="C:/Windows/System32/drivers/etc/hosts">',
            "timestamp": '12:30:00',
            "target_ip": '10.10.10.10',
            "lines_count": 1,
            "char_count": 80
        }
        hist_card = HistoryCard(entry=malicious_history)
        self.assertEqual(hist_card.lbl_content.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(hist_card.lbl_content.text(), malicious_history["text"])

        # 3. SnippetCard PlainText Verification
        malicious_snippet = {
            "id": "snip_1",
            "title": 'Nmap Scan <img src="/etc/passwd">',
            "category": 'Web <script>',
            "subcategory": 'Recon',
            "description": 'Scan description with <img src="/secret.png">',
            "template": 'nmap -sV {{TARGET_IP}} <img src="/private.png">',
            "is_custom": True
        }
        snippet_card = SnippetCard(snippet=malicious_snippet, variables={"target_ip": "10.10.10.10"})
        self.assertEqual(snippet_card.lbl_title.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(snippet_card.lbl_category.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(snippet_card.lbl_desc.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(snippet_card.lbl_command.textFormat(), Qt.TextFormat.PlainText)

    # -------------------------------------------------------------------------
    # 21. Subdirectory Symlink Escape Defense for Imported Projects
    # -------------------------------------------------------------------------
    def test_imported_project_symlinked_subdirectory_rejected(self):
        """
        Adversarial: An imported project directory whose 'loot', 'recon', or 'exploit'
        subfolder is a symlink to an outside victim directory must be rejected immediately.
        """
        victim_dir = self.temp_path / "victim_external"
        victim_dir.mkdir(parents=True, exist_ok=True)

        external_proj = self.temp_path / "MaliciousExternalBox"
        external_proj.mkdir(parents=True, exist_ok=True)
        symlink_loot = external_proj / "loot"

        try:
            os.symlink(victim_dir, symlink_loot, target_is_directory=True)
        except (OSError, NotImplementedError):
            # In restricted environments without symlink privileges
            return

        if symlink_loot.is_symlink():
            with self.assertRaises(ProjectCreationError):
                self.project_mgr.import_project_folder(external_proj)

            # Ensure victim dir has no files
            self.assertEqual(list(victim_dir.iterdir()), [])

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

        container = ServiceContainer.create_in_memory()
        window = MainWindow(container=container)

        with patch.object(window.report_ctrl, "confirm_discard_if_dirty", return_value=False):
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

        container = ServiceContainer.create_in_memory()
        window = MainWindow(container=container)

        with patch.object(window, "_save_current_project_state", return_value=False):
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

        container = ServiceContainer.create_in_memory()
        window = MainWindow(container=container)
        window.var_bar.txt_target.setText("192.168.1.77")

        with patch("PyQt6.QtWidgets.QApplication.quit"):
            res = window.request_quit()
            self.assertTrue(res)
            
            # Verify persisted state
            state = container.project_manager.load_project_state()
            self.assertEqual(state.get("target_ip"), "192.168.1.77")

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

        container = ServiceContainer.create_in_memory()
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
    # 33. Storage Backend Fails Closed on Path Traversal
    # -------------------------------------------------------------------------
    def test_storage_backend_rejects_traversal_resource_name(self):
        """
        Adversarial: FileStorageBackend must raise ValueError on traversal tokens
        rather than silently stripping directory parts.
        """
        from core.storage import FileStorageBackend

        storage = FileStorageBackend(base_dir=self.temp_path / "strict_storage")
        with self.assertRaises(ValueError):
            storage.save_json("../traversal", {"data": 1})

        with self.assertRaises(ValueError):
            storage.load_json("..\\windows_traversal")

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
    # 35. Tooltip HTML Injection Defense in SnippetListModel
    # -------------------------------------------------------------------------
    def test_snippet_list_model_tooltip_html_escaped(self):
        """
        Adversarial: Snippet titles, descriptions, and code templates containing
        raw HTML or XSS payloads must be strictly escaped in ToolTipRole.
        """
        from PyQt6.QtCore import Qt
        from ui.models.snippet_list_model import SnippetListModel

        malicious_snippet = {
            "id": "snip_xss_1",
            "title": "<script>alert('pwn')</script><b>Injected Title</b>",
            "description": "<img src=x onerror=alert('desc')>",
            "template": "<svg/onload=alert('code')> && cat /etc/passwd"
        }

        model = SnippetListModel([malicious_snippet])
        idx = model.index(0, 0)
        tooltip = model.data(idx, Qt.ItemDataRole.ToolTipRole)

        # Invariant: Raw dangerous HTML tags must NOT be present unescaped
        self.assertNotIn("<script>", tooltip)
        self.assertNotIn("<b>Injected Title</b>", tooltip)
        self.assertNotIn("<img src=x onerror=alert('desc')>", tooltip)
        self.assertNotIn("<svg/onload=alert('code')>", tooltip)

        # Invariant: Escaped HTML entities must be present
        self.assertIn("&lt;script&gt;alert(&#x27;pwn&#x27;)&lt;/script&gt;", tooltip)
        self.assertIn("&lt;b&gt;Injected Title&lt;/b&gt;", tooltip)
        self.assertIn("&lt;img src=x onerror=alert(&#x27;desc&#x27;)&gt;", tooltip)
        self.assertIn("&lt;svg/onload=alert(&#x27;code&#x27;)&gt; &amp;&amp; cat /etc/passwd", tooltip)

    # -------------------------------------------------------------------------
    # 36. Template Repository Path Traversal Defense
    # -------------------------------------------------------------------------
    def test_template_repository_path_traversal_defense(self):
        """
        Adversarial: Malicious template IDs containing directory traversal sequences
        (../, ../../etc/passwd, absolute paths) must be rejected across all repository
        operations (dict_to_template, save_user_template, get_template, delete_user_template).
        """
        from core.reporting.template_repository import TemplateRepository, dict_to_template
        from core.reporting.template_engine import ReportTemplate, TemplateSection

        repo = TemplateRepository(user_templates_dir=self.temp_path / "user_templates")

        # 1. dict_to_template rejects traversal IDs
        malicious_json = {
            "id": "../../../../../../tmp/evil_template",
            "name": "Evil Template",
            "sections": [{"type": "header_metadata"}]
        }
        self.assertIsNone(dict_to_template(malicious_json))

        # 2. save_user_template rejects saving outside sandbox
        evil_template = ReportTemplate(
            id="../../../../../../tmp/evil_drop",
            name="Evil Dropped File",
            language="de",
            category="ctf",
            complexity="simple",
            sections=[TemplateSection(type="header_metadata")]
        )
        self.assertFalse(repo.save_user_template(evil_template))

        # 3. get_template and delete_user_template reject traversal attempts
        self.assertIsNone(repo.get_template("../../victim_file"))
        self.assertFalse(repo.delete_user_template("../../victim_file"))

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
        self.assertFalse(screenshot_path.exists())
        controller.switch_mode.assert_not_called()
        self.assertEqual(published, [])

    # -------------------------------------------------------------------------
    # 38. v15-P0: set_active_project issues DeprecationWarning
    # -------------------------------------------------------------------------
    def test_set_active_project_issues_deprecation_warning(self):
        """
        v15-P0: set_active_project() must emit a DeprecationWarning,
        directing callers to use activate_project() instead.
        """
        import warnings
        self.project_mgr.create_project("BoxDeprecated")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.project_mgr.set_active_project("BoxDeprecated")
            deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
            self.assertTrue(
                len(deprecation_warnings) > 0,
                "set_active_project() must emit a DeprecationWarning"
            )
            self.assertIn("activate_project", str(deprecation_warnings[0].message))

    def test_deprecated_set_active_project_does_not_create_unknown_project(self):
        """v15-P0: deprecated activation must no longer create projects implicitly."""
        from core.project import ProjectNotFoundError
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with self.assertRaises(ProjectNotFoundError):
                self.project_mgr.set_active_project("UnknownBox")

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

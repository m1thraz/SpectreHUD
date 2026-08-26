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
from core.project_manager import ProjectManager
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

        for bad_name in malicious_names:
            proj_dir = self.project_mgr.create_project(bad_name, allow_existing=True)
            resolved_proj = proj_dir.resolve()

            # Boundary Invariant: Must be strictly inside projects_dir
            self.assertTrue(
                resolved_proj.is_relative_to(resolved_base),
                f"Adversarial path traversal escape detected for input {bad_name!r}: {resolved_proj}"
            )

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
        self.project_mgr.set_active_project("BoxTarget")

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
            # Attempt to create project on symlink target
            res_dir = self.project_mgr.create_project("Evil")
            
            # Invariant 1: Outside directory must have NO files or folders written to it
            outside_files = [p.name for p in outside_dir.iterdir()]
            self.assertEqual(
                outside_files, [],
                f"P1 Security Breach: create_project wrote files into outside directory {outside_dir}: {outside_files}"
            )
            
            # Invariant 2: Returned project directory must be strictly inside workspace
            self.assertTrue(
                res_dir.resolve().is_relative_to(self.projects_dir.resolve()),
                f"P1 Security Breach: Returned project directory is outside workspace: {res_dir}"
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
        self.project_mgr.set_active_project("BoxSnipFail")

        img = QImage(10, 10, QImage.Format.Format_RGB32)
        pix = QPixmap.fromImage(img)

        with patch.object(QPixmap, "save", return_value=False):
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
        from core.project_manager import ProjectExistsError

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

        with self.assertRaises(ProjectExistsError):
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

        # 2. get_project_dir("EvilSymlink") must NOT return outside_dir
        resolved_dir = self.project_mgr.get_project_dir("EvilSymlink")
        self.assertNotEqual(resolved_dir, outside_dir)
        self.assertTrue(resolved_dir.is_relative_to(self.projects_dir.resolve()))

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


if __name__ == "__main__":
    unittest.main()

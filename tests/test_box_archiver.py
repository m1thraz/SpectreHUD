import unittest
import tempfile
import zipfile
from pathlib import Path
from core.box_archiver import BoxArchiver
from core.project_manager import ProjectManager


class TestBoxArchiver(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name) / "projects"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.project_manager = ProjectManager(base_dir=self.base_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_archive_project_lifecycle(self):
        # 1. Create a project
        proj_dir = self.project_manager.create_project("ArchiveBoxTest", target_ip="10.10.10.77")
        
        # 2. Add some files to subdirectories
        (proj_dir / "notes.md").write_text("# Test Notes\nFound user flag.", encoding="utf-8")
        (proj_dir / "recon" / "nmap.txt").write_text("22/tcp open ssh\n80/tcp open http", encoding="utf-8")
        (proj_dir / "loot" / "test_screen.png").write_bytes(b"\x89PNG\r\n\x1a\ndummy")
        (proj_dir / "loot" / "temp.tmp").write_text("temporary data", encoding="utf-8")

        # 3. Archive project
        out_zip = self.base_dir / "ArchiveBoxTest.zip"
        res = self.project_manager.archive_project("ArchiveBoxTest", out_zip)

        self.assertTrue(res["success"])
        self.assertTrue(out_zip.exists())
        self.assertGreater(res["file_count"], 0)
        self.assertGreater(res["compressed_bytes"], 0)

        # 4. Verify ZIP archive contents
        self.assertTrue(zipfile.is_zipfile(out_zip))
        with zipfile.ZipFile(out_zip, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("ArchiveBoxTest/notes.md", namelist)
            self.assertIn("ArchiveBoxTest/project_state.json", namelist)
            self.assertIn("ArchiveBoxTest/recon/nmap.txt", namelist)
            self.assertIn("ArchiveBoxTest/loot/test_screen.png", namelist)
            # Excluded extension .tmp must not be included
            self.assertNotIn("ArchiveBoxTest/loot/temp.tmp", namelist)

            # Test reading back content
            notes_extracted = zf.read("ArchiveBoxTest/notes.md").decode("utf-8")
            self.assertIn("Found user flag.", notes_extracted)

    def test_archive_nonexistent_project_fails_safely(self):
        fake_path = self.base_dir / "NonExistentFolder"
        res = BoxArchiver.archive_project(fake_path)
        self.assertFalse(res["success"])
        self.assertIn("does not exist", res["error"])


if __name__ == "__main__":
    unittest.main()

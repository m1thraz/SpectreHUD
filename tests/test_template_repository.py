import unittest
import tempfile
import json
import sys
from pathlib import Path
from unittest.mock import patch

from core.reporting.template_repository import (
    TemplateRepository,
    template_to_dict,
    dict_to_template
)
from core.reporting.template_engine import ReportTemplate, TemplateSection


class TestTemplateRepository(unittest.TestCase):
    """Unit tests for the Template Repository (built-in discovery, user overrides, CRUD)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.temp_path = Path(self.temp_dir.name)
        self.user_dir = self.temp_path / "user_templates"
        self.repo = TemplateRepository(user_templates_dir=self.user_dir)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_discover_builtin_templates(self):
        """Discovers all 8 built-in templates from data/report_templates."""
        builtins = self.repo.get_builtin_templates()
        self.assertGreaterEqual(len(builtins), 8)

        ids = [t.id for t in builtins]
        self.assertIn("ctf_walkthrough_de", ids)
        self.assertIn("ctf_walkthrough_en", ids)
        self.assertIn("ctf_quick_de", ids)
        self.assertIn("ctf_quick_en", ids)
        self.assertIn("pentest_standard_de", ids)
        self.assertIn("pentest_standard_en", ids)
        self.assertIn("pentest_executive_de", ids)
        self.assertIn("pentest_executive_en", ids)

        # Check fields
        for t in builtins:
            self.assertTrue(t.is_builtin)
            self.assertIn(t.language, ("de", "en"))
            self.assertIn(t.category, ("ctf", "pentest"))
            self.assertIn(t.complexity, ("simple", "complex"))
            self.assertGreater(len(t.sections), 0)

    def test_frozen_build_reads_bundled_report_templates(self):
        """The one-file EXE must use its unpacked report template directory."""
        bundle_dir = self.temp_path / "bundle"
        bundled_templates = bundle_dir / "data" / "report_templates"
        bundled_templates.mkdir(parents=True)
        (bundled_templates / "only_bundle.json").write_text(
            json.dumps({
                "id": "only_bundle", "name": "Bundled", "language": "en",
                "category": "ctf", "complexity": "simple",
                "sections": [{"type": "header_metadata"}],
            }),
            encoding="utf-8",
        )

        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", str(bundle_dir), create=True):
            repo = TemplateRepository(user_templates_dir=self.user_dir)
            self.assertEqual(repo.builtin_dir, bundled_templates)
            self.assertEqual([template.id for template in repo.get_builtin_templates()], ["only_bundle"])

    def test_save_and_load_user_template(self):
        """User can create and persist custom templates."""
        custom_t = ReportTemplate(
            id="my_custom_template",
            name="My Custom Template",
            language="en",
            category="pentest",
            complexity="simple",
            sections=[
                TemplateSection(type="header_metadata", title="Custom Audit"),
                TemplateSection(type="executive_summary")
            ]
        )
        saved = self.repo.save_user_template(custom_t)
        self.assertTrue(saved)

        loaded = self.repo.get_template("my_custom_template")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "My Custom Template")
        self.assertFalse(loaded.is_builtin)
        self.assertEqual(len(loaded.sections), 2)

    def test_user_template_overrides_builtin(self):
        """User template with same ID overrides the built-in version in get_all_templates()."""
        override_t = ReportTemplate(
            id="pentest_standard_de",
            name="Pentest Standard-Bericht (Overridden)",
            language="de",
            category="pentest",
            complexity="complex",
            sections=[
                TemplateSection(type="header_metadata", title="Overridden Header")
            ]
        )
        self.repo.save_user_template(override_t)

        active = self.repo.get_template("pentest_standard_de")
        self.assertEqual(active.name, "Pentest Standard-Bericht (Overridden)")
        self.assertFalse(active.is_builtin)

        # Delete user override -> restores built-in
        self.repo.delete_user_template("pentest_standard_de")
        restored = self.repo.get_template("pentest_standard_de")
        self.assertEqual(restored.name, "Pentest Standard-Bericht (DE)")
        self.assertTrue(restored.is_builtin)

    def test_corrupted_or_oversized_template_handling(self):
        """Corrupted JSON or oversized files are skipped safely."""
        corrupt_file = self.user_dir / "corrupt.json"
        corrupt_file.write_text("{invalid json", encoding="utf-8")

        oversized_file = self.user_dir / "huge.json"
        oversized_file.write_bytes(b"A" * (600 * 1024))  # 600 KB > 512 KB limit

        user_templates = self.repo.get_user_templates()
        ids = [t.id for t in user_templates]
        self.assertNotIn("corrupt", ids)
        self.assertNotIn("huge", ids)

    def test_path_traversal_prevention(self):
        """Path traversal IDs in dict_to_template, save, get, and delete are strictly rejected."""
        evil_ids = [
            "../../../../../../tmp/evil_file",
            "../victim",
            "foo/bar",
            "foo\\bar",
            "bad*id",
            "",
            "a" * 65  # Too long
        ]

        # 1. dict_to_template rejects evil IDs
        for bad_id in evil_ids:
            bad_dict = {
                "id": bad_id,
                "name": "Evil Template",
                "sections": [{"type": "header_metadata"}]
            }
            self.assertIsNone(dict_to_template(bad_dict), f"dict_to_template should reject {bad_id}")

        # 2. save_user_template rejects evil template IDs
        evil_template = ReportTemplate(
            id="../../../../../tmp/evil_dropped",
            name="Evil Dropped",
            language="de",
            category="ctf",
            complexity="simple",
            sections=[TemplateSection(type="header_metadata")]
        )
        self.assertFalse(self.repo.save_user_template(evil_template))
        
        # Verify file was NOT created outside sandbox
        potential_escape = Path(tempfile.gettempdir()) / "evil_dropped.json"
        self.assertFalse(potential_escape.exists())

        # 3. get_template and delete_user_template reject traversal IDs
        self.assertIsNone(self.repo.get_template("../../something"))
        self.assertFalse(self.repo.delete_user_template("../../something"))


if __name__ == "__main__":
    unittest.main()

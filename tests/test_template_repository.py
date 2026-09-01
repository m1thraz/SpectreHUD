import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.reporting.template_engine import ReportTemplate, TemplateSection
from core.reporting.template_repository import TemplateRepository


class TestTemplateRepository(unittest.TestCase):
    """Unit tests for built-in discovery, user overrides, and normal CRUD."""

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
        """Discovers all eight built-in templates from data/report_templates."""
        builtins = self.repo.get_builtin_templates()
        self.assertGreaterEqual(len(builtins), 8)

        ids = [template.id for template in builtins]
        self.assertTrue(
            {
                "ctf_walkthrough_de",
                "ctf_walkthrough_en",
                "ctf_quick_de",
                "ctf_quick_en",
                "pentest_standard_de",
                "pentest_standard_en",
                "pentest_executive_de",
                "pentest_executive_en",
            }.issubset(ids)
        )

        for template in builtins:
            self.assertTrue(template.is_builtin)
            self.assertIn(template.language, ("de", "en"))
            self.assertIn(template.category, ("ctf", "pentest"))
            self.assertIn(template.complexity, ("simple", "complex"))
            self.assertGreater(len(template.sections), 0)

    def test_frozen_build_reads_bundled_report_templates(self):
        """The one-file EXE uses its unpacked report-template directory."""
        bundle_dir = self.temp_path / "bundle"
        bundled_templates = bundle_dir / "data" / "report_templates"
        bundled_templates.mkdir(parents=True)
        (bundled_templates / "only_bundle.json").write_text(
            json.dumps(
                {
                    "id": "only_bundle",
                    "name": "Bundled",
                    "language": "en",
                    "category": "ctf",
                    "complexity": "simple",
                    "sections": [{"type": "header_metadata"}],
                }
            ),
            encoding="utf-8",
        )

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "_MEIPASS", str(bundle_dir), create=True),
        ):
            repo = TemplateRepository(user_templates_dir=self.user_dir)
            self.assertEqual(repo.builtin_dir, bundled_templates)
            self.assertEqual(
                [template.id for template in repo.get_builtin_templates()], ["only_bundle"]
            )

    def test_save_and_load_user_template(self):
        """A user can create and persist a custom template."""
        custom_template = ReportTemplate(
            id="my_custom_template",
            name="My Custom Template",
            language="en",
            category="pentest",
            complexity="simple",
            sections=[
                TemplateSection(type="header_metadata", title="Custom Audit"),
                TemplateSection(type="executive_summary"),
            ],
        )
        self.assertTrue(self.repo.save_user_template(custom_template))

        loaded = self.repo.get_template("my_custom_template")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "My Custom Template")
        self.assertFalse(loaded.is_builtin)
        self.assertEqual(len(loaded.sections), 2)

    def test_user_template_overrides_builtin(self):
        """A user template can override and then restore a built-in template."""
        override_template = ReportTemplate(
            id="pentest_standard_de",
            name="Pentest Standard-Bericht (Overridden)",
            language="de",
            category="pentest",
            complexity="complex",
            sections=[TemplateSection(type="header_metadata", title="Overridden Header")],
        )
        self.repo.save_user_template(override_template)

        active = self.repo.get_template("pentest_standard_de")
        self.assertEqual(active.name, "Pentest Standard-Bericht (Overridden)")
        self.assertFalse(active.is_builtin)

        self.repo.delete_user_template("pentest_standard_de")
        restored = self.repo.get_template("pentest_standard_de")
        self.assertEqual(restored.name, "Pentest Standard-Bericht (DE)")
        self.assertTrue(restored.is_builtin)

    def test_corrupted_template_is_skipped(self):
        """A malformed user template does not prevent the template list from loading."""
        corrupt_file = self.user_dir / "corrupt.json"
        corrupt_file.write_text("{invalid json", encoding="utf-8")

        ids = [template.id for template in self.repo.get_user_templates()]
        self.assertNotIn("corrupt", ids)


if __name__ == "__main__":
    unittest.main()

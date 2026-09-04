import unittest
import tempfile
import json
from pathlib import Path
from core.i18n import (
    I18nManager,
    set_locale,
    SUPPORTED_LOCALES,
    get_locales_dir,
    load_locale_file,
)


class TestI18n(unittest.TestCase):
    def setUp(self):
        self.i18n = I18nManager(default_locale="de")

    def tearDown(self):
        set_locale("en")

    def test_default_locale_and_supported(self):
        self.assertEqual(self.i18n.current_locale, "de")
        self.assertIn("de", SUPPORTED_LOCALES)
        self.assertIn("en", SUPPORTED_LOCALES)

    def test_json_files_exist_and_loadable(self):
        locales_dir = get_locales_dir()
        self.assertTrue(locales_dir.exists(), f"Locales dir should exist: {locales_dir}")

        de_dict = load_locale_file("de", locales_dir)
        en_dict = load_locale_file("en", locales_dir)

        self.assertGreater(len(de_dict), 50)
        self.assertGreater(len(en_dict), 50)

    def test_german_translations(self):
        self.assertEqual(self.i18n.t("header.mode_cheatsheet"), "Cheatsheet")
        self.assertEqual(self.i18n.t("varbar.add_btn"), "Neu")
        self.assertEqual(self.i18n.t("dialog.cancel"), "Abbrechen")
        self.assertEqual(self.i18n.t("dialog.save"), "Speichern")

    def test_locale_switch_to_english(self):
        self.i18n.set_locale("en")
        self.assertEqual(self.i18n.current_locale, "en")
        self.assertEqual(self.i18n.t("varbar.add_btn"), "New")
        self.assertEqual(self.i18n.t("dialog.cancel"), "Cancel")
        self.assertEqual(self.i18n.t("dialog.save"), "Save")

    def test_parameter_interpolation(self):
        self.i18n.set_locale("de")
        formatted_de = self.i18n.t("footer.entries_count", count=42)
        self.assertEqual(formatted_de, "42 Einträge")

        self.i18n.set_locale("en")
        formatted_en = self.i18n.t("footer.entries_count", count=42)
        self.assertEqual(formatted_en, "42 entries")

    def test_missing_key_fallback(self):
        self.assertEqual(self.i18n.t("non_existing_key_xyz"), "non_existing_key_xyz")
        self.assertEqual(
            self.i18n.t("non_existing_key_xyz", default="Fallback Value"), "Fallback Value"
        )

    def test_custom_locales_dir_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            td = Path(tmp_dir)
            (td / "de.json").write_text(json.dumps({"test.key": "Hallo Welt"}), encoding="utf-8")
            (td / "en.json").write_text(json.dumps({"test.key": "Hello World"}), encoding="utf-8")

            mgr = I18nManager(default_locale="en", locales_dir=td)
            self.assertEqual(mgr.t("test.key"), "Hello World")
            mgr.set_locale("de")
            self.assertEqual(mgr.t("test.key"), "Hallo Welt")

    def test_locale_changed_signal(self):
        changed_locales = []
        self.i18n.locale_changed.connect(lambda loc: changed_locales.append(loc))

        self.i18n.set_locale("en")
        self.assertEqual(changed_locales, ["en"])

        # Setting same locale shouldn't emit signal again
        self.i18n.set_locale("en")
        self.assertEqual(len(changed_locales), 1)

    def test_dialog_and_view_translations(self):
        """Verifies translations for newly localized dialogs, views, and empty states."""
        # 1. German
        self.i18n.set_locale("de")
        self.assertIn("Keine Befehle gefunden", self.i18n.t("cheatsheet.empty_state"))
        self.assertIn("Kein Session-Loot vorhanden", self.i18n.t("loot.empty_state"))
        self.assertIn("Keine Clipboard-Historie vorhanden", self.i18n.t("history.empty_state"))
        self.assertIn("Datenschutz-Hinweis", self.i18n.t("privacy.warning"))
        self.assertEqual(self.i18n.t("project_dialog.lbl_name"), "Projekt- / Box-Name:")
        self.assertEqual(self.i18n.t("snippet_dialog.lbl_title"), "Titel / Name des Befehls:")
        self.assertEqual(self.i18n.t("settings.save_apply"), "Speichern & Übernehmen")

        # 2. English
        self.i18n.set_locale("en")
        self.assertIn("No commands found", self.i18n.t("cheatsheet.empty_state"))
        self.assertIn("No session loot captured yet", self.i18n.t("loot.empty_state"))
        self.assertIn("No clipboard history recorded yet", self.i18n.t("history.empty_state"))
        self.assertIn("Privacy Notice", self.i18n.t("privacy.warning"))
        self.assertEqual(self.i18n.t("project_dialog.lbl_name"), "Project / Box Name:")
        self.assertEqual(self.i18n.t("snippet_dialog.lbl_title"), "Title / Command Name:")
        self.assertEqual(self.i18n.t("settings.save_apply"), "Save & Apply")


if __name__ == "__main__":
    unittest.main()

import unittest
from core.i18n import (
    I18nManager, t, get_i18n, set_locale, 
    get_locale, SUPPORTED_LOCALES
)

class TestI18n(unittest.TestCase):
    def setUp(self):
        self.i18n = I18nManager(default_locale="de")

    def tearDown(self):
        set_locale("de")

    def test_default_locale_and_supported(self):
        self.assertEqual(self.i18n.current_locale, "de")
        self.assertIn("de", SUPPORTED_LOCALES)
        self.assertIn("en", SUPPORTED_LOCALES)

    def test_german_translations(self):
        self.assertEqual(self.i18n.t("header.mode_cheatsheet"), "Cheatsheet")
        self.assertEqual(self.i18n.t("varbar.add_btn"), "+ Neu")
        self.assertEqual(self.i18n.t("dialog.cancel"), "Abbrechen")
        self.assertEqual(self.i18n.t("dialog.save"), "Speichern")

    def test_locale_switch_to_english(self):
        self.i18n.set_locale("en")
        self.assertEqual(self.i18n.current_locale, "en")
        self.assertEqual(self.i18n.t("varbar.add_btn"), "+ New")
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
        self.assertEqual(self.i18n.t("non_existing_key_xyz", default="Fallback Value"), "Fallback Value")

    def test_locale_changed_signal(self):
        changed_locales = []
        self.i18n.locale_changed.connect(lambda l: changed_locales.append(l))
        
        self.i18n.set_locale("en")
        self.assertEqual(changed_locales, ["en"])
        
        # Setting same locale shouldn't emit signal again
        self.i18n.set_locale("en")
        self.assertEqual(len(changed_locales), 1)

if __name__ == '__main__':
    unittest.main()
"""
AST-based linter and regression test for internationalization (i18n).

Ensures:
1. 100% key parity between data/i18n/de.json and data/i18n/en.json.
2. All t(...) calls across the codebase reference keys that exist in the translation dictionaries.
3. No raw hardcoded German/English string literals are passed as titles or messages in QMessageBox calls.
"""

import ast
import json
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
LOCALES_DIR = REPO_ROOT / "data" / "i18n"


class TestI18nLint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(LOCALES_DIR / "de.json", encoding="utf-8") as f:
            cls.de = json.load(f)
        with open(LOCALES_DIR / "en.json", encoding="utf-8") as f:
            cls.en = json.load(f)

    def test_translation_files_strict_parity(self):
        """Ensures de.json and en.json have exactly the same set of translation keys."""
        de_keys = set(self.de.keys())
        en_keys = set(self.en.keys())

        missing_in_en = de_keys - en_keys
        missing_in_de = en_keys - de_keys

        self.assertEqual(
            missing_in_en,
            set(),
            f"Keys present in de.json but missing in en.json: {sorted(missing_in_en)}",
        )
        self.assertEqual(
            missing_in_de,
            set(),
            f"Keys present in en.json but missing in de.json: {sorted(missing_in_de)}",
        )

    def test_all_code_t_calls_have_translations(self):
        """Verifies that every literal t('key', ...) call in code exists in both locale files."""
        used_keys = set()

        for py_file in REPO_ROOT.rglob("*.py"):
            rel_str = str(py_file.relative_to(REPO_ROOT)).replace("\\", "/")
            parts = py_file.relative_to(REPO_ROOT).parts
            if any(part.startswith(".") for part in parts) or any(
                part in ("tests", "build", "dist", "site-packages") for part in parts
            ):
                continue

            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except Exception as exc:
                self.fail(f"Could not parse {py_file}: {exc}")

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                    if func_name == "t" and node.args:
                        first_arg = node.args[0]
                        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                            used_keys.add((first_arg.value, rel_str, node.lineno))

        de_keys = set(self.de.keys())
        missing_keys = [
            f"{key} (in {file_path}:{lineno})"
            for key, file_path, lineno in used_keys
            if key not in de_keys
        ]

        self.assertEqual(
            missing_keys,
            [],
            "Found t() calls with keys missing in translation files:\n" + "\n".join(missing_keys),
        )

    def test_qmessagebox_calls_are_localized(self):
        """Inspects QMessageBox static calls in ui/ and main.py to guard against raw string literals."""
        violations = []

        files_to_check = list((REPO_ROOT / "ui").rglob("*.py"))
        main_py = REPO_ROOT / "main.py"
        if main_py.exists():
            files_to_check.append(main_py)

        methods = {"information", "warning", "critical", "question"}

        for py_file in files_to_check:
            rel_str = str(py_file.relative_to(REPO_ROOT)).replace("\\", "/")
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except Exception as exc:
                self.fail(f"Could not parse {py_file}: {exc}")

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if (
                        isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "QMessageBox"
                        and node.func.attr in methods
                    ):
                        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                            violations.append(
                                f"{rel_str}:{node.lineno} QMessageBox.{node.func.attr} has hardcoded title literal: {node.args[1].value!r}"
                            )
                        if len(node.args) >= 3 and isinstance(node.args[2], ast.Constant) and isinstance(node.args[2].value, str):
                            violations.append(
                                f"{rel_str}:{node.lineno} QMessageBox.{node.func.attr} has hardcoded message literal: {node.args[2].value!r}"
                            )

        self.assertEqual(
            violations,
            [],
            "Found unlocalized QMessageBox calls with hardcoded strings:\n" + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()

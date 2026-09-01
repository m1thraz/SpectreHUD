"""Focused dependency-boundary regression tests."""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTING_ROOT = PROJECT_ROOT / "core" / "reporting"
REPORT_EDITOR = PROJECT_ROOT / "ui" / "report_editor_tab.py"


def _ui_imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "ui" or alias.name.startswith("ui."):
                    violations.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "ui" or module.startswith("ui."):
                violations.append((node.lineno, module))
    return violations


def test_reporting_layer_does_not_import_ui():
    violations = []
    for path in sorted(REPORTING_ROOT.rglob("*.py")):
        for line, module in _ui_imports(path):
            violations.append(
                f"{path.relative_to(PROJECT_ROOT)}:{line} imports {module}"
            )

    assert violations == [], "\n".join(violations)


def test_report_editor_does_not_own_concrete_export_adapters():
    """The editor may coordinate UI, but concrete export work belongs elsewhere."""
    tree = ast.parse(REPORT_EDITOR.read_text(encoding="utf-8"), filename=str(REPORT_EDITOR))
    forbidden_names = {
        "atomic_write_text",
        "CherryTreeExporter",
        "ExternalExportError",
        "HtmlReportExporter",
        "ObsidianExporter",
    }
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imported_names = {
                alias.name.rsplit(".", 1)[-1]
                for alias in node.names
            }
            for name in sorted(imported_names & forbidden_names):
                violations.append(f"{REPORT_EDITOR.name}:{node.lineno} imports {name}")

    assert violations == [], "\n".join(violations)

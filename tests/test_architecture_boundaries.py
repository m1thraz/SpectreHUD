"""Focused dependency-boundary regression tests."""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTING_ROOT = PROJECT_ROOT / "core" / "reporting"
REPORT_EDITOR = PROJECT_ROOT / "ui" / "report_editor_tab.py"
APP_CONTROLLER = PROJECT_ROOT / "ui" / "app_controller.py"
PLATFORM_ROOT = PROJECT_ROOT / "core" / "platform"


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
            violations.append(f"{path.relative_to(PROJECT_ROOT)}:{line} imports {module}")

    assert violations == [], "\n".join(violations)


def test_platform_layer_does_not_import_ui():
    violations = []
    for path in sorted(PLATFORM_ROOT.rglob("*.py")):
        for line, module in _ui_imports(path):
            violations.append(
                f"{path.relative_to(PROJECT_ROOT)}:{line} imports {module}"
            )

    assert violations == [], "\n".join(violations)


def test_local_path_opening_does_not_use_platform_shell_branches():
    """Local desktop opening belongs to core.platform.opener, not OS shell commands."""
    forbidden = ("os.startfile", '"xdg-open"', "'xdg-open'")
    violations = []
    for source_root in (PROJECT_ROOT / "core", PROJECT_ROOT / "ui"):
        for path in source_root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(token in source for token in forbidden):
                violations.append(str(path.relative_to(PROJECT_ROOT)))

    assert violations == [], (
        "Local-path shell opening escaped the platform boundary: "
        + ", ".join(violations)
    )


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
            imported_names = {alias.name.rsplit(".", 1)[-1] for alias in node.names}
            for name in sorted(imported_names & forbidden_names):
                violations.append(f"{REPORT_EDITOR.name}:{node.lineno} imports {name}")

    assert violations == [], "\n".join(violations)


def test_app_controller_receives_resolved_application_services():
    """Service selection belongs to MainWindow, not a second composition root."""
    tree = ast.parse(
        APP_CONTROLLER.read_text(encoding="utf-8"),
        filename=str(APP_CONTROLLER),
    )
    app_controller = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AppController"
    )
    constructor = next(
        node
        for node in app_controller.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    parameter_names = {argument.arg for argument in constructor.args.args}
    forbidden_calls = {
        "ClipboardWatcher",
        "ConfigManager",
        "EventBus",
        "LootManager",
        "ProjectManager",
        "ScreenshotManager",
        "SnippetManager",
    }
    constructed = {
        node.func.id
        for node in ast.walk(constructor)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "container" not in parameter_names
    assert constructed.isdisjoint(forbidden_calls)

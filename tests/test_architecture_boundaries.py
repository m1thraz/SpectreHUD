"""Focused dependency-boundary regression tests."""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTING_ROOT = PROJECT_ROOT / "core" / "reporting"
REPORT_EDITOR = PROJECT_ROOT / "ui" / "report_editor_tab.py"
APP_CONTROLLER = PROJECT_ROOT / "ui" / "app_controller.py"
PLATFORM_ROOT = PROJECT_ROOT / "core" / "platform"
CLIPBOARD_HISTORY = PROJECT_ROOT / "core" / "clipboard_history.py"
LEGACY_CLIPBOARD_WATCHER = PROJECT_ROOT / "core" / "clipboard_watcher.py"


CORE_ROOT = PROJECT_ROOT / "core"
TESTS_ROOT = PROJECT_ROOT / "tests"
QAPPLICATION_OWNERS = {
    TESTS_ROOT / "conftest.py",
    TESTS_ROOT / "qt_subprocess.py",
}


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


def test_core_layer_does_not_import_ui():
    """Architectural invariant: The entire core layer must never import from ui."""
    violations = []
    for path in sorted(CORE_ROOT.rglob("*.py")):
        for line, module in _ui_imports(path):
            violations.append(f"{path.relative_to(PROJECT_ROOT)}:{line} imports {module}")

    assert violations == [], (
        "Core layer violated architecture boundaries by importing from ui:\n"
        + "\n".join(violations)
    )


def test_qapplication_is_only_constructed_by_central_test_infrastructure():
    """Normal test modules must consume the shared lifecycle, never create a competing one."""
    violations = []
    for path in sorted(TESTS_ROOT.rglob("*.py")):
        if path in QAPPLICATION_OWNERS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "qapp":
                violations.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} defines qapp")
                continue
            if not isinstance(node, ast.Call):
                continue
            called_name = None
            if isinstance(node.func, ast.Name):
                called_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                called_name = node.func.attr
            if called_name == "QApplication":
                violations.append(
                    f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} constructs QApplication"
                )

    assert violations == [], "Direct QApplication construction outside central fixtures:\n" + "\n".join(
        violations
    )


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


def test_platform_package_does_not_eagerly_import_qt():
    """Importing core.platform or core.platform.paths must not eagerly load PyQt6 into memory."""
    import subprocess
    import sys

    code = (
        "import sys\n"
        "import core.platform\n"
        "import core.platform.paths\n"
        "import core.platform.network\n"
        "import core.platform.capabilities\n"
        "qt_modules = [m for m in sys.modules if m.startswith('PyQt6')]\n"
        "assert not qt_modules, f'PyQt6 was eagerly imported by core.platform: {qt_modules}'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, f"Subprocess failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"


def test_clipboard_history_is_headless_and_legacy_watcher_is_removed():
    """Clipboard state belongs to core while Qt capture belongs to the UI adapter."""
    assert CLIPBOARD_HISTORY.exists()
    assert not LEGACY_CLIPBOARD_WATCHER.exists()
    tree = ast.parse(
        CLIPBOARD_HISTORY.read_text(encoding="utf-8"),
        filename=str(CLIPBOARD_HISTORY),
    )
    qt_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            qt_imports.extend(
                alias.name for alias in node.names if alias.name.startswith("PyQt6")
            )
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("PyQt6"):
            qt_imports.append(node.module or "")
    assert qt_imports == []


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


def test_external_modules_do_not_import_core_subpackage_internals():
    """External code (UI and other core modules) must consume core packages via their public package API,
    never directly importing internal submodules."""
    public_core_packages = {
        "loot",
        "snippets",
        "screenshots",
        "platform",
        "project",
        "reporting",
    }
    violations = []

    for search_root in (PROJECT_ROOT / "ui", PROJECT_ROOT / "core"):
        for path in search_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                target_module = None
                if isinstance(node, ast.ImportFrom) and node.module:
                    target_module = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        for pkg in public_core_packages:
                            if alias.name.startswith(f"core.{pkg}."):
                                target_module = alias.name
                                break
                if target_module:
                    for pkg in public_core_packages:
                        if target_module.startswith(f"core.{pkg}."):
                            if path.is_relative_to(PROJECT_ROOT / "core" / pkg):
                                continue
                            violations.append(
                                f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} imports {target_module}"
                            )

    assert violations == [], (
        "Found internal core subpackage imports from external modules:\n"
        + "\n".join(violations)
    )

def test_core_packages_have_no_dependency_cycles():
    """Core domain packages must form a clean Directed Acyclic Graph (DAG) with zero cycles."""
    from collections import defaultdict

    packages = ["loot", "snippets", "screenshots", "platform", "project", "reporting", "exporters"]
    package_deps = defaultdict(set)

    for pkg in packages:
        pkg_dir = PROJECT_ROOT / "core" / pkg
        if not pkg_dir.exists():
            continue
        for py_file in pkg_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                mod = None
                if isinstance(node, ast.ImportFrom) and node.module:
                    mod = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        mod = alias.name
                if mod and mod.startswith("core."):
                    parts = mod.split(".")
                    if len(parts) >= 2:
                        target_pkg = parts[1]
                        if target_pkg in packages and target_pkg != pkg:
                            package_deps[pkg].add(target_pkg)

    cycles = []
    visited = set()
    stack = []

    def dfs(node):
        visited.add(node)
        stack.append(node)
        for neighbor in sorted(package_deps.get(node, [])):
            if neighbor in stack:
                idx = stack.index(neighbor)
                cycles.append(" -> ".join(stack[idx:] + [neighbor]))
            elif neighbor not in visited:
                dfs(neighbor)
        stack.pop()

    for p in sorted(packages):
        if p not in visited:
            dfs(p)

    assert cycles == [], f"Detected dependency cycle(s) between core packages: {cycles}"


def test_ui_does_not_access_private_core_attributes():
    """UI layer must not pierce encapsulation by accessing private attributes on core managers/services."""
    core_manager_names = {
        "project_manager",
        "report_file_manager",
        "screenshot_manager",
        "snippet_manager",
        "loot_manager",
        "loot_mgr",
    }
    violations = []

    for py_file in (PROJECT_ROOT / "ui").rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr.startswith("_") and not node.attr.startswith("__"):
                val_name = None
                if isinstance(node.value, ast.Name):
                    val_name = node.value.id
                elif (
                    isinstance(node.value, ast.Attribute)
                    and isinstance(node.value.value, ast.Name)
                    and node.value.value.id == "self"
                ):
                    val_name = node.value.attr

                if val_name and val_name in core_manager_names:
                    violations.append(
                        f"{py_file.relative_to(PROJECT_ROOT)}:{node.lineno} accesses {val_name}.{node.attr}"
                    )

    assert violations == [], (
        "UI code accesses private attributes on core domain services:\n"
        + "\n".join(violations)
    )


KNOWN_PURE_CORE_TEST_FILES = {
    "test_atomic_write.py",
    "test_box_archiver.py",
    "test_cherrytree_exporter.py",
    "test_cli.py",
    "test_clipboard_history.py",
    "test_core.py",
    "test_display_geometry.py",
    "test_event_bus.py",
    "test_export_result.py",
    "test_fuzzy_matcher.py",
    "test_hotkeys.py",
    "test_html_report_exporter.py",
    "test_i18n.py",
    "test_linux_filesystem_adversarial.py",
    "test_logger.py",
    "test_loot_entries.py",
    "test_loot_filter.py",
    "test_loot_migrator.py",
    "test_loot_persistence.py",
    "test_loot_report_sync.py",
    "test_navigation_state.py",
    "test_obsidian_exporter.py",
    "test_packaging_metadata.py",
    "test_pentest_mode.py",
    "test_phase_context.py",
    "test_phases.py",
    "test_platform_capabilities.py",
    "test_platform_network.py",
    "test_platform_opener.py",
    "test_platform_paths.py",
    "test_project_manager.py",
    "test_project_session_service.py",
    "test_project_transactions.py",
    "test_quick_note_manager.py",
    "test_report_builder.py",
    "test_report_draft_manager.py",
    "test_report_navigation.py",
    "test_report_note_formatter.py",
    "test_report_outline.py",
    "test_report_sections.py",
    "test_snippet_filter.py",
    "test_snippet_importer.py",
    "test_storage.py",
    "test_template_engine.py",
    "test_template_params.py",
    "test_template_repository.py",
    "test_update_checker.py",
    "test_validators.py",
    "test_verify_wheel.py",
}


def test_pure_core_test_files_do_not_import_ui_or_pyqt():
    """Pure core unit test files must never import ui or PyQt6, ensuring headless execution."""
    violations = []
    for filename in sorted(KNOWN_PURE_CORE_TEST_FILES):
        path = TESTS_ROOT / filename
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported_mod = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(("ui", "PyQt6")):
                        imported_mod = alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(("ui", "PyQt6")):
                    imported_mod = node.module
            if imported_mod:
                violations.append(
                    f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} imports {imported_mod}"
                )

    assert violations == [], (
        "Pure core test files violated headless boundary by importing ui or PyQt6:\n"
        + "\n".join(violations)
    )



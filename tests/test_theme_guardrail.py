"""
Theme Consistency Architecture Guardrail Test.

Enforces that NO hardcoded hex color literals (#[0-9a-fA-F]{6}) exist in UI components
or reporting runtime presentation logic. All dynamic UI colors must be retrieved
from the active theme palette via get_theme_color("TOKEN") or get_severity_color("sev").

Allowed exceptions (exactly 4):
1. ui/report/report_light_palette.py (complete file: central light/print export palette)
2. ui/styles/dialogs.py (only dedicated light rules in [reportLight="true"])
3. core/reporting/styles.py (complete file: CSS for HTML/PDF export)
4. core/theme_palette.py (complete file: fallback CYBER_DARK_PALETTE)
"""

import re
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

HEX_REGEX = re.compile(r"#[0-9a-fA-F]{6}\b")

# Whitelisted files (relative to PROJECT_ROOT with forward slashes)
FULLY_ALLOWED_FILES = {
    "ui/report/report_light_palette.py",
    "core/reporting/styles.py",
    "core/theme_palette.py",
}


def is_dialogs_light_block(line_num: int, lines: List[str]) -> bool:
    """Check if a line in ui/styles/dialogs.py is inside the [reportLight="true"] block."""
    in_light_block = False
    brace_depth = 0
    for idx, line in enumerate(lines, 1):
        if 'reportLight="true"' in line:
            in_light_block = True
            brace_depth += line.count("{") - line.count("}")
        elif in_light_block:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0:
                in_light_block = False
        if idx == line_num:
            return in_light_block
    return False


def scan_file_for_hex_violations(file_path: Path, root: Path = PROJECT_ROOT) -> List[Tuple[int, str, str]]:
    """Return a list of (line_number, match, line_content) for any forbidden hex literals."""
    rel_path = file_path.relative_to(root).as_posix()
    if rel_path in FULLY_ALLOWED_FILES:
        return []

    violations = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = file_path.read_text(encoding="latin-1")

    lines = content.splitlines()

    for line_num, line in enumerate(lines, 1):
        matches = HEX_REGEX.findall(line)
        if not matches:
            continue

        # Check special exception for ui/styles/dialogs.py in [reportLight="true"]
        if rel_path == "ui/styles/dialogs.py" and is_dialogs_light_block(line_num, lines):
            continue

        for m in matches:
            violations.append((line_num, m, line.strip()))

    return violations


def scan_target_directories(root: Path = PROJECT_ROOT) -> List[str]:
    """Scan all .py files in ui/ and core/reporting/ (and core/theme_palette.py)."""
    target_dirs = [root / "ui", root / "core" / "reporting"]
    target_files: List[Path] = []
    for d in target_dirs:
        if d.is_dir():
            target_files.extend(d.rglob("*.py"))

    # Also include core/theme_palette.py in guardrail
    theme_pal = root / "core" / "theme_palette.py"
    if theme_pal.is_file() and theme_pal not in target_files:
        target_files.append(theme_pal)

    all_violations: List[str] = []
    for file_path in sorted(target_files):
        v = scan_file_for_hex_violations(file_path, root=root)
        rel_path = file_path.relative_to(root).as_posix()
        for line_num, match, line_content in v:
            all_violations.append(f"{rel_path}:{line_num}: found hex literal '{match}' in: {line_content}")

    return all_violations


def test_theme_guardrail_no_hex_literals_in_ui_and_reporting():
    """Verify that no unlisted hex literals exist across ui/ and core/reporting/."""
    violations = scan_target_directories()
    assert not violations, (
        f"Found {len(violations)} forbidden hex color literal(s) in UI/reporting codebase:\n"
        + "\n".join(violations)
        + "\n\nAll UI colors must be retrieved dynamically via get_theme_color() or get_severity_color()."
    )


def test_theme_guardrail_negative_test_detects_violations(tmp_path):
    """Negative test verifying that unlisted hex literals in dummy files are caught."""
    dummy_ui_file = tmp_path / "ui" / "test_widget.py"
    dummy_ui_file.parent.mkdir(parents=True, exist_ok=True)
    dummy_ui_file.write_text(
        'button.setStyleSheet("background-color: #ff0055;")\n',
        encoding="utf-8",
    )

    violations = scan_file_for_hex_violations(dummy_ui_file, root=tmp_path)
    assert len(violations) == 1
    assert violations[0][0] == 1
    assert violations[0][1] == "#ff0055"

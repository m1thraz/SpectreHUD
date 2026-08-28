#!/usr/bin/env python3
"""
SpectreHUD Master Test Runner

Runs the same pytest collection as local development and CI, with shared
fixtures and test isolation enabled.
"""

import sys
import os
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows consoles to prevent UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set test environment flags
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def run_all_tests() -> int:
    tests_dir = PROJECT_ROOT / "tests"
    if not tests_dir.exists():
        print(f"Error: Tests directory not found at {tests_dir}")
        return 1

    if not list(tests_dir.glob("test_*.py")):
        print("No test files found in tests/ directory.")
        return 1

    try:
        import pytest
    except ImportError:
        print("pytest is required to run the SpectreHUD test suite.")
        return 1

    print("[*] SpectreHUD Test Runner delegates to pytest (same as CI).")
    return pytest.main([str(tests_dir)])


if __name__ == "__main__":
    sys.exit(run_all_tests())

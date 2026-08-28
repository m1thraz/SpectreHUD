#!/usr/bin/env python3
"""
SpectreHUD Master Test Runner

Discovers and executes all unit and regression test suites across the codebase.
Provides clear per-suite progress reporting, failure summaries, and exits with code 0 on success.
"""

import sys
import os
import unittest
import time
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

    test_files = sorted(tests_dir.glob("test_*.py"))
    if not test_files:
        print("No test files found in tests/ directory.")
        return 1

    print("=" * 65)
    print(f"[*] SpectreHUD Test Runner - Found {len(test_files)} test suites")
    print(f"[*] Python: {sys.version.split()[0]} | Platform: {sys.platform}")
    print("=" * 65)

    passed_count = 0
    failed_suites = []
    total_tests_run = 0
    start_time = time.time()

    for idx, test_file in enumerate(test_files, start=1):
        module_name = f"tests.{test_file.stem}"
        print(f"[{idx:02d}/{len(test_files):02d}] Running {test_file.stem}...", end=" ", flush=True)
        
        suite_start = time.time()
        loader = unittest.TestLoader()
        try:
            suite = loader.loadTestsFromName(module_name)
        except Exception as e:
            print(f"FAILED (Import Error: {e})")
            failed_suites.append((test_file.stem, f"Import Error: {e}"))
            continue

        with open(os.devnull, "w", encoding="utf-8", errors="replace") as null_stream:
            runner = unittest.TextTestRunner(verbosity=0, stream=null_stream)
            result = runner.run(suite)
        elapsed = time.time() - suite_start
        total_tests_run += result.testsRun

        if result.wasSuccessful():
            print(f"PASSED ({result.testsRun} tests in {elapsed:.2f}s)")
            passed_count += 1
        else:
            errors_and_failures = len(result.failures) + len(result.errors)
            print(f"FAILED ({errors_and_failures} failures/errors in {result.testsRun} tests)")
            failed_suites.append((test_file.stem, f"{errors_and_failures} failures in {result.testsRun} tests"))

    total_elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print(f"[*] Test Summary: {passed_count}/{len(test_files)} suites passed ({total_tests_run} total tests in {total_elapsed:.2f}s)")

    if failed_suites:
        print("\n[!] Failed Suites:")
        for name, err in failed_suites:
            print(f"    - {name}: {err}")
        print("=" * 65)
        return 1
    else:
        print("[+] ALL TEST SUITES PASSED SUCCESSFULLY!")
        print("=" * 65)
        return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())

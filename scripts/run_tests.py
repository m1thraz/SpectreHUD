#!/usr/bin/env python3
"""Cross-platform, agent-friendly test-tier runner for SpectreHUD."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Mapping, Sequence
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"
LOG_ROOT = Path(tempfile.gettempdir()) / "spectrehud-tests"
FAILURE_TAIL_LINES = 50


@dataclass(frozen=True)
class TierConfig:
    marker: str | None
    parallel: bool
    fail_fast: bool
    traceback: str


TIER_CONFIGS = {
    "fast": TierConfig(
        marker="not integration and not release",
        parallel=True,
        fail_fast=True,
        traceback="line",
    ),
    "full": TierConfig(
        marker="not release",
        parallel=True,
        fail_fast=False,
        traceback="short",
    ),
    "release": TierConfig(
        marker="release",
        parallel=False,
        fail_fast=False,
        traceback="short",
    ),
    "all": TierConfig(
        marker=None,
        parallel=False,
        fail_fast=False,
        traceback="short",
    ),
    "targeted": TierConfig(
        marker=None,
        parallel=False,
        fail_fast=False,
        traceback="short",
    ),
}


@dataclass(frozen=True)
class TestStats:
    selected: int
    subtests: int
    failures: int
    errors: int
    skipped: int
    xfailed: int
    duration: float
    failed_tests: tuple[str, ...]

    @property
    def passed(self) -> int:
        return self.selected - self.failures - self.errors - self.skipped

    @property
    def ordinary_skipped(self) -> int:
        return max(0, self.skipped - self.xfailed)


def configure_console() -> None:
    """Keep diagnostics readable on Windows consoles and redirected streams."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_test_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return an isolated subprocess environment without mutating the caller."""
    environment = dict(os.environ if source is None else source)
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    environment.setdefault("SPECTREHUD_NO_GUI_CRASH_POPUP", "1")
    environment.setdefault("PYTHONUTF8", "1")
    environment.setdefault("PYTHONIOENCODING", "utf-8")
    return environment


def build_pytest_command(
    tier: str,
    junit_path: Path,
    *,
    targets: Sequence[str] = (),
    collect_only: bool = False,
    no_parallel: bool = False,
) -> list[str]:
    """Build the canonical pytest invocation for one execution tier."""
    config = TIER_CONFIGS[tier]
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-o",
        "addopts=",
        f"--tb={config.traceback}",
        "-r",
        "fEsxX",
    ]

    if not collect_only:
        command.extend(("-q", f"--junitxml={junit_path}"))
    if config.marker:
        command.extend(("-m", config.marker))
    if config.parallel and not no_parallel and not collect_only:
        command.extend(("-n", "auto", "--dist=loadscope"))
    if config.fail_fast:
        command.append("-x")
    if collect_only:
        command.append("--collect-only")

    command.extend(targets if tier == "targeted" else (str(TESTS_DIR),))
    return command


def create_artifact_paths(tier: str) -> tuple[Path, Path]:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
    return LOG_ROOT / f"{tier}-{run_id}.log", LOG_ROOT / f"{tier}-{run_id}.xml"


def run_process(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    log_path: Path,
    verbose: bool,
) -> int:
    """Run pytest while retaining a complete UTF-8 log."""
    with log_path.open("w", encoding="utf-8", errors="replace", newline="") as log_file:
        if not verbose:
            try:
                completed = subprocess.run(
                    command,
                    cwd=PROJECT_ROOT,
                    env=dict(environment),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            except KeyboardInterrupt:
                return 130
            return completed.returncode

        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            env=dict(environment),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                log_file.write(line)
                log_file.flush()
                print(line, end="")
            return process.wait()
        except KeyboardInterrupt:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return 130


def _testcase_id(testcase: ET.Element) -> str:
    file_name = (testcase.get("file") or "").replace("\\", "/")
    class_name = (testcase.get("classname") or "").rsplit(".", 1)[-1]
    test_name = testcase.get("name") or "unknown"
    parts = [file_name] if file_name else []
    if class_name and (not file_name or class_name != Path(file_name).stem):
        parts.append(class_name)
    parts.append(test_name)
    return "::".join(parts)


def parse_junit_report(path: Path) -> TestStats:
    """Read stable counts and failing test IDs from pytest's JUnit report."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    reported_tests = sum(int(suite.get("tests", "0")) for suite in suites)
    failures = sum(int(suite.get("failures", "0")) for suite in suites)
    errors = sum(int(suite.get("errors", "0")) for suite in suites)
    skipped = sum(int(suite.get("skipped", "0")) for suite in suites)
    duration = sum(float(suite.get("time", "0")) for suite in suites)

    testcases = root.findall(".//testcase")
    selected = len(testcases)
    subtests = max(0, reported_tests - selected)
    xfailed = 0
    failed_tests = []
    for testcase in testcases:
        skipped_node = testcase.find("skipped")
        if skipped_node is not None:
            reason = " ".join(
                filter(None, (skipped_node.get("type"), skipped_node.get("message")))
            ).lower()
            if "xfail" in reason:
                xfailed += 1
        if testcase.find("failure") is not None or testcase.find("error") is not None:
            failed_tests.append(_testcase_id(testcase))

    return TestStats(
        selected=selected,
        subtests=subtests,
        failures=failures,
        errors=errors,
        skipped=skipped,
        xfailed=xfailed,
        duration=duration,
        failed_tests=tuple(failed_tests),
    )


def extract_failed_tests(log_text: str) -> tuple[str, ...]:
    """Use pytest's terminal summary when it contains more precise node IDs."""
    return tuple(dict.fromkeys(re.findall(r"^FAILED\s+([^\s]+)", log_text, re.MULTILINE)))


def extract_collection_summary(log_text: str) -> str:
    for line in reversed(log_text.splitlines()):
        if re.search(r"\b(?:test|tests) collected\b", line):
            return line.strip()
    return "collection completed"


def failure_kind(exit_code: int, log_text: str, report_exists: bool) -> str:
    if exit_code in (2, 130):
        return "interrupted"
    if exit_code == 3:
        return "pytest-internal"
    if exit_code == 4:
        return "pytest-usage"
    if exit_code == 5:
        return "no-tests-collected"
    if "node down: Not properly terminated" in log_text:
        return "worker-crash"
    if "ERROR collecting" in log_text or "errors during collection" in log_text:
        return "collection"
    if exit_code == 1 and report_exists:
        return "test-failure"
    return "pytest-process"


def print_failure_tail(log_text: str) -> None:
    lines = log_text.splitlines()
    if not lines:
        return
    print("\n--- actionable output ---")
    print("\n".join(lines[-FAILURE_TAIL_LINES:]))


def remove_success_artifacts(log_path: Path, junit_path: Path) -> None:
    for path in (log_path, junit_path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def execute_tier(
    tier: str,
    *,
    targets: Sequence[str] = (),
    collect_only: bool = False,
    no_parallel: bool = False,
    verbose: bool = False,
    keep_log: bool = False,
) -> int:
    log_path, junit_path = create_artifact_paths(tier)
    command = build_pytest_command(
        tier,
        junit_path,
        targets=targets,
        collect_only=collect_only,
        no_parallel=no_parallel,
    )
    started = time.monotonic()
    try:
        exit_code = run_process(
            command,
            environment=build_test_environment(),
            log_path=log_path,
            verbose=verbose,
        )
    except OSError as error:
        elapsed = time.monotonic() - started
        print(f"ERROR tier={tier} kind=launch exit=3 duration={elapsed:.2f}s")
        print(f"reason: {error}")
        print(f"full log: {log_path}")
        return 3
    elapsed = time.monotonic() - started
    log_text = log_path.read_text(encoding="utf-8", errors="replace")

    if collect_only and exit_code == 0:
        print(
            f"PASS tier={tier} collection={extract_collection_summary(log_text)!r} "
            f"duration={elapsed:.2f}s"
        )
        if keep_log:
            print(f"full log: {log_path}")
        else:
            remove_success_artifacts(log_path, junit_path)
        return 0

    stats = None
    if junit_path.exists():
        try:
            stats = parse_junit_report(junit_path)
        except (ET.ParseError, OSError, TypeError, ValueError):
            stats = None

    if exit_code == 0 and stats is not None:
        print(
            f"PASS tier={tier} selected={stats.selected} passed={stats.passed} "
            f"skipped={stats.ordinary_skipped} xfailed={stats.xfailed} "
            f"subtests={stats.subtests} "
            f"duration={elapsed:.2f}s"
        )
        if keep_log:
            print(f"full log: {log_path}")
        else:
            remove_success_artifacts(log_path, junit_path)
        return 0

    if exit_code == 0:
        exit_code = 3
        kind = "missing-report"
    else:
        kind = failure_kind(exit_code, log_text, junit_path.exists())

    label = "FAIL" if kind == "test-failure" else "ERROR"
    print(f"{label} tier={tier} kind={kind} exit={exit_code} duration={elapsed:.2f}s")
    failed_tests = extract_failed_tests(log_text) or (() if stats is None else stats.failed_tests)
    if failed_tests:
        print("failed:")
        for test_id in failed_tests:
            print(f"  {test_id}")
    print_failure_tail(log_text)
    print(f"\nfull log: {log_path}")
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tier",
        nargs="?",
        choices=tuple(TIER_CONFIGS),
        default="all",
        help="test tier to execute (default: all)",
    )
    parser.add_argument("targets", nargs="*", help="test paths or node IDs for targeted mode")
    parser.add_argument("--verbose", action="store_true", help="stream pytest output")
    parser.add_argument("--keep-log", action="store_true", help="retain logs after successful runs")
    parser.add_argument("--collect-only", action="store_true", help="collect without running tests")
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="disable xdist for fast and full tiers",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.tier == "targeted" and not args.targets:
        parser.error("targeted mode requires at least one test path or node ID")
    if args.tier != "targeted" and args.targets:
        parser.error("test paths are accepted only in targeted mode")
    if not TESTS_DIR.is_dir():
        parser.error(f"tests directory not found: {TESTS_DIR}")
    return execute_tier(
        args.tier,
        targets=args.targets,
        collect_only=args.collect_only,
        no_parallel=args.no_parallel,
        verbose=args.verbose,
        keep_log=args.keep_log,
    )


def run_all_tests() -> int:
    """Backward-compatible entry point for callers of the former master runner."""
    return main(("all",))


if __name__ == "__main__":
    raise SystemExit(main())

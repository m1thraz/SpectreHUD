#!/usr/bin/env python3
"""Cross-platform, agent-friendly test-tier runner for SpectreHUD."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping, Sequence
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"
LOG_ROOT = Path(tempfile.gettempdir()) / "spectrehud-tests"
FAILURE_TAIL_LINES = 50
DEFAULT_MAX_RETAINED_RUNS = 20
# Keep the simulated Windows branch testable on POSIX, where subprocess does
# not expose Windows creation flags.
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
WORKER_CRASH_PATTERNS = (
    re.compile(r"node down:\s*not properly terminated", re.IGNORECASE),
    re.compile(r"worker .+ crashed while running", re.IGNORECASE),
    re.compile(r"maximum crashed workers reached", re.IGNORECASE),
    re.compile(r"worker .+ terminated unexpectedly", re.IGNORECASE),
)


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
    "last-failed": TierConfig(
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
    command.extend(targets if tier in {"targeted", "last-failed"} else (str(TESTS_DIR),))
    return command


def create_artifact_paths(tier: str) -> tuple[Path, Path]:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = f"{datetime.now():%Y%m%d-%H%M%S-%f}-{os.getpid()}"
    return LOG_ROOT / f"{tier}-{run_id}.log", LOG_ROOT / f"{tier}-{run_id}.xml"


def load_last_failed() -> tuple[str, ...]:
    path = LOG_ROOT / "last-failed.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return ()
    tests = payload.get("tests") if isinstance(payload, dict) else None
    if not isinstance(tests, list) or not all(isinstance(item, str) for item in tests):
        return ()
    return tuple(dict.fromkeys(tests))


def save_last_failed(test_ids: Sequence[str]) -> None:
    if not test_ids:
        return
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    path = LOG_ROOT / "last-failed.json"
    temporary_path = LOG_ROOT / f"last-failed-{os.getpid()}.tmp"
    temporary_path.write_text(
        json.dumps({"schema_version": 1, "tests": list(dict.fromkeys(test_ids))}),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def clear_last_failed() -> None:
    try:
        (LOG_ROOT / "last-failed.json").unlink()
    except FileNotFoundError:
        pass


def prune_artifacts(max_runs: int = DEFAULT_MAX_RETAINED_RUNS) -> None:
    """Keep only the newest complete runner artifact groups."""
    if not LOG_ROOT.is_dir():
        return
    groups: dict[str, list[Path]] = {}
    for path in LOG_ROOT.iterdir():
        if path.is_file() and path.suffix in {".log", ".xml"}:
            groups.setdefault(path.stem, []).append(path)
    newest_first = sorted(
        groups.values(),
        key=lambda paths: max(path.stat().st_mtime_ns for path in paths),
        reverse=True,
    )
    for paths in newest_first[max_runs:]:
        for path in paths:
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def _process_group_options(platform_name: str | None = None) -> dict[str, Any]:
    platform_name = os.name if platform_name is None else platform_name
    if platform_name == "nt":
        return {"creationflags": CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def forward_signal(
    process: subprocess.Popen[Any], signum: int, *, platform_name: str | None = None
) -> None:
    """Forward an interrupt to pytest and its xdist worker process group."""
    if process.poll() is not None:
        return
    platform_name = os.name if platform_name is None else platform_name
    try:
        if platform_name == "nt":
            if signum == signal.SIGINT and hasattr(signal, "CTRL_BREAK_EVENT"):
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
        else:
            os.killpg(process.pid, signum)
    except (OSError, ProcessLookupError):
        process.terminate()


def stop_process(process: subprocess.Popen[Any], signum: int = signal.SIGINT) -> None:
    forward_signal(process, signum)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_process(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    log_path: Path,
    verbose: bool,
) -> int:
    """Run pytest while retaining a complete UTF-8 log."""
    with log_path.open("w", encoding="utf-8", errors="replace", newline="") as log_file:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            env=dict(environment),
            stdout=subprocess.PIPE if verbose else log_file,
            stderr=subprocess.STDOUT,
            text=verbose,
            encoding="utf-8" if verbose else None,
            errors="replace" if verbose else None,
            **_process_group_options(),
        )
        received_signal: int | None = None
        previous_handlers: dict[int, Any] = {}

        def handle_signal(signum: int, _frame: Any) -> None:
            nonlocal received_signal
            if received_signal is None:
                received_signal = signum
                forward_signal(process, signum)
            else:
                process.kill()

        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                previous_handlers[signum] = signal.signal(signum, handle_signal)
            except (ValueError, OSError):
                pass
        try:
            if verbose:
                assert process.stdout is not None
                for line in process.stdout:
                    log_file.write(line)
                    log_file.flush()
                    print(line, end="")
            exit_code = process.wait()
        except KeyboardInterrupt:
            stop_process(process)
            return 130
        finally:
            for signum, previous_handler in previous_handlers.items():
                signal.signal(signum, previous_handler)
        return 128 + received_signal if received_signal is not None else exit_code


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
    if exit_code in (2, 130, 143):
        return "interrupted"
    if any(pattern.search(log_text) for pattern in WORKER_CRASH_PATTERNS):
        return "worker-crash"
    if exit_code == 3:
        return "pytest-internal"
    if exit_code == 4:
        return "pytest-usage"
    if exit_code == 5:
        return "no-tests-collected"
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


def _stats_payload(stats: TestStats | None) -> dict[str, int | float] | None:
    if stats is None:
        return None
    return {
        "selected": stats.selected,
        "passed": stats.passed,
        "failures": stats.failures,
        "errors": stats.errors,
        "skipped": stats.ordinary_skipped,
        "xfailed": stats.xfailed,
        "subtests": stats.subtests,
        "junit_duration_seconds": round(stats.duration, 3),
    }


def emit_json_result(
    *,
    status: str,
    tier: str,
    kind: str,
    exit_code: int,
    duration: float,
    stats: TestStats | None = None,
    failed_tests: Sequence[str] = (),
    log_path: Path | None = None,
    junit_path: Path | None = None,
    detail: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "tier": tier,
        "kind": kind,
        "exit_code": exit_code,
        "duration_seconds": round(duration, 3),
        "stats": _stats_payload(stats),
        "failed_tests": list(failed_tests),
        "artifacts": {
            "log": str(log_path) if log_path is not None else None,
            "junit": str(junit_path) if junit_path is not None else None,
        },
    }
    if detail is not None:
        payload["detail"] = detail
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def execute_tier(
    tier: str,
    *,
    targets: Sequence[str] = (),
    collect_only: bool = False,
    no_parallel: bool = False,
    verbose: bool = False,
    keep_log: bool = False,
    json_output: bool = False,
    max_retained_runs: int = DEFAULT_MAX_RETAINED_RUNS,
) -> int:
    if tier == "last-failed" and not targets:
        targets = load_last_failed()
        if not targets:
            if json_output:
                emit_json_result(
                    status="passed",
                    tier=tier,
                    kind="no-last-failures",
                    exit_code=0,
                    duration=0.0,
                )
            else:
                print("PASS tier=last-failed selected=0 kind=no-last-failures duration=0.00s")
            return 0
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
        if json_output:
            emit_json_result(
                status="error",
                tier=tier,
                kind="launch",
                exit_code=3,
                duration=elapsed,
                log_path=log_path,
                detail=str(error),
            )
        else:
            print(f"ERROR tier={tier} kind=launch exit=3 duration={elapsed:.2f}s")
            print(f"reason: {error}")
            print(f"full log: {log_path}")
        prune_artifacts(max_retained_runs)
        return 3
    elapsed = time.monotonic() - started
    log_text = log_path.read_text(encoding="utf-8", errors="replace")

    if collect_only and exit_code == 0:
        collection = extract_collection_summary(log_text)
        if keep_log:
            retained_log = log_path
        else:
            remove_success_artifacts(log_path, junit_path)
            retained_log = None
        if json_output:
            emit_json_result(
                status="passed",
                tier=tier,
                kind="collection",
                exit_code=0,
                duration=elapsed,
                log_path=retained_log,
                detail=collection,
            )
        else:
            print(f"PASS tier={tier} collection={collection!r} duration={elapsed:.2f}s")
            if retained_log is not None:
                print(f"full log: {retained_log}")
        prune_artifacts(max_retained_runs)
        return 0

    stats = None
    if junit_path.exists():
        try:
            stats = parse_junit_report(junit_path)
        except (ET.ParseError, OSError, TypeError, ValueError):
            stats = None

    if exit_code == 0 and stats is not None:
        if tier == "last-failed":
            clear_last_failed()
        if keep_log:
            retained_log = log_path
            retained_junit = junit_path
        else:
            remove_success_artifacts(log_path, junit_path)
            retained_log = retained_junit = None
        if json_output:
            emit_json_result(
                status="passed",
                tier=tier,
                kind="success",
                exit_code=0,
                duration=elapsed,
                stats=stats,
                log_path=retained_log,
                junit_path=retained_junit,
            )
        else:
            print(
                f"PASS tier={tier} selected={stats.selected} passed={stats.passed} "
                f"skipped={stats.ordinary_skipped} xfailed={stats.xfailed} "
                f"subtests={stats.subtests} duration={elapsed:.2f}s"
            )
            if retained_log is not None:
                print(f"full log: {retained_log}")
        prune_artifacts(max_retained_runs)
        return 0

    if exit_code == 0:
        exit_code = 3
        kind = "missing-report"
    else:
        kind = failure_kind(exit_code, log_text, junit_path.exists())

    failed_tests = extract_failed_tests(log_text) or (() if stats is None else stats.failed_tests)
    save_last_failed(failed_tests)
    if json_output:
        emit_json_result(
            status="failed" if kind == "test-failure" else "error",
            tier=tier,
            kind=kind,
            exit_code=exit_code,
            duration=elapsed,
            stats=stats,
            failed_tests=failed_tests,
            log_path=log_path,
            junit_path=junit_path if junit_path.exists() else None,
            detail="\n".join(log_text.splitlines()[-FAILURE_TAIL_LINES:]),
        )
    else:
        label = "FAIL" if kind == "test-failure" else "ERROR"
        print(f"{label} tier={tier} kind={kind} exit={exit_code} duration={elapsed:.2f}s")
        if failed_tests:
            print("failed:")
            for test_id in failed_tests:
                print(f"  {test_id}")
        print_failure_tail(log_text)
        print(f"\nfull log: {log_path}")
    prune_artifacts(max_retained_runs)
    return exit_code


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


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
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit one machine-readable JSON result",
    )
    parser.add_argument("--collect-only", action="store_true", help="collect without running tests")
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="disable xdist for fast and full tiers",
    )
    parser.add_argument(
        "--max-retained-runs",
        type=positive_int,
        default=DEFAULT_MAX_RETAINED_RUNS,
        metavar="N",
        help=f"retain at most N logged runs (default: {DEFAULT_MAX_RETAINED_RUNS})",
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
    if args.verbose and args.json_output:
        parser.error("--verbose and --json cannot be combined")
    if not TESTS_DIR.is_dir():
        parser.error(f"tests directory not found: {TESTS_DIR}")
    return execute_tier(
        args.tier,
        targets=args.targets,
        collect_only=args.collect_only,
        no_parallel=args.no_parallel,
        verbose=args.verbose,
        keep_log=args.keep_log,
        json_output=args.json_output,
        max_retained_runs=args.max_retained_runs,
    )


def run_all_tests() -> int:
    """Backward-compatible entry point for callers of the former master runner."""
    return main(("all",))


if __name__ == "__main__":
    raise SystemExit(main())

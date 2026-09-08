"""Tests for the cross-platform, quiet test-tier runner."""

import sys

from scripts import run_tests


def _option_value(command: list[str], option: str) -> str:
    option_index = len(command) - 1 - command[::-1].index(option)
    return command[option_index + 1]


def test_fast_command_preserves_marker_loadscope_and_fail_fast(tmp_path):
    command = run_tests.build_pytest_command("fast", tmp_path / "results.xml")

    assert command[:3] == [sys.executable, "-m", "pytest"]
    assert _option_value(command, "-m") == "not integration and not release"
    assert ("-n", "auto") == tuple(command[command.index("-n") : command.index("-n") + 2])
    assert "--dist=loadscope" in command
    assert "-x" in command
    assert "--tb=line" in command
    assert command[-1] == str(run_tests.TESTS_DIR)


def test_full_command_preserves_parallel_non_release_contract(tmp_path):
    command = run_tests.build_pytest_command("full", tmp_path / "results.xml")

    assert _option_value(command, "-m") == "not release"
    assert "-n" in command
    assert "--dist=loadscope" in command
    assert "-x" not in command
    assert "--tb=short" in command


def test_release_and_all_commands_are_serial(tmp_path):
    release = run_tests.build_pytest_command("release", tmp_path / "release.xml")
    all_tests = run_tests.build_pytest_command("all", tmp_path / "all.xml")

    assert _option_value(release, "-m") == "release"
    assert "-n" not in release
    assert all_tests.count("-m") == 1
    assert "-n" not in all_tests


def test_no_parallel_removes_xdist_without_changing_marker(tmp_path):
    command = run_tests.build_pytest_command(
        "fast", tmp_path / "results.xml", no_parallel=True
    )

    assert "-n" not in command
    assert "--dist=loadscope" not in command
    assert _option_value(command, "-m") == "not integration and not release"


def test_targeted_command_uses_only_supplied_node_ids(tmp_path):
    targets = ("tests/test_core.py", "tests/test_storage.py::test_missing")
    command = run_tests.build_pytest_command(
        "targeted", tmp_path / "results.xml", targets=targets
    )

    assert command[-2:] == list(targets)
    assert str(run_tests.TESTS_DIR) not in command
    assert command.count("-m") == 1


def test_collect_only_omits_junit_and_quiet_mode(tmp_path):
    command = run_tests.build_pytest_command(
        "fast", tmp_path / "results.xml", collect_only=True
    )

    assert "--collect-only" in command
    assert "-q" not in command
    assert "-n" not in command
    assert "--dist=loadscope" not in command
    assert not any(argument.startswith("--junitxml=") for argument in command)


def test_environment_is_copied_and_existing_platform_choice_wins():
    source = {"QT_QPA_PLATFORM": "xcb", "CUSTOM": "value"}

    environment = run_tests.build_test_environment(source)

    assert environment["QT_QPA_PLATFORM"] == "xcb"
    assert environment["SPECTREHUD_NO_GUI_CRASH_POPUP"] == "1"
    assert environment["PYTHONUTF8"] == "1"
    assert environment["PYTHONIOENCODING"] == "utf-8"
    assert source == {"QT_QPA_PLATFORM": "xcb", "CUSTOM": "value"}


def test_junit_parser_reports_counts_xfails_and_failure_ids(tmp_path):
    report = tmp_path / "results.xml"
    report.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites tests="5" failures="1" errors="0" skipped="2" time="1.25">
  <testsuite name="pytest" tests="5" failures="1" errors="0" skipped="2" time="1.25">
    <testcase classname="tests.test_sample" name="test_pass" file="tests/test_sample.py" />
    <testcase classname="tests.test_sample.TestWidget" name="test_failure" file="tests/test_sample.py">
      <failure message="assert false">traceback</failure>
    </testcase>
    <testcase classname="tests.test_sample" name="test_skip" file="tests/test_sample.py">
      <skipped type="pytest.skip" message="platform" />
    </testcase>
    <testcase classname="tests.test_sample" name="test_expected" file="tests/test_sample.py">
      <skipped type="pytest.xfail" message="known" />
    </testcase>
  </testsuite>
</testsuites>
""",
        encoding="utf-8",
    )

    stats = run_tests.parse_junit_report(report)

    assert stats.selected == 4
    assert stats.subtests == 1
    assert stats.passed == 1
    assert stats.failures == 1
    assert stats.errors == 0
    assert stats.skipped == 2
    assert stats.ordinary_skipped == 1
    assert stats.xfailed == 1
    assert stats.duration == 1.25
    assert stats.failed_tests == ("tests/test_sample.py::TestWidget::test_failure",)


def test_failure_helpers_prefer_terminal_node_ids_and_classify_infrastructure():
    log = "FAILED tests/test_sample.py::test_case[param] - assert False\n"

    assert run_tests.extract_failed_tests(log) == (
        "tests/test_sample.py::test_case[param]",
    )
    assert run_tests.failure_kind(1, "node down: Not properly terminated", False) == (
        "worker-crash"
    )
    assert run_tests.failure_kind(1, "ERROR collecting tests/test_bad.py", True) == (
        "collection"
    )
    assert run_tests.failure_kind(2, "", False) == "interrupted"
    assert run_tests.failure_kind(130, "", False) == "interrupted"
    assert run_tests.failure_kind(5, "", False) == "no-tests-collected"


def test_success_prints_summary_and_removes_artifacts(tmp_path, monkeypatch, capsys):
    log_path = tmp_path / "run.log"
    junit_path = tmp_path / "run.xml"
    monkeypatch.setattr(run_tests, "create_artifact_paths", lambda _tier: (log_path, junit_path))

    def fake_run(_command, *, environment, log_path, verbose):
        assert environment["QT_QPA_PLATFORM"]
        assert verbose is False
        log_path.write_text("one passed\n", encoding="utf-8")
        junit_path.write_text(
            '<testsuite tests="1" failures="0" errors="0" skipped="0" time="0.1">'
            '<testcase classname="tests.test_sample" name="test_pass" />'
            "</testsuite>",
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(run_tests, "run_process", fake_run)

    assert run_tests.execute_tier("targeted", targets=("tests/test_sample.py",)) == 0

    output = capsys.readouterr().out
    assert "PASS tier=targeted selected=1 passed=1 skipped=0 xfailed=0 subtests=0" in output
    assert not log_path.exists()
    assert not junit_path.exists()


def test_test_failure_keeps_log_and_shows_actionable_tail(tmp_path, monkeypatch, capsys):
    log_path = tmp_path / "run.log"
    junit_path = tmp_path / "run.xml"
    monkeypatch.setattr(run_tests, "create_artifact_paths", lambda _tier: (log_path, junit_path))

    def fake_run(_command, *, environment, log_path, verbose):
        log_path.write_text(
            "FAILED tests/test_sample.py::test_failure - assert False\n", encoding="utf-8"
        )
        junit_path.write_text(
            '<testsuite tests="1" failures="1" errors="0" skipped="0" time="0.1">'
            '<testcase classname="tests.test_sample" name="test_failure" '
            'file="tests/test_sample.py"><failure>traceback</failure></testcase>'
            "</testsuite>",
            encoding="utf-8",
        )
        return 1

    monkeypatch.setattr(run_tests, "run_process", fake_run)

    assert run_tests.execute_tier("targeted", targets=("tests/test_sample.py",)) == 1

    output = capsys.readouterr().out
    assert "FAIL tier=targeted kind=test-failure exit=1" in output
    assert "tests/test_sample.py::test_failure" in output
    assert "--- actionable output ---" in output
    assert str(log_path) in output
    assert log_path.exists()


def test_success_without_junit_is_an_infrastructure_error(tmp_path, monkeypatch, capsys):
    log_path = tmp_path / "run.log"
    junit_path = tmp_path / "missing.xml"
    monkeypatch.setattr(run_tests, "create_artifact_paths", lambda _tier: (log_path, junit_path))

    def fake_run(_command, *, environment, log_path, verbose):
        log_path.write_text("pytest exited without report\n", encoding="utf-8")
        return 0

    monkeypatch.setattr(run_tests, "run_process", fake_run)

    assert run_tests.execute_tier("targeted", targets=("tests/test_sample.py",)) == 3
    assert "ERROR tier=targeted kind=missing-report exit=3" in capsys.readouterr().out


def test_artifact_paths_live_in_the_system_temp_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tests, "LOG_ROOT", tmp_path / "spectrehud-tests")

    log_path, junit_path = run_tests.create_artifact_paths("fast")

    assert log_path.parent == tmp_path / "spectrehud-tests"
    assert junit_path.parent == log_path.parent
    assert log_path.suffix == ".log"
    assert junit_path.suffix == ".xml"


def test_legacy_entry_point_selects_all(monkeypatch):
    called = []
    monkeypatch.setattr(run_tests, "main", lambda arguments=None: called.append(arguments) or 0)

    assert run_tests.run_all_tests() == 0
    assert called == [("all",)]

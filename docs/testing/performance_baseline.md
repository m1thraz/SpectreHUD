# Test Performance Baseline

This file records wall-clock measurements used to decide whether test-suite
parallelization is worth evaluating. Times are local observations, not CI
performance guarantees.

## 2026-09-01 — Phase 0 Go/No-Go

- Environment: Windows, Git Bash, project virtual environment
- Command: `time ./scripts/test_fast.sh`
  - Exit status: `0`
  - Wall-clock time: `23.335 s`
- Command: `time ./scripts/test_full.sh`
  - Exit status: `0`
  - Wall-clock time: `197.063 s` (`3m17.063s`)

The first attempt from the canonical Git checkout was discarded because that
checkout had no local `.venv`; the script consequently selected an unrelated
system Python 3.13 installation, which crashed in a Qt test. The recorded runs
used the project's existing virtual environment and the same source revision.

Decision rule: stop when the full run is below 30 seconds; otherwise continue
to Phase 1.

**Decision: GO — continue to Phase 1.** The measured full run is above the
30-second threshold.

## 2026-09-01 — Phase 2 Isolation Audit

The suite was reviewed before enabling xdist. No test changes were required.

### Process and desktop resources

- `tests/test_single_instance.py`: subprocesses use `sys.executable`; every
  lock lives in a unique `TemporaryDirectory`, child processes are terminated
  in `finally` blocks, and no application-wide lock path is shared between
  tests.
- `tests/test_tray_icon.py`: `QProcess.startDetached` is patched, so the test
  does not launch a replacement application.
- `tests/test_hotkeys.py`: the pynput backend is replaced with fake modules;
  no real global keyboard hook is installed.
- `tests/test_cli.py`: subprocesses only read the checked-out `main.py` and
  launcher through `sys.executable`; they do not bind ports or mutate shared
  files.
- `tests/test_packaging_integration.py`: the wheel output uses a unique
  `TemporaryDirectory`. The module remains release-only and is not part of the
  parallel non-release scripts.
- `tests/test_ui_interactions.py`: one test verifies the real Qt clipboard.
  No other test writes the system clipboard, and `loadscope` keeps this module
  on one worker.

### Environment and filesystem isolation

`tests/conftest.py` uses an autouse `tmp_path`/`monkeypatch` fixture to assign a
fresh `SPECTRE_CONFIG_DIR` and `SPECTRE_PROJECTS_DIR` for every test. Additional
assignments in the following unittest modules point only to their own
`TemporaryDirectory` and are removed during teardown:

- `tests/test_adversarial_project_session.py`
- `tests/test_adversarial_report.py`
- `tests/test_adversarial_runtime.py`
- `tests/test_adversarial_screenshot_registry.py`
- `tests/test_adversarial_workflows.py`
- `tests/test_clipboard.py`
- `tests/test_controllers_domain.py`
- `tests/test_logger.py`
- `tests/test_loot_entries.py`
- `tests/test_loot_persistence.py`
- `tests/test_project_manager.py`
- `tests/test_report_builder.py`
- `tests/test_report_editor_tab.py`
- `tests/test_report_file_manager.py`
- `tests/test_screenshot.py`
- `tests/test_smoke.py`
- `tests/test_snippet_importer.py`
- `tests/test_ui_core.py`
- `tests/test_ui_interactions.py`
- `tests/test_ui_loot_theme.py`

The remaining direct or `setdefault` environment writes only select
`QT_QPA_PLATFORM=offscreen` before Qt imports. Every xdist worker is a separate
process and all modules request the same platform, so these writes do not
compete. This applies to the modules above as well as:

- `tests/test_cheatsheet_scroll_geometry.py`
- `tests/test_header_panel.py`
- `tests/test_loot_board.py`
- `tests/test_screenshot_manager.py`
- `tests/test_template_dialogs.py`
- `tests/test_theme_popup_styles.py`
- `tests/test_tray_icon.py`
- `tests/test_window_frame_manager.py`
- `tests/test_workflow_project_report.py`
- `tests/test_workflow_runtime_workspace.py`

### Fixed-resource search

- No test opens or binds a TCP/UDP port. Port-like literals are report,
  snippet, project-field, or URL test data only.
- No test writes to a fixed absolute path outside its temporary directory.
  Absolute-looking paths are validation inputs or UI field values only.
- Application-lock tests derive their lock filename from a unique temporary
  configuration directory.

**Decision: isolation prerequisites satisfied; continue to Phase 3.**

## 2026-09-01 — Phase 4 Serial/Parallel Comparison

Both runs used the same Windows checkout, Python 3.10 project environment,
`not release` marker expression, and short traceback mode. `addopts` was cleared
on the command line only so pytest printed an explicit result summary; the
repository configuration was not changed.

Collection immediately before each run reported **386 tests**. The marker
expression selected 385 non-release tests in both cases.

| Mode | Command-specific options | Result | pytest time | Wall-clock |
| --- | --- | --- | ---: | ---: |
| Serial | `-n0` | 384 passed, 1 skipped, 1 deselected, 15 subtests passed | 283.66 s | 290.236 s |
| Parallel | `-n auto --dist=loadscope` | 384 passed, 1 skipped, 15 subtests passed | 37.82 s | 39.139 s |

xdist omits the deselected release test from its final summary, but the
collection count and the 385 executed non-release outcomes are identical. No
test failed only in the parallel run.

Parallel execution reduced measured wall-clock time by **251.097 seconds**
(approximately **86.5%**) and was approximately **7.4 times faster** for the
non-release suite.

**Decision: comparison accepted; continue to Phase 5.**

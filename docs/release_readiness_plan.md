# Release Readiness Plan: SpectreHUD v2.0.0

> **Status: completed.** This document records the release-hardening work and
> acceptance evidence for the v2.0.0 release.

## Goal

SpectreHUD is released as a stable, reproducibly buildable, and documented
application. This plan deliberately covers release hardening, quality assurance,
and publication preparation rather than new product features.

## Release Version

### Selected release version: v2.0.0

`pyproject.toml`, `main.py --version`, release artifacts, and the final Git tag
all use `v2.0.0`.

**Acceptance evidence:** `spectrehud --version`, package metadata, and the
published `v2.0.0` tag agree.

---

## Phase 1: Test Isolation and Reliability

**Status: completed.** Shared pytest fixtures isolate implicit configuration and
project paths for every test. `run_tests.py` delegates to the same pytest
collection used by CI.

### 1.1 Remove global test state

Some tests previously relied implicitly on the global configuration directory
(`~/.ctf_cheatsheet_widget`), which could cause cross-test side effects.

- Every test fixture receives its own temporary `config_dir` and `projects_dir`.
- Tests do not read or write user configuration, real projects, or global registry
  files.
- `SPECTRE_CONFIG_DIR` and `SPECTRE_PROJECTS_DIR` are restored by test teardown.

**Acceptance evidence:** pytest runs reproducibly in a single process without
accessing user paths.

### 1.2 Align test runners

- `run_tests.py`, pytest, and CI use the same test collection.
- Release documentation treats the concrete CI result as the authoritative test
  count because regression additions and parametrization change it over time.

**Acceptance evidence:** local runner and pytest report the same successful test
collection.

---

## Phase 2: CI as a Release Gate

### 2.1 Verify the CI matrix

- Windows and Linux run all officially supported Python versions.
- Headless Qt setup, linting, tests, wheel build, and wheel installation succeed.
- Individual test and job timeouts provide meaningful logs instead of indefinitely
  consuming CI capacity.

**Implementation:** `ci.yml` consolidates the former overlapping workflows.
Windows and Linux run Python 3.10 through 3.13; Linux 3.11 additionally produces
coverage. A Windows 3.11 packaging job validates syntax, the wheel installation,
and the Windows executable. The release workflow rejects tags that do not match
the package version.

**Acceptance evidence:** the full GitHub CI matrix completed successfully for the
release commit.

### 2.2 Validate release artifacts

- Build the wheel without a runtime network dependency.
- Install the wheel into a fresh test environment.
- Run `spectrehud --help` and `spectrehud --version`.
- Build the Windows executable with PyInstaller and smoke-test it.

**Acceptance evidence:** the wheel verifier confirmed 122 archive files; a fresh
environment installed the wheel and passed both CLI smoke tests. The Windows x64
executable was built with PyInstaller 6.22.2 and passed `--version` and `--help`.
The executable bundles translations, both default snippet files, and report
templates.

---

## Phase 3: Manual Windows Product Acceptance

The following checks were completed in a normal Windows desktop session:

1. Application startup, window display, always-on-top behavior, and tray menu.
2. Global hotkeys for HUD toggle, screenshot capture, and application quit.
3. Clipboard recorder default pause state, activation, recording, and project
   persistence.
4. Screenshot snipping, loot entry creation, report inclusion, and save failures.
5. Project creation and switching, external and empty workspaces, and rollback on
   failures.
6. Template selection, report editing, Change View, Dark/Light HTML export,
   browser editing, and ZIP export.
7. Multi-monitor operation with mixed scaling and negative screen coordinates.
8. Pentest Mode encryption, lock/unlock behavior, password failure handling, and
   absence of plaintext `project_state.json`.
9. Quit behavior for saving, save failures, cancellation, and exit without saving.

**Acceptance evidence:** manual Windows acceptance completed without blockers,
data loss, UI-thread warnings, or unexplained error dialogs.

---

## Phase 4: Security and Documentation Completion

### 4.1 Security regression

- Re-run path traversal, symlink escape, ZIP Slip, oversized import, and image
  limit regressions.
- Keep clipboard recording disabled by default.
- Document plaintext default storage and the scope and limits of optional Pentest
  Mode.

**Acceptance evidence:** adversarial regression tests passed with no open
high- or critical-severity issue.

### 4.2 Release documentation

- Create release notes covering key features, fixes, and compatibility.
- Verify installation, supported platforms, and known limitations.
- Retain Wayland screenshot and privacy notices.

**Acceptance evidence:** [release notes](release_notes_v2.0.0.md), README, and
architecture documentation explain installation, first use, supported platforms,
Wayland limitations, and privacy boundaries without requiring source-code reading.

---

## Phase 5: Release Procedure

1. Create the release candidate branch or tag.
2. Complete CI and manual acceptance.
3. Inspect the Git working tree and commit only intended changes.
4. Create the final `v2.0.0` tag.
5. Publish the wheel and Windows executable as release artifacts.
6. Publish release notes and artifact links/checksums.

## Go / No-Go Checklist

- [x] Version number is consistent (`v2.0.0`).
- [x] Full isolated local test run passed (344 passed, 1 expected skip).
- [x] CI passed on supported platforms.
- [x] Wheel and executable built and passed local smoke tests.
- [x] Manual Windows acceptance completed without blockers.
- [x] Security regressions passed.
- [x] Release notes and known limitations are documented.
- [x] Git working tree was checked and the release tag was created.

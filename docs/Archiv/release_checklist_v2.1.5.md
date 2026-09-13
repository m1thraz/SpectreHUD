# SpectreHUD v2.1.5 Release Checklist

This checklist tracks the patch-release handoff. The v2.1.5 commit, tag, and GitHub
release are intentionally left to the repository owner after CI validation.

## Prepared in the release change

- [x] `pyproject.toml` package version is `2.1.5`.
- [x] `core/cli.py` `APP_VERSION` is `2.1.5`.
- [x] `spectrehud --version` reports `SpectreHUD 2.1.5` from source.
- [x] Package metadata tests enforce agreement with `APP_VERSION`.
- [x] Changelog and v2.1.5 release notes contain the former Unreleased items.
- [x] README links to the v2.1.5 release notes.
- [x] Architecture documentation identifies v2.1.5 as its current baseline.
- [x] Historical release documents remain unchanged.

## Local release verification

- [x] Ruff passes.
- [x] Focused version, CLI, packaging-metadata, settings-version, persistence,
  diagnostics, and dialog tests pass (58 passed).
- [x] Release test suite passes (16 passed in 18.78s).
- [x] Full local safety gate passes (`1000 passed, 4 skipped, 15 subtests` in
  69.81s).
- [x] The v2.1.5 wheel passes repository verification (203 files) and
  fresh-environment `--version` / `--help` smoke tests.
- [x] Manual smoke test confirms startup, project load/save and legacy migration,
  diagnostics actions, copyable error dialogs, Cheatsheet switching, screenshot
  phase assignment, and clean shutdown.

## Repository-owner release steps

- [x] Review, commit, and push the prepared v2.1.5 release state.
- [x] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [x] Create the annotated v2.1.5 tag from the CI-verified commit and push it.
- [x] Confirm the release workflow publishes the Windows executable, Debian packages,
  and wheel.
- [x] Download the published executable/deb and verify `--version`, startup, and UI.
- [x] Confirm the GitHub release description links to
  `docs/release_notes_v2.1.5.md`.

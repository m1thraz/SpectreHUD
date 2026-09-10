# SpectreHUD v2.0.1 Release Checklist

This checklist tracks the patch-release handoff. The `v2.0.1` tag and GitHub
release are intentionally left to the repository owner.

## Prepared in the release commit

- [x] `pyproject.toml` package version is `2.0.1`.
- [x] `spectrehud --version` reports `SpectreHUD 2.0.1`.
- [x] Version regression tests expect `2.0.1`.
- [x] Changelog and v2.0.1 release notes are present.
- [x] README and architecture version references are current.
- [x] v2.0.0 release evidence remains unchanged as historical documentation.

## Local release verification

- [x] Full offline-capable pytest suite passes.
- [x] Wheel builds without dependency downloads and passes `verify_wheel.py`
  (141 files verified).
- [x] Wheel CLI smoke test reports `SpectreHUD 2.0.1` from a fresh virtual
  environment.
- [x] Manual Windows smoke test confirms theme-change restart and
  single-instance behaviour.

Final automated verification: 351 passed, 1 skipped, 15 subtests passed.

## Repository-owner release steps

- [x] Commit and push the prepared v2.0.1 release state.
- [x] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [x] Create the annotated `v2.0.1` tag from the verified commit and push it.
- [x] Confirm the release workflow publishes the Windows executable and wheel.
- [x] Download the published executable and verify `--version`, startup, theme
  selection/restart, Loot list/Kanban switching, and one persisted card reorder.
- [x] Confirm the GitHub release description links to
  `docs/release_notes_v2.0.1.md`.

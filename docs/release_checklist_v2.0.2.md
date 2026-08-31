# SpectreHUD v2.0.2 Release Checklist

This checklist tracks the patch-release handoff. The `v2.0.2` tag and GitHub
release are intentionally left to the repository owner.

## Prepared in the release commit

- [x] `pyproject.toml` package version is `2.0.2`.
- [x] `spectrehud --version` reports `SpectreHUD 2.0.2`.
- [x] Version regression tests expect `2.0.2`.
- [x] Changelog and v2.0.2 release notes are present.
- [x] README, architecture guide, and bug-report template reference the current
  release.
- [x] Historical v2.0.0 and v2.0.1 release documents remain unchanged.

## Local release verification

- [x] Full pytest suite passes: 370 passed, 1 skipped.
- [x] Wheel builds and passes `scripts/verify_wheel.py` (138 files verified).
- [x] Source and installed-wheel CLI smoke tests report `SpectreHUD 2.0.2`.
- [ ] Manual Windows smoke test confirms startup, font changes, theme restart,
  Loot list/Kanban switching, and clean shutdown.

## Repository-owner release steps

- [x] Commit and push the prepared v2.0.2 release state.
- [x] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [x] Create the annotated `v2.0.2` tag from the verified commit and push it.
- [x] Confirm the release workflow publishes the Windows executable and wheel.
- [x] Download the published executable and verify `--version`, startup, font
  selection, theme restart, Loot view switching, and shutdown.
- [x] Confirm the GitHub release description links to
  `docs/release_notes_v2.0.2.md`.

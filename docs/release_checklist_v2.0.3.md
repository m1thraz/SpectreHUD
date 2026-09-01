# SpectreHUD v2.0.3 Release Checklist

This checklist tracks the patch-release handoff. The `v2.0.3` tag and GitHub
release are intentionally left to the repository owner.

## Prepared in the release change

- [x] `pyproject.toml` package version is `2.0.3`.
- [x] `spectrehud --version` reports `SpectreHUD 2.0.3`.
- [x] Version regression tests expect `2.0.3`.
- [x] Changelog and v2.0.3 release notes are present.
- [x] README, architecture guide, development guide, and contributor guide
  describe the current release and test workflow.
- [x] Historical v2.0.0 through v2.0.2 release documents remain unchanged.

## Local release verification

- [x] Focused version, CLI, and packaging-metadata tests pass (8 passed).
- [x] Complete unfiltered pytest gate passes, including release tests
  (385 passed, 1 skipped, 15 subtests passed).
- [x] Wheel builds and passes `scripts/verify_wheel.py` (139 files verified).
- [x] Source and installed-wheel CLI smoke tests report `SpectreHUD 2.0.3`.
- [ ] Manual Windows smoke test confirms startup, HUD transparency, Report
  Editor transparency, theme changes, and clean shutdown.

## Repository-owner release steps

- [ ] Review, commit, and push the prepared v2.0.3 release state.
- [ ] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [ ] Create the annotated `v2.0.3` tag from the verified commit and push it.
- [ ] Confirm the release workflow publishes the Windows executable and wheel.
- [ ] Download the published executable and verify `--version`, startup,
  Appearance settings, theme restart, and shutdown.
- [ ] Confirm the GitHub release description links to
  `docs/release_notes_v2.0.3.md`.

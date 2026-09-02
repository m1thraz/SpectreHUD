# SpectreHUD v2.0.4 Release Checklist

This checklist tracks the patch-release handoff. The `v2.0.4` tag and GitHub
release are intentionally left to the repository owner.

## Prepared in the release change

- [x] `pyproject.toml` package version is `2.0.4`.
- [x] `spectrehud --version` reports `SpectreHUD 2.0.4`.
- [x] Version regression tests expect `2.0.4`.
- [x] Changelog and v2.0.4 release notes are present.
- [x] README, architecture guide, and Linux platform audit reference the current
  release state.
- [x] Historical v2.0.0 through v2.0.3 release documents remain unchanged.

## Local release verification

- [x] Focused version, CLI, packaging-metadata, and release tests pass.
- [ ] Linter passes without new findings. Ruff is not installed in the local
  Python environment; confirmation remains with CI.
- [x] Complete unfiltered pytest gate passes, including release tests
  (504 passed, 4 skipped, 15 subtests passed).
- [x] Wheel builds and passes `scripts/verify_wheel.py` (157 files verified).
- [x] Source and installed-wheel CLI smoke tests report `SpectreHUD 2.0.4`;
  the installed `--help` command also exits successfully.
- [ ] Manual Windows smoke test confirms startup, Report Editor Loot append,
  export, theme display, and clean shutdown.
- [ ] Manual Linux X11/Wayland acceptance remains tracked in
  `docs/linux_platform_audit.md`.

## Repository-owner release steps

- [ ] Review, commit, and push the prepared v2.0.4 release state.
- [ ] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [ ] Create the annotated `v2.0.4` tag from the verified commit and push it.
- [ ] Confirm the release workflow publishes the Windows executable and wheel.
- [ ] Download the published artifacts and verify `--version`, startup, report
  synchronization, exports, and shutdown.
- [ ] Confirm the GitHub release description links to
  `docs/release_notes_v2.0.4.md`.

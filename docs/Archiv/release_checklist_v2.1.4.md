# SpectreHUD v2.1.4 Release Checklist

This checklist tracks the patch-release handoff. The v2.1.4 commit, tag, and GitHub
release are intentionally left to the repository owner after CI validation.

## Prepared in the release change

- [x] `pyproject.toml` package version is `2.1.4`.
- [x] `core/cli.py` `APP_VERSION` is `2.1.4`.
- [x] `spectrehud --version` reports `SpectreHUD 2.1.4` from source.
- [x] Package metadata tests enforce agreement with `APP_VERSION`.
- [x] Changelog and v2.1.4 release notes contain the former Unreleased items.
- [x] README links to the v2.1.4 release notes.
- [x] Architecture documentation identifies v2.1.4 as its current baseline.
- [x] Historical release documents remain unchanged.

## Local release verification

- [x] Ruff passes.
- [x] Focused version, CLI, packaging-metadata, and update-check tests pass
  (25 passed).
- [x] Release test suite passes (16 passed in 16.69s).
- [x] Full local safety gate passes (`995 passed, 4 skipped, 15 subtests` in
  276.72s).
- [x] The v2.1.4 wheel passes repository verification (201 files) and fresh-environment
  `--version` / `--help` smoke tests.
- [ ] Manual smoke test confirms startup, Report Navigator, themed report toolbar,
  global recorder shortcut, update check, template dialogs, and clean shutdown.

## Repository-owner release steps

- [ ] Review, commit, and push the prepared v2.1.4 release state.
- [ ] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [ ] Create the annotated v2.1.4 tag from the CI-verified commit and push it.
- [ ] Confirm the release workflow publishes the Windows executable, Debian packages,
  and wheel.
- [ ] Download the published executable/deb and verify `--version`, startup, and UI.
- [ ] Confirm the GitHub release description links to
  `docs/release_notes_v2.1.4.md`.

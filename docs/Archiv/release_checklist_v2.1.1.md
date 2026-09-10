# SpectreHUD v2.1.1 Release Checklist

This checklist tracks the patch-release handoff. The v2.1.1 tag and GitHub
release are intentionally left to the repository owner after CI validation.

## Prepared in the release change

- [x] `pyproject.toml` package version is `2.1.1`.
- [x] `core/cli.py` `APP_VERSION` is `2.1.1`.
- [x] `spectrehud --version` reports `SpectreHUD 2.1.1` from source.
- [x] Package metadata tests enforce agreement with `APP_VERSION`.
- [x] Changelog and v2.1.1 release notes contain the former Unreleased items.
- [x] README links to the v2.1.1 release notes.
- [x] Historical release documents remain unchanged.

## Local release verification

- [x] Ruff passes.
- [x] Focused version, CLI, and packaging-metadata tests pass.
- [x] Release test suite passes (`python -m pytest -m release -q`).
- [x] Full local safety gate passes (`python scripts/run_tests.py`):
  `860 passed, 4 skipped, 15 subtests passed` in 6:33.
- [x] The v2.1.1 wheel passes repository verification and fresh-environment
  `--version` / `--help` smoke tests.
- [ ] Manual smoke test confirms startup, shortcut overview, phase switching and
  inheritance, snippet interpolation, Obsidian append, and clean shutdown.

## Repository-owner release steps

- [ ] Review, commit, and push the prepared v2.1.1 release state.
- [ ] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [ ] Create the annotated v2.1.1 tag from the CI-verified commit and push it.
- [ ] Confirm the release workflow publishes the Windows executable, Debian packages,
  and wheel.
- [ ] Download the published executable/deb and verify `--version`, startup, and UI.
- [ ] Confirm the GitHub release description links to
  `docs/release_notes_v2.1.1.md`.

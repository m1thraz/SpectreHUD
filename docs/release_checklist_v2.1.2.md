# SpectreHUD v2.1.2 Release Checklist

This checklist tracks the patch-release handoff. The v2.1.2 commit, tag, and GitHub
release are intentionally left to the repository owner after CI validation.

## Prepared in the release change

- [x] `pyproject.toml` package version is `2.1.2`.
- [x] `core/cli.py` `APP_VERSION` is `2.1.2`.
- [x] `spectrehud --version` reports `SpectreHUD 2.1.2` from source.
- [x] Package metadata tests enforce agreement with `APP_VERSION`.
- [x] Changelog and v2.1.2 release notes contain the former Unreleased items.
- [x] README links to the v2.1.2 release notes.
- [x] Architecture documentation identifies v2.1.2 as its current baseline.
- [x] Historical release documents remain unchanged.

## Local release verification

- [x] Ruff passes.
- [x] Focused version, CLI, and packaging-metadata tests pass.
- [x] Release test suite passes (`python -m pytest -m release -q`) in 19.14 s.
- [x] Full local safety gate passes (`python scripts/run_tests.py`):
  `941 passed, 4 skipped, 15 subtests passed` in 6:23.
- [x] The v2.1.2 wheel contains 198 files, passes repository verification, and
  passes fresh-environment
  `--version` / `--help` smoke tests.
- [ ] Manual smoke test confirms startup, Quick Notes stream/focus review, collapsed
  toolbar restoration, Interactive export, Professional Print, Add Missing Loot,
  Obsidian/CherryTree export, and clean shutdown.
- [ ] Manual browser-print review confirms clean PDF output with browser-native headers
  and footers disabled.

## Repository-owner release steps

- [ ] Review, commit, and push the prepared v2.1.2 release state.
- [ ] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [ ] Create the annotated v2.1.2 tag from the CI-verified commit and push it.
- [ ] Confirm the release workflow publishes the Windows executable, Debian packages,
  and wheel.
- [ ] Download the published executable/deb and verify `--version`, startup, and UI.
- [ ] Confirm the GitHub release description links to
  `docs/release_notes_v2.1.2.md`.

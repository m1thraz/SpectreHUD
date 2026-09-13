# SpectreHUD v2.1.6 Release Checklist

This checklist tracks the patch-release handoff. The v2.1.6 commit, tag, and GitHub
release are intentionally left to the repository owner after CI validation.

## Prepared in the release change

- [x] `pyproject.toml` package version is `2.1.6`.
- [x] `core/cli.py` `APP_VERSION` is `2.1.6`.
- [x] `spectrehud --version` reports `SpectreHUD 2.1.6` from source.
- [x] Package metadata tests enforce agreement with `APP_VERSION`.
- [x] Changelog and v2.1.6 release notes contain the former Unreleased items.
- [x] README links to the v2.1.6 release notes.
- [x] Architecture documentation identifies v2.1.6 as its current baseline.
- [x] Historical release documents remain unchanged in `docs/Archiv/`.

## Local release verification

- [x] Ruff passes (`ruff check .`).
- [x] Focused version, CLI, packaging-metadata, settings-version, and domain tests pass (34 passed).
- [x] Release test suite passes (`python -m pytest -m release -q`, 24 passed in 26s).
- [x] Architecture boundaries, import linter, and static typing pass (`mypy`, `lint-imports --no-cache`).
- [x] Full local safety gate passes (`python scripts/run_tests.py full --no-parallel`, 1111 passed, 4 skipped, 15 subtests).

## Repository-owner release steps

- [ ] Review, commit, and push the prepared v2.1.6 release state.
- [ ] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [ ] Create the annotated v2.1.6 tag from the CI-verified commit and push it.
- [ ] Confirm the release workflow publishes the Windows executable, Debian packages,
  and wheel.
- [ ] Download the published executable/deb and verify `--version`, startup, and UI.
- [ ] Confirm the GitHub release description links to
  `docs/release_notes_v2.1.6.md`.

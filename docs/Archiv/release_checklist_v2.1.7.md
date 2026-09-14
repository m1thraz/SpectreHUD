# SpectreHUD v2.1.7 Release Checklist

This checklist tracks the patch-release handoff. The v2.1.7 commit, tag, and GitHub
release are intentionally left to the repository owner after CI validation.

## Prepared in the release change

- [x] `pyproject.toml` package version is `2.1.7`.
- [x] `core/cli.py` `APP_VERSION` is `2.1.7`.
- [x] `spectrehud --version` reports `SpectreHUD 2.1.7` from source.
- [x] Package metadata tests enforce agreement with `APP_VERSION`.
- [x] Changelog contains only the user-facing v2.1.7 changes.
- [x] Detailed v2.1.7 release notes cover the implementation and compatibility details.
- [x] README links to the v2.1.7 release notes.
- [x] Architecture documentation identifies v2.1.7 as its current baseline.
- [x] v2.1.6 release documents are preserved unchanged in `docs/Archiv/`.

## Local release verification

- [x] Ruff passes (`ruff check .`).
- [x] Focused version, CLI, packaging-metadata, settings-version, architecture, and
  wheel-verifier tests pass (49 passed).
- [x] Release test suite passes (`python -m pytest -m release -q`, 25 passed).
- [x] Import boundaries pass (`lint-imports --no-cache`, 8 contracts kept).
- [ ] Repository-wide static typing remains open (`mypy`: 591 errors in 76 files);
  the changed Report Editor production module passes its focused Mypy check.
- [x] Full local safety gate passes (`python scripts/run_tests.py`: 1169 passed,
  4 skipped, 15 subtests).
- [x] The v2.1.7 wheel contains 232 files, passes the expanded artifact verifier,
  and a clean Python 3.10 installation passes `spectrehud --version` and `--help`.

## Repository-owner release steps

- [ ] Review, commit, and push the prepared v2.1.7 release state.
- [ ] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [ ] Create the annotated v2.1.7 tag from the CI-verified commit and push it.
- [ ] Confirm the release workflow publishes the Windows executable, Debian packages,
  and wheel.
- [ ] Download the published executable/deb and verify `--version`, startup, and UI.
- [ ] Confirm the GitHub release description links to
  `docs/release_notes_v2.1.7.md`.

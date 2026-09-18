# SpectreHUD v2.1.9 Release Checklist

This checklist tracks the patch-release handoff. The v2.1.9 commit, tag, and GitHub
release are intentionally left to the repository owner after CI validation.

## Prepared in the release change

- [x] `pyproject.toml` package version is `2.1.9`.
- [x] `core/cli.py` `APP_VERSION` is `2.1.9`.
- [x] `spectrehud --version` reports `SpectreHUD 2.1.9` from source.
- [x] Package metadata tests enforce agreement with `APP_VERSION`.
- [x] Changelog contains only the user-facing v2.1.9 changes.
- [x] Detailed v2.1.9 release notes cover the implementation and compatibility details.
- [x] README links to the v2.1.9 release notes.
- [x] Architecture documentation identifies v2.1.9 as its current baseline.
- [x] v2.1.8 release documents are preserved unchanged in `docs/Archiv/`.

## Local release verification

- [x] Ruff passes (`ruff check .`).
- [x] Focused version, CLI, packaging-metadata, settings-version, architecture, and
  wheel-verifier tests pass.
- [x] Release test suite passes (`python -m pytest -m release -q`).
- [x] Import boundaries pass (`lint-imports --no-cache`, 9 contracts kept).
- [ ] Repository-wide static typing remains open (`mypy`);
  focused Mypy checks on changed modules pass.
- [x] Full local safety gate passes.

## Repository-owner release steps

- [ ] Review, commit, and push the prepared v2.1.9 release state.
- [ ] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [ ] Create the annotated v2.1.9 tag from the CI-verified commit and push it.
- [ ] Confirm the release workflow publishes the Windows executable, Debian packages,
  and wheel.
- [ ] Download the published executable/deb and verify `--version`, startup, and UI.
- [ ] Confirm the GitHub release description links to
  `docs/release_notes_v2.1.9.md`.

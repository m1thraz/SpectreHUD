# SpectreHUD v2.2.0 Release Checklist

This checklist tracks the release handoff. The v2.2.0 commit, tag, and GitHub
release are intentionally left to the repository owner after CI validation.

## Prepared in the release change

- [x] `pyproject.toml` package version is `2.2.0`.
- [x] `core/cli.py` `APP_VERSION` is `2.2.0`.
- [x] `spectrehud --version` reports `SpectreHUD 2.2.0` from source.
- [x] Package metadata tests enforce agreement with `APP_VERSION`.
- [x] Changelog contains user-facing v2.2.0 changes.
- [x] Detailed v2.2.0 release notes cover implementation and compatibility details.
- [x] README links to the v2.2.0 release notes.
- [x] Architecture documentation identifies v2.2.0 as its current baseline.
- [x] v2.1.9 release documents are preserved in `docs/Archiv/`.

## Local release verification

- [x] Ruff passes (`ruff check .`).
- [x] Focused version, CLI, packaging-metadata, settings-version, architecture, and wheel-verifier tests pass.
- [x] Release test suite passes (`python -m pytest -m release -q`).
- [x] Import boundaries pass (`lint-imports --no-cache`).
- [x] Full local safety gate passes.

## Repository-owner release steps

- [ ] Review, commit, and push the prepared v2.2.0 release state.
- [ ] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [ ] Create the annotated v2.2.0 tag from the CI-verified commit and push it.
- [ ] Confirm the release workflow publishes the Windows executable, Debian packages, and wheel.
- [ ] Download the published executable/deb and verify `--version`, startup, and UI.
- [ ] Confirm the GitHub release description links to `docs/release_notes_v2.2.0.md`.

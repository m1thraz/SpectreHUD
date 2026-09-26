# SpectreHUD v2.2.2 Release Checklist

This checklist tracks the release handoff. The v2.2.2 commit, tag, and GitHub
release are intentionally left to the repository owner after CI validation.

## Prepared in the release change

- [x] `pyproject.toml` package version is `2.2.2`.
- [x] `core/cli.py` `APP_VERSION` is `2.2.2`.
- [x] `spectrehud --version` reports `SpectreHUD 2.2.2` from source.
- [x] Package metadata tests enforce agreement with `APP_VERSION`.
- [x] Changelog contains only user-facing v2.2.2 changes.
- [x] Detailed v2.2.2 release notes cover export behavior and verification details.
- [x] README links to the v2.2.2 release notes.
- [x] Architecture documentation identifies v2.2.2 as its current baseline.
- [x] v2.2.1 release documents are preserved in `docs/Archiv/`.

## Local release verification

- [x] Ruff passes (`ruff check .`).
- [x] Focused version, CLI, packaging-metadata, settings-version, architecture, and wheel-verifier tests pass.
- [x] Release test suite passes (`python -m pytest -m release -q`).
- [x] Import boundaries pass (`lint-imports --no-cache`).
- [x] Full local safety gate passes.
- [x] Wheel metadata and an isolated installed `spectrehud --version` report v2.2.2.

## Repository-owner release steps

- [ ] Review, commit, and push the prepared v2.2.2 release state.
- [ ] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [ ] Create the annotated v2.2.2 tag from the CI-verified commit and push it.
- [ ] Confirm the release workflow publishes the Windows executable, Debian packages, and wheel.
- [ ] Download the published executable/deb and verify `--version`, startup, and UI.
- [ ] Confirm the GitHub release description links to `docs/release_notes_v2.2.2.md`.

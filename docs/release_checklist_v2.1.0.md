# SpectreHUD v2.1.0 Release Checklist

This checklist tracks the minor-release handoff. The v2.1.0 tag and GitHub
release are intentionally left to the repository owner.

## Prepared in the release change

- [x] pyproject.toml package version is 2.1.0.
- [x] core/cli.py APP_VERSION is 2.1.0.
- [x] spectrehud --version reports SpectreHUD 2.1.0.
- [x] Version regression tests expect 2.1.0.
- [x] Changelog and v2.1.0 release notes are present.
- [x] Historical v2.0.0 through v2.0.9 release documents remain unchanged.

## Local release verification

- [x] Focused version, CLI, and packaging-metadata tests pass.
- [x] Release test suite passes (python -m pytest -m release -q).
- [x] Source and installed CLI smoke tests report SpectreHUD 2.1.0.
- [x] Manual smoke test confirms startup, Phase Taxonomy, Loot Board tactile cards, Quick Notes workflow, badge truncation protection, and clean shutdown.

## Repository-owner release steps

- [ ] Review, commit, and push the prepared v2.1.0 release state.
- [ ] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [ ] Create the annotated v2.1.0 tag from the verified commit and push it.
- [ ] Confirm the release workflow publishes the Windows executable, Debian packages, and wheel.
- [ ] Download the published executable/deb and verify --version, startup, and UI.
- [ ] Confirm the GitHub release description links to docs/release_notes_v2.1.0.md.

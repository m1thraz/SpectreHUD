# SpectreHUD v2.0.7 Release Checklist

This checklist tracks the patch-release handoff. The v2.0.7 tag and GitHub
release are intentionally left to the repository owner.

## Prepared in the release change

- [x] pyproject.toml package version is 2.0.7.
- [x] spectrehud --version reports SpectreHUD 2.0.7.
- [x] Version regression tests expect 2.0.7.
- [x] Changelog and v2.0.7 release notes are present.
- [x] Historical v2.0.0 through v2.0.6 release documents remain unchanged.

## Local release verification

- [x] Focused version, CLI, and packaging-metadata tests pass.
- [x] Complete test suite passes (100% passed).
- [x] Source and installed CLI smoke tests report SpectreHUD 2.0.7.
- [x] Manual smoke test confirms startup, Report Editor two-tier toolbar, scroll sync, outline navigation, crash recovery, and clean shutdown.

## Repository-owner release steps

- [ ] Review, commit, and push the prepared v2.0.7 release state.
- [ ] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [ ] Create the annotated v2.0.7 tag from the verified commit and push it.
- [ ] Confirm the release workflow publishes the Windows executable, Debian packages, and wheel.
- [ ] Download the published executable/deb and verify --version, startup, and UI.
- [ ] Confirm the GitHub release description links to docs/release_notes_v2.0.7.md.

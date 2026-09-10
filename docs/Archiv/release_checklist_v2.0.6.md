# SpectreHUD v2.0.6 Release Checklist

This checklist tracks the patch-release handoff. The 2.0.6 tag and GitHub
release are intentionally left to the repository owner.

## Prepared in the release change

- [x] pyproject.toml package version is 2.0.6.
- [x] spectrehud --version reports SpectreHUD 2.0.6.
- [x] Version regression tests expect 2.0.6.
- [x] Changelog and v2.0.6 release notes are present.
- [x] Historical v2.0.0 through v2.0.5 release documents remain unchanged.

## Local release verification

- [x] Focused version, CLI, and packaging-metadata tests pass.
- [x] Complete Fast-Gate suite passes (100% passed).
- [x] Wheel builds and passes scripts/verify_wheel.py.
- [x] Source and installed CLI smoke tests report SpectreHUD 2.0.6.
- [x] Manual smoke test confirms startup, responsive category bar, Auth/Scope popovers, and clean shutdown.

## Repository-owner release steps

- [x] Review, commit, and push the prepared v2.0.6 release state.
- [x] Confirm the GitHub CI matrix and CodeQL complete successfully.
- [x] Create the annotated v2.0.6 tag from the verified commit and push it.
- [x] Confirm the release workflow publishes the Windows executable, Debian packages, and wheel.
- [x] Download the published executable/deb and verify --version, startup, and UI.
- [x] Confirm the GitHub release description links to docs/release_notes_v2.0.6.md.

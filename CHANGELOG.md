# Changelog

Notable user-facing changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use
semantic versioning.

## [Unreleased]

## [2.0.1] - 2026-08-31

### Added

- Theme selection with Slate, Nord, Warm Night, High Contrast, Matrix Terminal,
  Red Team, Solarized, and Daylight variants.
- Persistent Kanban card ordering, drag feedback, and a direct Loot view toggle.

### Changed

- Split themes, typography, and Loot presentation into a dedicated Appearance
  settings tab.
- Saving a different application theme now performs a controlled restart so the
  selection becomes active immediately.
- Consolidated report exports and Obsidian report/loot export coordination.
- Split major UI and project-persistence responsibilities into focused modules.
- Curated adversarial regression coverage against the documented desktop threat
  model.

### Fixed

- The optional minimize-after-copy setting now applies to copied Cheatsheet,
  Loot, Kanban, and History content.
- The installed `spectrehud --help` and `--version` commands now run without
  importing Qt or bootstrapping the desktop application.

## [2.0.0] - 2026-08-30

First documented public release. It introduced the project-oriented workflow,
Report Editor V2, standalone HTML/Obsidian/CherryTree exports, Pentest Mode,
single-instance protection, atomic persistence, and the English/German UI.

See the [full v2.0.0 release notes](docs/release_notes_v2.0.0.md).

Earlier repository tags predate the maintained changelog and are intentionally
not reconstructed without authoritative release notes.

[Unreleased]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.1...HEAD
[2.0.1]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/m1thraz/SpectreHUD/releases/tag/v2.0.0

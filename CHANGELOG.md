# Changelog

Notable user-facing changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use
semantic versioning.

## [Unreleased]

## [2.0.2] - 2026-08-31

### Added

- Close button in the HUD header that quits through the transactional
  shutdown path (dirty-report confirmation, project state save, geometry
  flush), matching tray quit and Ctrl+Q.

### Changed

- Swapped the Loot and History mode tab order to Cheatsheet · History · Loot · Report.
- UI and code font changes now update the running application immediately;
  unavailable local font families are visibly marked and disabled.
- Removed the redundant Loot presentation switch from Appearance settings. The
  persistent toggle in the Loot window is now the single view control.

### Fixed

- Tooltips and the settings theme list no longer render as unreadable black
  surfaces in light themes such as Daylight; the affected scroll areas are now
  styled through the central application stylesheet instead of per-widget
  stylesheets.
- Late mouse events during the theme-restart teardown no longer raise an
  unhandled `RuntimeError` from the window frame event filter.
- Restored transparent scroll-area viewports without reintroducing local widget
  stylesheets that interfere with popup theming.
- Cheatsheet filtering now recalculates content geometry immediately and no
  longer leaves a large stale scroll area below the final card.
- Long Kanban Loot content is capped to a five-line, ellipsized preview without
  nested scrollbars or oversized cards.
- The Loot Markdown export tooltip now follows the active interface language.

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

[Unreleased]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.2...HEAD
[2.0.2]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/m1thraz/SpectreHUD/releases/tag/v2.0.0

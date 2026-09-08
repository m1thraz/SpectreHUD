# Changelog

Notable user-facing changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use
semantic versioning.

## [Unreleased]

### Added

* Compact semantic Report Navigator for jumping to marked sections and findings without leaving the existing editor.

## [2.1.3] - 2026-09-08

### Added

* Protected Report Editor metadata view that hides Spectre markers by default and exposes them through an explicit toolbar toggle.

### Fixed

* Cancel delayed Quick-IP and snippet-copy feedback when their widgets are closed, preventing stale Qt callbacks from touching deleted buttons.
* Allow note text to be edited inline in Focus Review mode while retaining the details dialog for phase, target, and status changes.
* Restart Focus Review at the first unfinished note after a completed pass and show a clear completion notice instead of an empty view.
* Keep inline note editing exclusive to Focus Review while restoring the full edit dialog on double-click in the regular Notes stream.

### Changed

* Aligned the report-generation and template-manager windows with SpectreHUD's frameless dialog chrome instead of native light title bars.
* Made header action buttons and default QtAwesome icons inherit the active theme palette instead of retaining Cyber Dark cyan.
* Moved the Shortcut Help dialog from hard-coded Cyber Dark colors to the active application theme palette.
* Reordered report exports around HTML/PDF first and Markdown last, and simplified HTML choices to Professional Print first and an editable classic web version without a dark export option.
* Made Professional Print HTML editable in the browser, including the existing edited-copy download workflow.
* Replaced generated report severity emojis with export-safe text labels styled consistently across Markdown and HTML profiles.

## [2.1.2] - 2026-09-07

### Added

* Optional one-note-at-a-time focus review for working through the Quick Notes backlog.
* Local light/dark appearance toggle for the Report Editor and live-preview panes.
* Compact live-preview indicators for manual report page breaks.
* Cross-export report spacers with small, medium, and large toolbar presets.
* Interactive and Professional Print HTML export profiles backed by persistent semantic report-section markers.
* Professional Print cover pages and a restrained, A4-oriented report design system.

### Changed

* Redesigned Quick Notes as a chronological, age-aware stream with simplified rows, contextual actions, completion undo, and an explicit bulk-selection mode.
* Variable Bar and Report toolbar collapse now hide their complete surfaces and actions, leaving only the restore control visible.
* Newly generated report findings now use structured metadata and description blocks across Interactive and Professional Print exports.
* Professional Print omits empty phase sections while preserving phases that contain manual notes.
* Reworked built-in report templates so pentest reports use assessment-oriented findings and attack-path sections while CTF reports retain their chronological workflow.
* Added optional finding recommendations, recommendation-backed action plans, and gap-free Professional Print section numbering.
* Added controlled Professional Print pagination, running page furniture, and print-stable finding and table layouts.
* Refined Professional Print cover branding, finding metadata, timestamps, action-plan proportions, and appendix treatment.

## [2.1.1] - 2026-09-06

### Added

* Central keyboard shortcut overview (`Ctrl+/` / `F1`) with searchable, categorized global and in-app shortcuts.
* Active pentest phase workflow with global phase hotkeys, header selection, automatic phase inheritance for new captures, and HUD confirmation.

### Changed

* Simplified the footer shortcut display to a compact shortcut-help action.

### Fixed

* Preserve snippet presets and unresolved placeholders when supplied template values are blank.
* Keep Obsidian loot-append deduplication accurate for one-shot iterables such as generators.

## [2.1.0] - 2026-09-05

### Added

* Centralized pentest phase taxonomy with normalized phase badges and legacy-value migration.
* Improved Loot Kanban cards with clearer styling, drag feedback, visible-column indicators, and scroll fades.

### Changed

* Reworked HUD and report surfaces around theme-aware simulated glass with consistent behavior across compositor configurations.
* Reduced UI orchestration coupling and separated clipboard persistence from Qt clipboard monitoring.
* Improved Kanban layout and scrolling behavior.

### Fixed

* Restored consistent flat styling outside the Kanban board and improved card contrast.
* Fixed narrow-card badge clipping, title truncation, wrapped content sizing, and glass-intensity behavior.
* Added missing Xorg pynput backends to the Debian bundle for global hotkeys on X11.

## [2.0.9] - 2026-09-04

### Added

* Multi-resolution Windows application icon.
* Double-click editing for Loot, Quick Notes, and Clipboard History.
* Dedicated Quick Note and History edit dialogs.
* Quick-Loot popup with global hotkey.
* Report text-alignment controls.
* Export-safe searchable QtAwesome report icon picker.

### Changed

* Report Editor toolbar can now collapse into a minimal restore bar.
* Standardized QtAwesome icons across major UI surfaces.

### Fixed

* Corrected Debian icon installation paths.
* Fixed click-outside closing for Quick Note, Quick IP, and Quick Loot popups.
* Improved PDF/print handling of long code blocks.
* Completed localization of previously hardcoded UI strings.

## [2.0.8] - 2026-09-04

### Added

* Quick Notes as a dedicated top-level workflow with global capture hotkey, pentest-phase tagging, triage states, pinning, filtering, bulk actions, inline editing, and Markdown-light rendering.
* Send Quick Notes directly to Loot or the active report.
* Quick-IP popup for Target IP and LHOST with live synchronization and auto-detection.
* History split-button for direct capture into Notes or Loot.

### Changed

* Harmonized global shortcuts around `Ctrl+Alt+...` combinations and automatically migrated legacy bindings.
* Streamlined the header bar with vector icons and reduced spacing.

## [2.0.7] - 2026-09-03

### Added

* Expanded Report Editor Markdown formatting controls.
* Direct insertion of external images and Loot screenshots.
* Bi-directional editor/preview scroll synchronization.
* Heading outline with jump-to-section navigation.
* Automatic crash-recovery draft snapshots.

### Changed

* Reorganized Report Editor controls into document and formatting toolbars.
* Improved destructive-action safety around report regeneration, including explicit confirmation and preservation of pending edits.

## [2.0.6] - 2026-09-03

### Added

* Five additional built-in themes: Blue Team, Catppuccin Mocha, Dracula, Gruvbox, and Tokyo Night.
* One-click copy buttons for common variables.
* Added Subnet, DNS Server, NTLM Hash, Hash, and Hash File variables.
* Expanded UI, code, and report font choices.

### Changed

* Moved Port into the Auth popover and further compacted the variable bar.
* Reduced visual emphasis of active variable badges.

## [2.0.5] - 2026-09-02

### Added

* X11 compositor awareness with graceful non-composited rendering.
* Responsive category pills with automatic overflow menu.
* Compact variable bar with Auth and Scope popovers.

### Fixed

* Fixed window border artifacts on non-composited X11.
* Improved report template contrast under GTK/light-theme environments.
* Removed unwanted Kanban card scrollbars while preserving scrolling.
* Centralized theme palette ownership and cleaned up screenshot overlay configuration.

## [2.0.4] - 2026-09-02

### Added

* Additive **Add Missing Loot** workflow that inserts new Loot into existing reports without rebuilding manual content.
* Stable internal Loot markers, backups, preview round-trip preservation, and marker-free exports.
* Linux desktop integration and cross-platform shortcut creation.
* Automated Debian package build and release pipeline.

### Changed

* Strengthened separation between headless core services and UI/platform integrations.

### Fixed

* Improved Wayland/unsupported-session fallback for screenshots and global hotkeys.
* Hardened POSIX filesystem handling and architecture boundaries.

## [2.0.3] - 2026-09-01

### Added

* Independent transparency controls for the HUD and Report Editor.
* Dedicated Fast and Full parallel test workflows.

### Changed

* Reorganized tests by responsibility and execution tier.
* Centralized application appearance and tooltip styling.

### Fixed

* Restored transparent HUD scroll-area rendering.
* Fixed tooltip colors in affected themed popup areas.

See the [full v2.0.3 release notes](docs/release_notes_v2.0.3.md).

## [2.0.2] - 2026-08-31

### Added

* HUD close button using the same transactional shutdown path as other quit actions.

### Changed

* Reordered main modes to Cheatsheet · History · Loot · Report.
* Font changes now apply immediately.
* Removed the redundant Loot presentation setting.

### Fixed

* Fixed unreadable light-theme tooltips and theme lists.
* Prevented late mouse-event crashes during theme restart.
* Restored transparent scroll-area rendering.
* Fixed stale Cheatsheet scroll geometry.
* Improved long Kanban Loot previews.
* Localized the Loot Markdown export tooltip.

## [2.0.1] - 2026-08-31

### Added

* Added Slate, Nord, Warm Night, High Contrast, Matrix Terminal, Red Team, Solarized, and Daylight themes.
* Persistent Kanban ordering, drag feedback, and direct Loot view switching.

### Changed

* Added a dedicated Appearance settings section.
* Theme changes now apply through a controlled restart.
* Consolidated report and Obsidian export coordination.
* Split major UI and project-persistence responsibilities into focused modules.

### Fixed

* Minimize-after-copy now applies consistently across supported views.
* Installed `spectrehud --help` and `--version` no longer bootstrap Qt.

## [2.0.0] - 2026-08-30

First documented public release, introducing the project-oriented workflow,
Report Editor V2, HTML/Obsidian/CherryTree exports, Pentest Mode,
single-instance protection, atomic persistence, and the English/German UI.

See the [full v2.0.0 release notes](docs/release_notes_v2.0.0.md).

Earlier repository tags predate the maintained changelog and are intentionally
not reconstructed without authoritative release notes.

[Unreleased]: https://github.com/m1thraz/SpectreHUD/compare/v2.1.3...HEAD
[2.1.3]: https://github.com/m1thraz/SpectreHUD/compare/v2.1.2...v2.1.3
[2.1.2]: https://github.com/m1thraz/SpectreHUD/compare/v2.1.1...v2.1.2
[2.1.1]: https://github.com/m1thraz/SpectreHUD/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.9...v2.1.0
[2.0.9]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.8...v2.0.9
[2.0.8]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.7...v2.0.8
[2.0.7]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.6...v2.0.7
[2.0.6]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.5...v2.0.6
[2.0.5]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.4...v2.0.5
[2.0.4]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.3...v2.0.4
[2.0.3]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.2...v2.0.3
[2.0.2]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/m1thraz/SpectreHUD/releases/tag/v2.0.0

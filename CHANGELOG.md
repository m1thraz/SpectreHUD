# Changelog

Notable user-facing changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use
semantic versioning.

## [Unreleased]

### Added

- **5 New Built-in HUD Themes**: Added popular dark community color schemes for enhanced
  personalization:
  - **Blue Team**: Cool defensive cobalt blue accents for blue teamers and SOC analysts.
  - **Catppuccin Mocha**: Soothing pastel dark palette with warm lavender and mauve accents.
  - **Dracula**: Classic high-contrast dark theme with vibrant purple, pink, and cyan highlights.
  - **Gruvbox**: Warm retro groove palette with earthy amber, green, and orange tones.
  - **Tokyo Night**: Clean modern neon cyberpunk dark palette celebrating downtown Tokyo vibes.
- **1-Click Circular Copy Buttons for Variable Inputs**: Added sleek circular vector
  copy-to-clipboard buttons inside Target IP, LHOST, and Popover input fields for
  instant 1-click clipboard copying with dynamic feedback, zero layout overhead, and bilingual tooltips (EN/DE).
- **Streamlined Variable Bar with Port in Auth Popover**: Relocated the Port field into the
  Auth Popover, further compacting the main cheatsheet header bar for narrow windows.
- **Expanded Typography Options**: Added curated UI, Code, and Report font stacks in Settings:
  - **App UI**: *IBM Plex Sans* (technical/industrial look) and *Manrope* (crisp semi-geometric dark-mode font).
  - **Code/Snippets**: *IBM Plex Mono*, *Iosevka* (condensed monospace allowing ~25% more characters per line in command snippets), and *Hack* (high-contrast terminal standard).
  - **Reports & Exports**: *Source Serif Pro* (executive report serif), *Lato* (clean agency standard sans), and *Cambria* (native print serif).

## [2.0.5] - 2026-09-02

### Added

- **Compositor Awareness for Linux X11**: Automatically detects if an X11 compositing
  manager is running (via `_NET_WM_CM_S0` atom or `SPECTREHUD_COMPOSITOR` environment
  variable) with graceful non-composited window adaptation.
- **Responsive Category Pills Bar**: Cheatsheet category filter buttons now dynamically
  adapt to the available window width. Exactly as many category buttons as fit are displayed
  horizontally, and the final button is an adaptive "More ▾" ("Mehr ▾") dropdown containing all
  remaining categories. In wide or maximized windows, all categories fit directly without an
  overflow button. Resizing is optimized with zero-thrashing threshold detection.
- **Hybrid Variable Bar with Auth & Scope Popovers**: Streamlined the top variable bar down
  from over 850px to a compact, responsive layout (~680px). Target IP, LHOST, and Port remain
  directly editable on the bar for instant live substitution, while credentials (Username,
  Password with visibility toggle, Domain, and NTLM Hash) and environment settings (Wordlist
  with file browser, Target URL) are conveniently accessible via sleek `[👤 Auth ▾]` and
  `[📁 Scope ▾]` popover flyouts with active state badges.

### Fixed

- **Window Borders on Non-Composited X11**: Fixed black rectangular outer margin and
  corner artifacts on systems without a compositor (e.g. Linux Mint / XFCE / MATE with
  compositing disabled) by dynamically turning off `WA_TranslucentBackground`, removing
  the 10px transparent margin, and applying clean square borders.
- **Report Template Dropdown Contrast**: Fixed unreadable template selection text in
  `ReportGenerationDialog` by adding explicit high-contrast item styles (`::item`, hover,
  and selection) and enforcing `QListView` viewport rendering against GTK light-theme conflicts.
- **Kanban Board Scrollbars on Overflowing Items**: Eliminated unsightly vertical scrollbars
  on individual Kanban columns and cards by enforcing `ScrollBarAlwaysOff` on column scroll
  areas, suppressing scrollbars via QSS, and bounding initial card content rendering. Mouse-wheel
  scrolling remains fully functional and smooth without horizontal card squeezing.
- **Theme Palette Single Source of Truth**: Unified internal theme tokens under
  `core.theme_palette` as the single canonical source of truth, eliminating maintenance drift.
- **Overlay Factory Encapsulation**: Exposed clean public registration API for overlay
  view factories, removing direct private state mutation.

## [2.0.4] - 2026-09-02

### Added

- Additive **"Add Missing Loot"** ("Aus Loot ergänzen") feature in the Report Editor
  that inserts newly captured loot entries into their matching report phase sections
  without modifying or rebuilding existing manual report text.
- Robust, canonical report marker infrastructure (`<!-- spectre:loot:{id}:{hash} -->`)
  with 12-character SHA-256 content hashes, strict byte preservation outside insertion
  points, code-fence isolation, and a single aggregated fallback section for unmatched
  categories (`## Neu aus Loot ergänzt`).
- Automatic backup protection (`report.md.bak`) and dirty-state auto-save protection
  before appending loot, with transactional fail-closed guarantees.
- Roundtrip reconciliation for editable rich live preview to preserve report markers
  across mode switches.
- Exporter marker stripping for HTML, Markdown copy, Obsidian, and CherryTree exports
  ensuring no internal sync markers are exposed in client-facing documents.
- Linux desktop integration assets including standard `resources/linux/spectrehud.desktop`,
  hicolor icons across 48x48, 128x128, 256x256, and scalable SVG, plus aligned
  `StartupWMClass` / `setDesktopFileName` application metadata.
- Cross-platform desktop shortcut generator (`create_desktop_shortcut.py`) creating `.lnk`
  on Windows and `.desktop` on Linux with standard execution permissions.
- Automated Debian package (`.deb`) build pipeline (`scripts/build_deb.py` and `scripts/pack_deb.py`)
  with native desktop/icon integration and automated release workflow in GitHub Actions.
- Pure Python domain services in `core/` for snippet search (`core/snippet_filter.py`), loot
  filtering (`core/loot_filter.py`), and navigation state (`core/navigation_state.py`).

### Changed

- Centralized core theme tokens (`core/theme_palette.py`) as the single source of truth,
  re-exported by `ui/styles/palette.py` to prevent theme token drift.
- Decoupled `ScreenshotManager` with injected `overlay_factory` and explicit public configuration
  API (`set_overlay_factory`), removing direct UI imports.
- Lazy Qt resolution in `core/platform/opener.py`, ensuring `core.platform` can be imported
  without eagerly loading PyQt6 modules into memory.

### Fixed

- Explicit desktop capability abstraction (`ScreenCaptureStatus`) and graceful degradation
  for screen capture under Wayland and unsupported sessions without UI crashes.
- Capability awareness and graceful fallback for global hotkeys (`HotkeyListener.is_available()`),
  ensuring application startup resilience under Wayland while keeping in-app Qt shortcuts operational.
- Comprehensive POSIX adversarial filesystem hardening covering case sensitivity, permission
  boundaries, symlink resolutions, and atomic write durability.
- Architecture guard invariants verifying that `core/` never imports `ui` and that `core.platform`
  does not eagerly load Qt.

## [2.0.3] - 2026-09-01

### Added

- Independent live transparency controls for the HUD and Report Editor. The
  established HUD glass appearance remains the default, while the Report
  Editor remains opaque by default.
- Dedicated parallel Fast and Full test commands with virtual-environment
  guards and a documented worker-isolation baseline.

### Changed

- Split the largest test modules by responsibility while preserving the exact
  386-test collection, and documented compact Fast/Full commands for coding
  agents.
- Centralized startup and runtime appearance application, including a
  theme-derived tooltip palette guard for popup labels inside locally styled
  scroll areas.
- Split test execution into Fast, Integration, and Release marker groups while
  keeping the unfiltered suite as the CI and release gate. Pytest output is now
  compact by default, and duplicate CLI subprocess coverage was removed.

### Fixed

- Restored the original transparent `MainScrollArea` glass rendering after the
  centralized scroll-area stylesheet change.
- Hardened theme-derived tooltip colors for popup labels inside locally styled
  scroll areas.

See the [full v2.0.3 release notes](docs/release_notes_v2.0.3.md).

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

[Unreleased]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.5...HEAD
[2.0.5]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.4...v2.0.5
[2.0.4]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.3...v2.0.4
[2.0.3]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.2...v2.0.3
[2.0.2]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/m1thraz/SpectreHUD/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/m1thraz/SpectreHUD/releases/tag/v2.0.0

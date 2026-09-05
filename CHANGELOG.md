# Changelog

Notable user-facing changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use
semantic versioning.

## [Unreleased]

## [2.1.0] - 2026-09-05

### Added

- **Centralized Pentest Phase Taxonomy & Standardized Badges**:
  - Single source of truth in `core/phases.py` for all 6 pentest phases (`RECON`, `ACCESS`, `PRIVESC`, `POSTEX`, `SCRIPTS`, `MISC`), including alias resolution and backward-compatible `CATEGORIES`.
  - Standardized phase badges across Loot and Quick Notes cards displaying short uppercase labels with full phase titles as tooltips.
  - Automatic normalization and migration for legacy phase strings and shorthand aliases in `LootMigrator` and `QuickNoteManager`.
- **Kanban Loot Board Card Styling & Tactile Drag**:
  - Elevated card appearance (`QFrame#lootCard`) with theme surface styling, rounded borders, and hover glow.
  - Tactile drag handle (`fa5s.grip-vertical`), responsive drag cursors (`OpenHand` / `ClosedHand`), and 60% drag opacity.
  - Dynamic visible column count indicator ("Spalte 1–3 von 6") and right-edge scroll fade.

### Changed

- Give simulated glass more depth with a four-stop diagonal gradient, a soft
  light reflection, and cached fine/coarse grain over the opaque background.
- Replace desktop translucency in the main HUD and report surfaces with opaque,
  theme-aware simulated glass (gradient, cached grain, and highlight edge).
  Rename appearance controls to glass intensity while retaining saved settings;
  the main window now uses the same layout with or without a compositor.
- Reduced UI orchestration coupling with registered mode renderers, container-only
  `MainWindow` construction, isolated shutdown and selection workflows, and smaller
  reporting/loot helpers without changing user-facing behavior.
- Separated headless clipboard history and persistence from the Qt system-clipboard
  monitor, preserving privacy defaults, capture behavior, and project-session storage.

### Fixed

- Prevent badge clipping (e.g. "TARC" instead of "TARGET") by computing dynamic badge
  minimum widths and gracefully truncating card titles with `ElidedLabel` (`…`).
- Make glass intensity control every effect layer: 0 disables the effect,
  while higher values progressively increase gradient, reflection and grain.
- Keep wrapped command cards tall enough for their full text after resizing,
  changing fonts, or substituting variables, including long SQL commands.
- Include pynput's dynamically loaded Xorg keyboard and mouse backends in the
  standalone Debian bundle so global hotkeys can start on X11.

## [2.0.9] - 2026-09-04

### Added

- **Multi-Resolution Windows Application Icon**:
  - Generated full multi-resolution `data/icon.ico` embedding 7 standard icon resolutions (`16x16`, `24x24`, `32x32`, `48x48`, `64x64`, `128x128`, `256x256`) directly from `icon.svg` so Windows Explorer, Desktop, Taskbar, and Alt+Tab render the custom icon crisply across all display scales.
- **Double-Click to Edit for Loot, Notes, and History**:
  - **Loot**: Double-clicking any loot card (including its title and text) opens `AddLootDialog` in edit mode directly.
  - **Quick Notes**: Double-clicking any note card (or clicking the edit button) opens the new `EditNoteDialog` to adjust text, pentest phase category, triage status, and target IP.
  - **Clipboard History**: Double-clicking any history card (or clicking the new `✎` edit button) opens the new `EditHistoryDialog` to adjust recorded commands/snippets and target IPs directly.
- **Dedicated History & Note Edit Dialogs**:
  - `EditHistoryDialog`: Clean modal HUD dialog with target IP and content editor, supporting `Ctrl+Enter` save and `Esc` cancel.
  - `EditNoteDialog`: Modal HUD dialog with phase category dropdown, triage status selector, target IP, and multi-line text editor.
  - Added `ClipboardWatcher.update_entry()` with automatic recalculation of lines count, char count, and multiline categorization.
- **Quick-Loot Popup & Global Hotkey**:
  - Global hotkey `Ctrl+Alt+L` and header trigger to capture findings and credentials via a lightweight non-modal dialog at the cursor position without disrupting the active window.
- **Report Text Alignment Controls**:
  - Added Left (`align-left`), Center (`align-center`), and Right (`align-right`) formatting buttons to the Report Editor toolbar for effortless block and text alignment.
- **Export-Robust QtAwesome Icons for Reports**:
  - Added a searchable, categorized picker with 28 report- and pentest-focused icons.
  - Icons are stored as reusable, theme-independent PNG assets and inserted as normal
    Markdown images, preserving Live Preview, HTML/Print, Obsidian, and CherryTree support.

### Changed

- **Full Report Toolbar Collapsing (Single-Button Hide)**:
  - Updated the Report Editor toolbar collapse action to collapse both Tier 1 (document actions/status) and Tier 2 (formatting tools) together into a minimal restore bar, maximizing writing space.
- **Header Navigation Bar Streamlining**:
  - Removed the thumbtack icon from the `Notes` tab button in `HeaderPanel` for a unified, typography-driven HUD navigation bar.
- Modernized the Report Editor toolbars with consistent QtAwesome icons for structural,
  insert, view, export, save, and collapse actions while retaining clear text labels and
  typographic Markdown controls where they are more readable.
- Replaced remaining emoji and Unicode action glyphs across the Variable Bar, Cheatsheet,
  Loot, Quick Notes, and History core views with consistent QtAwesome icons and state feedback.

### Fixed

- **Debian Package Icon Installation Paths**:
  - Corrected icon source search in `scripts/build_deb.py` to match the `/hicolor/<size>/apps/` structure, ensuring icons (48px, 128px, 256px, and scalable SVG) are cleanly copied into `/usr/share/icons/hicolor/...`.
- **Click-Outside-to-Close for Quick Popups (Quick Note, Quick IP, Quick Loot)**:
  - Fixed focus-stealing timer loop issue where forced foreground capture prevented windows from closing on background click.
  - Quick popups now gain initial keyboard focus once upon opening (`ActiveWindowFocusReason`) and close cleanly on focus loss.
- **PDF & Print Code Block Scroll Cutoff**:
  - Fixed issue where long, horizontally or vertically scrollable code blocks were cut off in PDF exports. Added print stylesheets (`@media print`) so code blocks wrap naturally without scrollbars and avoid awkward mid-block page breaks.
- **Comprehensive UI Internationalization (i18n)**:
  - Localized previously hardcoded strings in `ui/project_dialog.py` (including Pentest-Mode password unlock dialog), `ui/template_manager_dialog.py`, find/replace bar, and dialog alerts.
  - Enforced 100% key parity (582+ keys) across `de.json` and `en.json`.

## [2.0.8] - 2026-09-04

### Added

- **Quick-Notes ("Haftnotizen") & Dedicated Top-Level Tab**:
  - Global hotkey `Ctrl+Alt+N` and header `Note` button to quickly capture findings and fleeting thoughts in a minimal, frameless glass popup at cursor position without disrupting workflow.
  - **1-Key Pentest Phase Tagging**: Quick single-key tagging (`1`–`6` or `Alt+1..6`) for pentest categories (`Recon`, `Access`, `PrivEsc`, `PostEx`, `Scripts`, `Misc`) with memory of the last selected phase.
  - **First-Class Header Tab**: Promoted Quick Notes from a nested filter inside History to a dedicated top-level tab in the HUD header bar (`Notes` / `Notes (N)`) featuring real-time unread badge counts.
  - **1-Click Loot Promotion**: Each note card includes a `★ Promote` action that pre-fills `AddLootDialog` with title, category, target, and content, cleanly removing the note from the inbox once converted.
  - **Project Session Persistence**: Fully integrated into per-project storage (`project_state.json`), ensuring notes persist reliably across sessions and project switches without requiring migrations.
- **Quick Notes Pentest Workflow (Capture → Triage → Follow-up / Loot / Report)**:
  - **Triage Status Lifecycle**: Added structured note states (`inbox`, `followup`, `resolved`) with interactive color-coded status pills (`📥 Inbox ▾`, `⏳ Follow-up ▾`, `✓ Resolved ▾`) and subtle text dimming for completed entries.
  - **Priority Pinning & 3-Tier Sorting**: Notes can be pinned to the top (`fa5s.thumbtack`). Displayed notes use a stable 3-tier priority ordering: (1) Pinned notes, (2) Active/open notes (`inbox`, `followup`), (3) Resolved notes, maintaining newest-first order within each tier.
  - **Inline Card Editing**: Click "Edit" to edit note text directly in-place with `Ctrl+Enter` to save and `Esc` to cancel.
  - **"Send to ▾" (Loot & Report Promotion)**: Upgraded promote action into a dual-destination menu:
    - `★ Send to Loot`: Opens `AddLootDialog` pre-filled with note details and deletes the note from the inbox upon acceptance.
    - `📝 Send to Report`: Directly appends the note as a structured Markdown block (`### Note (<PHASE>) - [<IP>] (<TIMESTAMP>)`) to the active project report and automatically marks it as `resolved`.
  - **Status & Phase Filtering**: Filter bar provides triage pills (`All`, `Inbox`, `Follow-up`, `Resolved`, `📌 Pinned`) and a dedicated phase dropdown (`Phase: All ▾`).
  - **Multi-Field Spotlight Search**: Search matches note content, pentest phase, target IP, and triage status simultaneously.
  - **Bulk Triage Bar**: Multi-select checkboxes on cards summon a Cyberpunk HUD bulk action bar to mark statuses, delete notes in bulk with safety confirmation, or deselect all.
  - **Native Markdown-Light Rendering**: Notes display Markdown formatting (bold, code, lists, headings) cleanly in cards without extra dependencies.
- **Quick-IP Popup (Target + LHOST)**:
  - Global hotkey `Ctrl+Alt+I` opens a minimal, frameless glass popup at cursor position to inspect, copy, or edit Target IP and LHOST without needing to focus the HUD.
  - Features embedded 1-click circular copy buttons (`CopyableLineEdit`) and an "Auto" button that runs `NetDetector.detect_attacker_ip()` with instant live visual feedback.
  - Edits synchronize live on every keystroke with `VariableBar`, immediately updating cheatsheet placeholders and scheduling project autosave without requiring a manual save or confirm step.
  - Closes cleanly via `Esc` or clicking outside (focus loss).
- **"Erfassen ▾" Split-Button on History Cards**:
  - Replaced the previous `+ Loot` button with a multi-action split-button.
  - **Direct Capture**: 1-click on the primary button instantly saves clipboard history entries directly into the Quick Notes inbox with tactical visual confirmation (`✓ Note!`).
  - **Dropdown Menu**: Arrow dropdown allows explicit selection between "Als Note erfassen" and opening `AddLootDialog` ("Als Loot erfassen...").
  - Smart category resolution infers `access` for shell/command entries and `recon` otherwise, prioritizing the user's active quick-note phase.

### Changed

- **Harmonized Global Keyboard Shortcuts**:
  - Overhauled default system hotkeys to eliminate collisions with operating systems, desktop window managers, and browsers:
    - **Toggle Overlay**: `Ctrl + Alt + H` (replaces `Ctrl + Super + <`)
    - **Screenshot Snip**: `Ctrl + Alt + X` (replaces `Ctrl + Super + X`)
    - **Quick-Note Capture**: `Ctrl + Alt + N` (replaces `Ctrl + Super + N`)
    - **Quick-IP Popup**: `Ctrl + Alt + I` (new global hotkey)
    - **Quit Application**: `Ctrl + Alt + Q` (replaces `Ctrl + Super + Q`)
  - Added automatic configuration migration on startup to silently upgrade legacy config files.
  - Updated in-app Settings dialog presets, footer hints, and system tray menu shortcuts.
- **Header Bar Vector Icon System & Visual Compactness**:
  - Replaced platform-inconsistent Unicode emoji (`⚙`, `🚩`) on Header bar buttons with crisp vector FontAwesome icons (`fa5s.cog`, `fa5s.sticky-note`).
  - Eliminated redundant padding between `QFrame#HeaderBar` stylesheet rules and `HeaderPanel` layout margins, reducing unnecessary vertical whitespace.
  - Compacted mode switch button padding from `4px 10px` to `3px 10px` for a unified, streamlined Cyberpunk HUD aesthetic.

## [2.0.7] - 2026-09-03

### Added

- **Enhanced Report Markdown Toolbar**: Added formatting buttons and keyboard shortcuts
  for Blockquotes (`> ` / `Ctrl+Shift+Q`), Strikethrough (`~~Text~~` / `Ctrl+Shift+X`),
  Horizontal Rules (`---`), and Headings `H4`-`H6`, with compact toolbar styling
  and bilingual tooltips (EN/DE).
- **Direct Image & Loot Screenshot Insert in Report Editor**: Added `🖼️` toolbar button
  and `Ctrl+Shift+I` shortcut to insert images directly into report Markdown.
  Features a quick-access menu displaying recent Loot screenshots for 1-click insertion,
  a searchable `LootImagePickerDialog` with live preview to pick individual screenshots
  without regenerating or appending all loot, and automatic import of external images
  into the project's `screenshots/` directory.
- **Bi-directional Scroll-Sync in Split View**: Synchronized scrolling between the Markdown editor
  and live preview in Split View mode with smooth proportional alignment and feedback-loop guards.
- **Hierarchical Heading Outline & Jump-to-Section Navigation**: Added `[ 📑 Sections ▾ ]` (`[ 📑 Gliederung ▾ ]`)
  dropdown on Tier 1 and `Ctrl+Shift+O` shortcut to dynamically parse document headings (H1–H6, excluding code blocks)
  and jump directly to any section with synchronized preview alignment.
- **Real-Time Crash Recovery & Draft Snapshots**: Background engine saves atomic `.report.md.draft`
  snapshots every 5 seconds while typing unsaved notes. Automatically cleans up on normal save/discard
  and presents an instant restore prompt on startup if an unsaved draft is detected following a crash
  or unexpected shutdown.

### Changed

- **Two-Tier Report Toolbar Layout**:
  - **Tier 1 (Document Actions & Status)**: Houses document-level controls (`View ▾`, `Add Missing Loot`, `Regenerate`, `Export ▾`) on the left, and the localized project status indicator (`<project> — ✓ Saved · [Split]`) right-aligned on the same row.
  - **Tier 2 (Formatting Tools)**: Cleanly dedicated row for structure (`H ▾` Dropdown, `❝`, `•`, `1.`, `―`), inline styling (`B`, `I`, `S̶`, `</>`, `>_`), and inserts (`🖼️`, `🔗`, `▦`) with visible vertical dividers and rounded hit-boxes.
  - **Toolbar Minimize / Expand Toggle**: Added a compact `▲` / `▼` toggle button on the far right of Tier 2 (directly underneath the status label) allowing users to collapse the formatting tools for an unobstructed view of their notes.
  - **Compact Icon-Save on Tier 1**: Added a compact, discrete diskette icon button (`💾`) right next to the status label on Tier 1, preserving explicit manual save capability with tactical tactile feedback without cluttering the interface with a bulky button.
- **Full Status Label Localization (i18n)**: Fully localized report save states (`✓ Saved` / `✓ Gespeichert`, `● Unsaved changes` / `● Ungespeicherte Änderungen`) and view mode badges across languages.
- **Destructive Action Safety**:
  - Permanently styled `Regenerate` button with red danger accent (`color: {TEXT_REC}; border: 1px solid {ERROR_A70}`)
    to clearly signal its destructive nature against the neutral `Add Missing Loot` button.
  - Added an explicit overwrite confirmation dialog with "No" as default before regenerating existing reports.
  - Automatically saves pending editor edits before regeneration so that automatic backups (`report.md.bak`)
    reliably capture the user's latest manual work.

## [2.0.6] - 2026-09-03

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
- **Subnet, DNS Server & Unified Hash/File Variables**: Added dedicated persistent inputs
  for `{{SUBNET}}` and `{{DNS_SERVER}}` inside the Scope Popover, and unified `{{NTLM_HASH}}`,
  `{{HASH}}`, and `{{HASH_FILE}}` inside the Auth Popover with 1-click circular copy buttons,
  smart auto-resolution, and parameter prompt fallback.
- **Expanded Typography Options**: Added curated UI, Code, and Report font stacks in Settings:
  - **App UI**: *IBM Plex Sans* (technical/industrial look) and *Manrope* (crisp semi-geometric dark-mode font).
  - **Code/Snippets**: *IBM Plex Mono*, *Iosevka* (condensed monospace allowing ~25% more characters per line in command snippets), and *Hack* (high-contrast terminal standard).
  - **Reports & Exports**: *Source Serif Pro* (executive report serif), *Lato* (clean agency standard sans), and *Cambria* (native print serif).

### Changed

- **Streamlined Variable Bar with Port in Auth Popover**: Relocated the Port field into the
  Auth Popover, further compacting the main cheatsheet header bar for narrow windows.
- **Subtle Active Badge Button Styling**: Calmed `VarBadgeBtnActive` styling so active popover
  badge buttons (e.g., `[👤 admin ▾]`) match the non-intrusive border and background of default
  badge buttons, removing distracting neon focus outlines.

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

[Unreleased]: https://github.com/m1thraz/SpectreHUD/compare/v2.1.0...HEAD
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

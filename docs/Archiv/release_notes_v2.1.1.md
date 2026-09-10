# SpectreHUD v2.1.1 – Release Notes

SpectreHUD v2.1.1 improves shortcut discovery and phase-aware capture workflows while
fixing two edge cases in snippet interpolation and Obsidian loot export.

---

## Highlights

### Central Shortcut Overview

- Open the searchable shortcut overview with `Ctrl+/` or `F1`.
- Browse global and in-app shortcuts grouped by workflow area.
- Distinguish system-wide shortcuts from in-app bindings at a glance.
- Use the compact footer action instead of a permanently expanded shortcut list.

### Active Pentest Phase Workflow

- Select the active pentest phase from the application header.
- Switch phases globally with `Ctrl+Alt+1` through `Ctrl+Alt+6`.
- Automatically apply the active phase to new Quick Loot, Quick Notes, and Clipboard
  History captures.
- Receive a lightweight HUD confirmation when the phase changes in the background.

### Reliability Fixes

- Blank snippet variables now preserve their configured presets or visible unresolved
  placeholders instead of rendering as empty text.
- Obsidian loot append now reports skipped entry IDs correctly when entries are supplied
  through a one-shot iterable such as a generator.

---

## Compatibility and Upgrade

- Python 3.10 through 3.13.
- Fully compatible with existing SpectreHUD v2.1.0 project directories, settings,
  snippets, reports, and export destinations.
- No data or configuration migration is required.

# SpectreHUD v2.0.1 – Release Notes

SpectreHUD v2.0.1 is a usability and maintenance update. It keeps the v2.0.0
project format and focuses on a more interactive Loot workflow, broader visual
customisation, smaller quality-of-life improvements, and targeted bug fixes.

## Highlights

### Interactive Kanban Loot Board

- Loot cards can be moved between pentest-phase columns and reordered within a
  column.
- Card positions are persisted and restored when the project is loaded again.
- Dragged cards now use a visible preview, reduced source opacity, and an active
  target-column highlight.
- A compact Loot action toggles directly between the classic list and Kanban
  views without opening Settings.

### Theme Manager and Appearance Settings

- Built-in themes now include Cyber Dark, Slate, Nord, Warm Night, High
  Contrast, Matrix Terminal, Red Team, Solarized, and Daylight.
- Themes, application/code/report fonts, and the Loot presentation have moved
  into a dedicated **Appearance / Aussehen** settings tab.
- Saving a different theme performs a controlled application restart after the
  current project state is safely persisted and the single-instance lock is
  released.
- Custom JSON themes remain discoverable through the user theme directory.

### UI and Quality-of-Life Changes

- Report exports are grouped behind one export action and chooser.
- Obsidian report and Loot export orchestration is consolidated.
- The optional minimize-after-copy setting now applies consistently to
  Cheatsheet, Loot, Kanban, and History copies.
- The classic Loot list remains the default presentation for new configurations.
- Contributor, security-reporting, issue, pull-request, and dependency-update
  infrastructure is now included in the repository.

## Bug Fixes and Reliability

- Fixed the previously disconnected minimize-after-copy option.
- Preserved transactional persistence when Kanban ordering is changed; failed
  writes do not commit a new in-memory order.
- Kept the theme restart on the normal dirty-report and project-save shutdown
  path instead of bypassing lifecycle checks.
- Updated wheel verification so every built-in theme must be present in release
  artifacts.
- Made the installed `spectrehud --help` and `--version` commands independent
  from Qt and the full GUI bootstrap.

## Compatibility and Upgrade

- Python 3.10 through 3.13
- Windows and Linux
- No project-state or Pentest-Mode migration is required from v2.0.0

Close any running SpectreHUD instance before replacing the executable. Existing
projects can be opened without conversion. As before, creating a project archive
before a release upgrade is recommended for important engagement data.

For the complete change history, see the repository [changelog](../CHANGELOG.md).

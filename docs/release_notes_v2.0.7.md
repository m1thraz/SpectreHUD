# SpectreHUD v2.0.7 – Release Notes

SpectreHUD v2.0.7 is a major usability and resilience release for the Report Editor,
bringing two-tier toolbar organization, bi-directional scroll synchronization in Split View,
hierarchical heading outline navigation, real-time crash recovery snapshots, and 1-click
loot image insertion.

## Highlights

### Two-Tier Report Toolbar & Minimization

- **Tier 1 (Document Actions & Status)**: Compact top row housing document-level actions
  (`View ▾`, `Sections ▾`, `Add Missing Loot`, `Regenerate`, `Export ▾`), project status
  (`<project> — ✓ Saved · [Split]`), and a discreet diskette icon save button (`💾`).
- **Tier 2 (Formatting Tools)**: Cleanly dedicated row for structure (`H ▾` Dropdown, `❝`, `•`, `1.`, `―`),
  inline styling (`B`, `I`, `S̶`, `</>`, `>_`), and inserts (`🖼️`, `🔗`, `▦`) with visible vertical dividers.
- **Collapsible Toggle**: Added a compact `▲` / `▼` button on the far right of Tier 2 to
  fold away formatting tools for an unobstructed view of notes.

### Bi-directional Scroll Synchronization

- Proportional, real-time scroll sync between the Markdown source editor and rendered live preview
  in Split View (`ViewMode.SPLIT`).
- Recursion protection guard prevents feedback loops and eliminates scrollbar jitter.
- Maintains relative scroll alignment when switching view modes or re-rendering markdown.

### Hierarchical Heading Outline Navigation (`[ 📑 Sections ▾ ]`)

- Dynamic outline dropdown (`Ctrl+Shift+O`) that extracts document headings (`H1`–`H6`) while
  strictly ignoring `#` comments inside fenced code blocks.
- One-click navigation positions the cursor at the target section and glides both editor
  and preview panes into place synchronously.

### Real-Time Crash Recovery & Draft Snapshots

- Background engine writes atomic `.report.md.draft` snapshots every 5 seconds when unsaved
  edits are in flight.
- Automatically cleans up draft snapshots upon successful save (`Ctrl+S`, `[ 💾 ]`) or discard.
- Shows an instant recovery prompt on project startup if an uncommitted draft is detected
  following an unexpected shutdown, crash, or power loss.

### Direct Image & Loot Screenshot Insert (`🖼️`)

- Direct image insertion into the report editor via toolbar button and `Ctrl+Shift+I`.
- Quick-access menu displaying recent Loot screenshots for instant 1-click markdown insertion (`![](screenshots/...)`).
- Searchable dialog with thumbnail preview to select specific screenshots without regenerating or appending all loot.
- Automatic copy and relative path resolution for external image files.

### Safety & UX Polish

- **Destructive Action Safeguards**: Permanently highlighted `Regenerate` button with red danger accent
  and explicit overwrite confirmation dialog with "No" default.
- Automatically saves pending editor edits before regeneration so backups (`report.md.bak`) reliably capture manual work.
- Full bilingual localization (English & German) across report status badges, view labels, and dialogs.

## Compatibility and upgrade

- Python 3.10 through 3.13
- Fully backwards compatible with existing SpectreHUD project directories and reports.

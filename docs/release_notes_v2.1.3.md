# SpectreHUD v2.1.3 – Release Notes

SpectreHUD v2.1.3 is a focused usability and visual-consistency update for the
Report Editor, Quick Notes, and application dialogs.

---

## Highlights

### Safer Report Editing and Export

- Spectre metadata markers are hidden by default in the Report Editor, protecting
  synchronization structure from accidental edits while retaining an explicit control
  for advanced users who need to inspect or modify them.
- Report exports now lead with HTML/PDF, offer Professional Print before the editable
  Classic Web version, and place Markdown export last.
- Professional Print HTML is editable in the browser and can save an edited standalone
  copy while retaining its controlled A4 presentation.
- Generated Markdown and HTML reports use export-safe text severity labels instead of
  platform-dependent emoji badges.

### Quick Notes Corrections

- Focus Review supports direct inline text editing while retaining the full details
  dialog for phase, target, and status changes.
- Completing a review pass shows a clear notice and restarts at the first unfinished
  note instead of leaving an empty view.
- Regular Note cards continue to open the full edit dialog on double-click; inline
  editing remains exclusive to Focus Review.

### Theme and Dialog Consistency

- Report generation and template management now use SpectreHUD's frameless dialog
  chrome instead of native light Windows title bars.
- Header actions and default QtAwesome icons inherit the active theme palette.
- The Shortcut Help dialog now derives its complete color treatment from the active
  application theme rather than hard-coded Cyber Dark colors.

### Reliability

- Delayed Quick-IP and snippet-copy feedback is cancelled when its widget closes,
  preventing stale Qt callbacks from accessing deleted controls.

---

## Compatibility and Upgrade

- Python 3.10 through 3.13.
- Compatible with existing SpectreHUD v2.1.2 projects, reports, templates, snippets,
  Loot, Quick Notes, and settings.
- No project, report, or configuration migration is required.
- Existing report marker, Loot hash, synchronization, Obsidian, and CherryTree
  contracts remain unchanged.

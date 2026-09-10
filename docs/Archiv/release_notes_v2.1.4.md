# SpectreHUD v2.1.4 – Release Notes

SpectreHUD v2.1.4 improves Report Editor navigation, capture controls, update
visibility, and the consistency of frameless dialogs.

---

## Highlights

### Report Navigation and Theme Integration

- A compact semantic Report Navigator jumps directly to marked sections and
  findings while preserving the existing Markdown editing workflow.
- The former heading-based Sections dropdown was removed because the semantic
  navigator now covers both sections and findings.
- Report toolbar icons inherit the active theme accent instead of retaining the
  Cyber Dark cyan color.

### Faster Capture Controls

- `Ctrl+Alt+R` now pauses or resumes clipboard recording system-wide and shows
  brief state feedback on the monitor containing the mouse pointer.
- The shortcut overview now presents Quick Capture & Controls before phase
  switching, making the most frequently used actions easier to find.

### Manual Update Checks

- Settings includes a non-blocking **Check for Updates** action backed by the
  latest stable GitHub release.
- Versions are compared semantically, pre-releases and drafts are rejected, and
  available Windows `.exe` or Linux `.deb` assets are detected without starting
  downloads or installations automatically.
- When an update exists, SpectreHUD offers the official GitHub release page.

### Dialog and Desktop Reliability

- Report generation, template management, template editing, section editing,
  and destructive regeneration confirmation now share the opaque frameless HUD
  dialog shell. Parent report content no longer shows through these windows.
- Frameless resize cursors reliably return to their neutral state after leaving
  a resize edge.
- Add Missing Loot uses the active template language when it must create the
  fallback section.

---

## Compatibility and Upgrade

- Python 3.10 through 3.13.
- Compatible with existing SpectreHUD v2.1.3 projects, reports, templates,
  snippets, Loot, Quick Notes, and settings.
- No project, report, or configuration migration is required.
- Report section/finding/Loot markers, content hashes, additive synchronization,
  recommendations, Obsidian, and CherryTree contracts remain unchanged.
- Update checks are manual and read-only; SpectreHUD does not automatically
  download or install releases.

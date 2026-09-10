# SpectreHUD v2.1.5 – Release Notes

SpectreHUD v2.1.5 strengthens local project persistence, makes failures easier
to diagnose, improves workflow guidance, and reduces the delay when returning to
the Cheatsheet.

---

## Highlights

### Safer Project Persistence

- Project-session writes now return typed outcomes and load Loot, clipboard
  history, Quick Notes, and phase state as one validated transaction.
- Corrupted, unreadable, oversized, or unsupported project state is reported
  explicitly instead of being mistaken for a missing or empty session.
- Versionless valid project and Pentest-security state is migrated to schema 1
  with an exact backup of the pre-migration file.
- Failed project creation rolls back only files created by SpectreHUD and keeps
  pre-existing user content intact.
- Atomic replacement now also synchronizes the parent directory for stronger
  crash durability on filesystems that require it.

### Actionable Diagnostics

- Runtime logs now live in the machine-local SpectreHUD Diagnostics directory;
  Settings can open that directory or copy the active log path.
- `SPECTRE_LOG_DIR` remains available as an explicit override for portable or
  managed installations.
- Standard error dialogs provide selectable, copyable diagnostics including
  technical details and the active log location.
- Warning, information, and confirmation dialogs now share one consistent UI
  boundary while specialized multi-action prompts retain their workflow-specific
  behavior.

### Faster, Clearer Workflows

- Returning to an unchanged Cheatsheet reuses its rendered cards, while initial
  construction is performed incrementally to reduce perceived blocking.
- Context-aware empty states and tooltips explain capture, phase, report, and
  export actions more directly in English and German.
- History's Markdown action is identified as draft generation rather than an
  export of the editable report.
- New screenshot Loot inherits the active Pentest phase instead of falling back
  to Misc.

### Reliability Fixes

- Frameless header navigation remains clickable where it overlaps the top resize
  region.
- The test runner's simulated Windows process-group configuration works on Linux
  CI hosts.

---

## Compatibility and Upgrade

- Python 3.10 through 3.13.
- Existing valid SpectreHUD v2.1.4 projects, reports, templates, snippets, Loot,
  Quick Notes, and settings remain supported.
- Versionless valid project-state and Pentest-security files are backed up and
  upgraded to schema 1 when loaded; unsupported future schemas are rejected with
  an actionable error instead of being overwritten.
- Report section/finding/Loot markers, hashes, additive synchronization,
  Recommendations, Obsidian, and CherryTree contracts remain unchanged.

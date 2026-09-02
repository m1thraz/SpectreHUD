# SpectreHUD v2.0.4 – Release Notes

SpectreHUD v2.0.4 extends the Linux baseline, adds non-destructive report
synchronization from Loot, and completes a focused architecture-maintenance
round. Existing v2.0.x projects, registries, templates, custom themes, and
Pentest Mode data remain compatible.

## Highlights

### Add missing Loot without rebuilding a report

- The Report Editor can append newly captured Loot to the matching report
  sections without replacing manually edited report content.
- Canonical internal markers identify synchronized entries and detect unchanged,
  stale, missing, and orphaned report references deterministically.
- Existing report content is backed up before synchronization, and dirty editor
  state is saved before the operation proceeds.
- Failed backup or save operations remain fail-closed and do not report a false
  success.
- Internal synchronization markers are removed from HTML, Markdown, Obsidian,
  and CherryTree exports.

### Linux platform baseline

- Central platform modules now own XDG-aware config/data/cache paths, local
  file and directory opening, Linux network-interface discovery, and desktop
  capability detection.
- Linux network discovery parses `ip -j -4 addr`, prioritizes common VPN
  interfaces, and degrades to generic fallbacks when the command or output is
  unavailable.
- Screenshot capture and global hotkeys degrade gracefully in restricted
  Wayland or headless sessions while local Qt shortcuts remain available.
- The wheel includes a Linux desktop entry and hicolor icons, and the shortcut
  helper can create Linux `.desktop` launchers.
- CI includes an Ubuntu wheel gate that installs the built artifact into a fresh
  environment outside the repository and checks `spectrehud --version` and
  `spectrehud --help`.

Real X11 and Wayland desktop acceptance remains tracked separately in the
[Linux platform audit](linux_platform_audit.md); automated capability tests do
not substitute for compositor-specific manual verification.

### Architecture and maintenance

- Runtime settings, report exports, and screenshot transactions are routed
  through focused coordinators and services without changing user workflows.
- Core theme tokens, snippet filtering, screenshot overlay creation, and the
  platform opener were decoupled from eager UI/Qt imports; architecture tests
  enforce the resulting dependency direction.
- POSIX coverage exercises case-sensitive paths, permissions, symlinks, and
  atomic-write failure behavior.
- The tiered Fast/Full testing workflow keeps release tests in the packaging
  gate while retaining the complete suite as the final safety net.
- Theme selectors display concise theme names without redundant author labels.
- Cheatsheet cards keep Copy and Edit actions visible even when commands are
  unusually long.
- Windows Qt appearance tests avoid the native teardown race that previously
  caused an access violation in CI.

## Compatibility and upgrade

- Python 3.10 through 3.13
- Windows and Linux
- No project-state, registry, report-template, custom-theme, or Pentest Mode
  migration is required from earlier v2.0.x releases.

Close a running SpectreHUD instance before replacing the executable. Existing
projects, reports, templates, and themes can be reused without conversion.

For the complete change history, see the repository [changelog](../CHANGELOG.md).

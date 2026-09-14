# SpectreHUD v2.1.6 – Release Notes

SpectreHUD v2.1.6 introduces the Modular Report Workspace, bringing an interactive
tri-pane report authoring environment with live Markdown synchronization, dedicated
section and finding inspectors, responsive view reflow, clipboard history curation,
and theme-dependent frameless export dialogs.

---

## Highlights

### Modular Report Workspace

- **Tri-Pane Environment**: Combines a semantic Report Navigator, structured
  section/finding inspectors, and live Markdown preview with free-form splitter
  resizing across Editor, Split, and Workspace view modes.
- **Dedicated Cockpits**:
  - *Assessment Metadata & Scope*: Client, tester, target, classification, and date properties.
  - *Executive Summary*: Real-time posture scorecards, severity breakdown pills, and dynamic finding matrix.
  - *Scope & Methodology*: In-scope/out-of-scope targets and assessment limitations with high-contrast themed dark inputs.
  - *Attack Path*: Narrative attack chain modeling with step sequencing and visual path representation.
  - *Technical Findings*: Hierarchical findings management with one-click Loot conversion, severity badges, and phase attribution.
  - *Remediation Plan*: Action item prioritization and owner assignments.
  - *Appendix & Evidence*: Curated terminal history commands and screenshot evidence cards.
  - *Raw Markdown*: Direct bidirectional Markdown editing synchronized live with the workspace document model.
- **Responsive Layout Reflow**: Cockpit layouts dynamically adapt to narrow split
  views (260px - 450px) and intermediate widths, preventing truncation and wrapping form controls cleanly.
- **Default-Collapsed Navigator**: Findings categories start collapsed to reduce
  clutter on large assessments, with smart auto-expansion when navigating to or selecting an entry.
- **Theme-Aware Navigation**: Navigator section icons dynamically inherit active theme
  accent palettes (e.g. Dracula violet, Matrix green, Red Team crimson).

### Curated Clipboard History for Reports

- Individual terminal snippets can now be marked (`[x] Report`) directly from
  the History stream or card context menu.
- Report generation (Appendix A: Terminal Command History) selectively includes only
  curated commands, keeping noise and transient shell commands out of the final deliverable.
- Clean placeholder feedback (`*Keine Befehle für den Report ausgewählt.*`) when no
  commands have been flagged for inclusion.
- Streamlined History filter pill and Clipboard History Picker dialog support.

### Themed Frameless Export Dialog

- `ReportExportTypeDialog` migrated to a frameless `BaseHudDialog` featuring custom
  header dragging, HUD glowing frames, and interactive option cards for HTML/PDF presentation,
  Obsidian Vault, CherryTree package, and Raw Markdown exports.
- Seamless design token integration across all 14 built-in SpectreHUD themes.

### Security, CI/CD & Build Hardening

- Pinned all GitHub Actions across workflows to immutable 40-character commit SHAs
  with human-readable version annotations.
- Enforced bit-deterministic wheel builds across CI and release workflows via
  `--no-build-isolation` against pinned `setuptools` and `wheel` build backend constraints.
- Automated fallback to serial test execution in `scripts/run_tests.py` when `pytest-xdist`
  is absent from the local environment.
- Consolidated code security scanning onto native GitHub CodeQL analysis.

---

## Compatibility and Upgrade

- Python 3.10 through 3.13.
- Existing valid SpectreHUD v2.1.5 projects, reports, templates, snippets, Loot,
  Quick Notes, and settings remain fully supported.
- Report section/finding/Loot markers, hashes, additive synchronization,
  Recommendations, Obsidian, and CherryTree contracts remain unchanged.

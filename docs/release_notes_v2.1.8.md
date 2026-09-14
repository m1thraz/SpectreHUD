# SpectreHUD v2.1.8 – Release Notes

SpectreHUD v2.1.8 refines the Report Workspace and Loot-to-Finding workflow,
enhances cross-theme styling consistency across widgets and dialogs, introduces
granular Loot reconciliation for findings and evidence, and resolves visual and
metadata contrast issues in report preview and appendix inspectors.

---

## Highlights

### Enhanced Loot-to-Finding Workflow & Enriched Loot Capture

- **Explicit Loot-to-Finding Transition:** Transform Loot items directly into structured
  report findings while bundling supporting Loot entries as linked evidence.
- **Enriched Loot Properties:** Added CVSS score, vector calculation, finding status,
  references, and multi-target associations directly in the session Loot capture dialog.
- **Evidence Provenance Preservation:** CVSS scores, targets, and metadata provenance
  remain intact when converting Loot into findings.

### Granular Loot & Finding Reconciliation

- **Smart Difference Review:** Live comparison distinguishes new, modified, and
  report-only entries with clear status indicators.
- **Actionable Conflict Resolution:** Provides granular, non-destructive resolution
  choices for every changed item (keep report version, update from Loot, preserve both,
  detach, or delete).

### Theme & Styling Harmonization

- **Appendix & Form Field Readability:** Unified text fields and code editors across the
  Appendix Inspector to use standard themed `CommandBox` styling, eliminating contrast
  blowouts and unreadable text across built-in themes.
- **Independent Workspace Sidebar Styling:** The workspace navigation sidebar and toolbars
  now retain their theme-governed cyber-HUD aesthetics regardless of whether the document
  editor/preview is toggled into light mode.
- **Universal Palette Safety:** Added fallback resolution for background tokens, ensuring
  custom and legacy HUD popups maintain solid contrast without color leaks.

### Workspace & Live Preview Polish

- **Clean Metadata Display:** Evidence metadata tags (`<!-- spectre:evidence:... -->`) are
  hidden from plain-text inspector descriptions during editing and cleanly reconciled upon save.
- **Live Preview Typography:** Improved heading spacing and block margins between findings
  and sections in the live preview document.
- **Removed Degrading Opacity:** Eliminated fading opacity on quick notes and clipboard cards
  for clearer readability.

---

## Compatibility and Upgrade

- Python 3.10 through 3.13 supported.
- Fully backward compatible with existing SpectreHUD v2.1.7 and earlier project databases,
  reports, Loot collections, and templates.
- No project or storage migration required.
- Primary production platform is Windows 10/11; Linux X11 verified.

# SpectreHUD v2.1.2 – Release Notes

SpectreHUD v2.1.2 delivers a redesigned Quick Notes workflow and a complete
professional-reporting pass while keeping existing projects, edited reports, and
external export workflows compatible.

---

## Highlights

### Professional Reports

- Choose between the existing editable Interactive HTML export and a dedicated
  Professional Print profile.
- Preserve report-section and finding identity through internal markers while keeping
  exported HTML, Obsidian, and CherryTree documents marker-free.
- Continue using the manually editable `report.md` as the sole report source of truth;
  Professional Print never regenerates or rewrites it during export.
- Generate assessment-oriented Pentest reports and intentionally chronological CTF
  walkthroughs from distinct built-in template narratives.
- Render findings with structured severity, target, phase, observation time,
  description, and optional recommendation metadata without inventing unavailable
  fields.
- Aggregate only real finding recommendations into a priority-sorted Remediation &
  Action Plan.
- Suppress semantically empty Professional sections while preserving manual notes and
  other user-authored content.

### Print-Ready Presentation

- Use a restrained A4 cover, semantic section styling, compact finding metadata, and
  print-stable Findings Matrix and Action Plan tables.
- Keep short findings together where possible, repeat table headers, protect rows and
  headings from poor breaks, wrap long commands, and respect explicit page-break
  markers.
- Add subtle report-name, classification, and page-number furniture for compatible
  browser print engines while isolating the cover page.
- Reduce generator branding to a small `SpectreHUD` cover tag and omit duplicate body
  signatures in Professional output.
- Insert bounded report spacers and visible live-preview page-break indicators from the
  Report Editor toolbar.
- Toggle the Report Editor and preview panes between local dark and light appearances
  without changing the rest of the application theme.

### Quick Notes and Core Views

- Work through Quick Notes as a chronological, age-aware stream with simplified rows,
  contextual actions, completion undo, and explicit bulk selection.
- Review notes one at a time in the optional focus workflow without changing their
  persisted content or status model.
- Collapse the Variable Bar and Report toolbar to their small restore controls so the
  hidden surfaces no longer reserve unused space.
- Continue the QtAwesome-based icon and card cleanup across frequently used capture and
  history surfaces for more consistent Windows and Linux rendering.

### Compatibility and Reliability

- Existing reports without semantic section markers remain fully exportable and are
  never silently migrated.
- Add Missing Loot remains additive and idempotent; manual report edits, Loot hashes,
  and existing marker contracts retain priority.
- Existing Loot entries load without a recommendation, while populated recommendations
  persist and participate in change detection.
- Browser-native print headers and footers remain controlled by the browser print
  dialog; Professional exports provide a concise reminder to disable them for clean
  PDFs.

---

## Compatibility and Upgrade

- Python 3.10 through 3.13.
- Compatible with existing SpectreHUD v2.1.1 projects, settings, snippets, Loot,
  Quick Notes, and reports.
- No project, report, or configuration migration is required.
- Existing manually edited reports retain their current structure; the revised finding
  and template layouts apply only to newly generated or explicitly regenerated reports.

# SpectreHUD v2.1.9 – Release Notes

SpectreHUD v2.1.9 introduces partitioned snippet libraries for antivirus false-positive
prevention, an in-app Cheatsheet snippet import workflow, significant enhancements to
the Professional Print report export engine, and localized success dialog feedback.

---

## Highlights

### Antivirus False-Positive Prevention & Snippet Partitioning

- **Curated Safe Default Snippets:** The built-in Cheatsheet database contains only
  strictly curated, benign utility commands to prevent antivirus heuristics from flagging
  packaged binaries (`.exe`, `.deb`).
- **External Community Snippets:** Advanced offensive, payload-heavy, and specialized
  pentest commands are now distributed as optional external release assets alongside
  each release.

### In-App Cheatsheet Snippet Import

- **One-Click Snippet Import:** Added an **Import Snippets** button to the Cheatsheet
  interface, allowing users of standalone portable `.exe` and Debian installations to load
  external snippet JSON files directly into their local database without manual CLI or Python
  script execution.
- **Deduplication & Merge:** Imported snippets are merged safely into existing categories
  with validation and immediate UI refresh.

### Professional Print Export Polish & Cover Projection

- **Clean Executive Cover Projection:** Report metadata (Client, Target / Scope, Lead Tester,
  Assessment Period, Report Date, Classification, and Version) is cleanly projected onto the
  executive cover page (`.report-cover`).
- **Eliminated Duplicate Table Leaks:** Raw metadata HTML tables are automatically pruned
  from the body of both structured and unstructured reports.
- **Preserved Manual Notes:** Evaluator notes, custom disclaimers, and narrative text located
  beneath metadata tables are strictly preserved in the report body.
- **Intelligent Fallback for Markerless Reports:** Reports lacking HTML section comments
  (e.g., imported or manually authored Markdown) now resolve their leading H1 title and
  two-column metadata tables automatically onto the cover page.
- **Resilient Metadata Parsing:** Metadata extraction supports unbolded keys, optional
  trailing colons, and automatically strips empty placeholders (`-`, `n/a`).
- **Dynamic Cover Title Resolution:** Cover page titles resolve to the document's H1 heading
  rather than falling back to the generic label `"Target"`.

### Localization & Quality

- **Localized Success Dialogs:** Added `dialog.success` translations in English (`Success`)
  and German (`Erfolg`) ensuring clean i18n lint compliance.

---

## Compatibility and Upgrade

- Python 3.10 through 3.13 supported.
- Fully backward compatible with SpectreHUD v2.1.8 and earlier project databases, reports,
  Loot collections, and templates.
- No project or database schema migration required.
- Primary production platform is Windows 10/11; Linux X11 verified.

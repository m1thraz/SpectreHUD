# SpectreHUD v2.2.3 - Release Notes

SpectreHUD v2.2.3 improves first-run guidance, strengthens report and project-state safety,
finishes the Professional Print navigation workflow, and publishes the first stable export-plugin
boundary. Existing projects and reports require no migration.

---

## Highlights

### Guided First Run and Clearer Capture Controls

- **Getting Started:** A compact first-run dialog introduces the core capture-to-report workflow.
- **Contextual Guidance:** Report editing, Clip, Quick IP, Quick Notes, and Loot provide clearer
  in-context hints without interrupting experienced users.
- **Unambiguous Clipboard Control:** The former `REC` header control now uses a clipboard icon and
  fixed `Clip` label while preserving the existing active warning state, shortcuts, tray icon, and
  activation overlay.

### Navigable Professional Reports

- **Optional Linked Contents:** Professional Print can add a dedicated contents page with links to
  rendered sections and nested findings.
- **Consistent Finding References:** Findings Matrix, Attack Path, Technical Findings, and
  Remediation use deterministic `F-001` identifiers and share stable internal PDF/HTML targets.
- **Semantic Document Boundaries:** Executive Summary closes as a management section; Technical
  Findings and Appendix start on clean pages without forcing every report section onto a new page.
- **Print-Safe Flow:** Existing semantic rules continue to keep finding leads, headings, code,
  evidence, table rows, callouts, and attack-path steps together where practical while allowing
  long findings and tables to break naturally.

### Export Plugin API V1

- **Stable Public Boundary:** External exporters import the headless `spectrehud_plugin_api`
  facade instead of application-internal modules.
- **Compatibility Before Loading:** Manifests declare API version, plugin version, and minimum host
  version; incompatible plugins are rejected before their implementation or optional dependencies
  load.
- **Capability-Based Design:** Report export is the required V1 capability. Optional Loot append is
  queried explicitly instead of being imposed on every exporter.
- **Plugin-Owned Metadata:** Exporter names, descriptions, fields, translations, availability, and
  failure results cross a small typed contract. `accent` remains only a host-interpreted hint.
- **Separate DOCX Reference Plugin:** The editable Word exporter is built as an optional,
  platform-specific plugin bundle and serves as the first non-bundled reference implementation.
- **Portable Discovery:** Local plugins work with portable Windows builds, Linux packages, and
  per-user plugin directories. Obsidian and CherryTree now use the same isolated host boundary.

## Reliability and Data Safety

- All Target, authentication, scope, URL, subnet, DNS, wordlist, and hash variables now survive
  project switches and application restarts.
- Existing reports that are unreadable, oversized, or incorrectly encoded are no longer treated as
  empty editable documents. Autosave, note append, regeneration, and Loot mutations fail closed.
- Successful report saves warn when a recovery draft cannot be removed, and stale drafts older than
  the saved report are not offered for recovery.
- Bundled and optional exporters are included in Windows and Debian packaging checks and exercised
  through packaged-runtime smoke tests, including missing and incompatible dependency failures.

## Compatibility and Scope

- Existing project data, report Markdown, templates, Obsidian settings, and CherryTree workflows
  remain compatible.
- Classic HTML remains unchanged; internal anchors and pagination changes are scoped to
  Professional Print.
- V1 covers export plugins only. Import plugins, installation UI, updates, marketplaces, arbitrary
  UI injection, and generic feature hooks remain intentionally out of scope.
- Plugin authors should use the documented V1 facade and manifest format in
  `docs/export_plugin_api_v1.md`.

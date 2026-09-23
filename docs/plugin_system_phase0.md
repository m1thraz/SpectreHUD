# Plugin System Phase 0: Exporter Baseline

This document records the current Obsidian and CherryTree integration boundaries before
introducing plugin discovery or changing either export workflow. It is an implementation
baseline, not a proposed public API.

The resulting scope decision is explicit: V1 covers export plugins only. Import is deferred
until SpectreHUD has a real importer from which a separate minimal contract can be derived.

## Current workflows

### Obsidian

The Report Editor passes the current editor Markdown to `ExportCoordinator`. The coordinator
resolves the active project directory and full project state, reads the persisted Obsidian
settings, constructs `ObsidianExporter`, and presents all success and error dialogs. The
exporter writes a new Markdown note and copies safe project-local attachments. Existing notes
are preserved by creating a numbered copy.

Obsidian also has a second, independently reachable workflow: all Loot or one selected Loot
entry can be appended to the previously exported project note. Entry markers make repeated
appends idempotent and manual note content is preserved. This workflow is exposed from the
Loot toolbar, list and board cards, and the Loot edit dialog.

Configuration is persistent and currently lives directly in the application config:

- `obsidian_vault_path`
- `obsidian_export_folder`
- `obsidian_open_after_export`

The Settings dialog owns the corresponding controls and validates the values by constructing
an `ObsidianExporter` directly.

Output layout:

```text
<vault>/<configured folder>/<project>/<project>.md
                                      /attachments/*
```

### CherryTree

The Report Editor asks for a destination directory for each run and passes that destination,
the current editor Markdown, and the selected report font to `ExportCoordinator`. The
coordinator resolves the active project directory and supplies the complete current Loot
collection. `CherryTreeExporter` writes an importable HTML snapshot; it never touches a native
CherryTree database.

CherryTree currently has no persistent integration settings and no independent Loot action.

Output layout:

```text
<chosen destination>/<project>/report.html
                               /loot.html
                               /images/*
```

## Shared data and behavior

Both integrations currently require:

- a validated project name;
- the active project directory as the trust boundary for local attachments;
- the current, prepared Report Editor Markdown rather than a reload of `report.md`;
- removal of internal report, finding, and Loot synchronization markers;
- safe resolution and copying of project-local image files;
- atomic output writes;
- a structured `ExportResult` containing artifacts, warnings, status, and metadata;
- controlled handling of invalid destinations, unsafe paths, missing assets, and write errors.

Both exporters are headless pure-Python code. Neither currently adds a third-party runtime
dependency. Obsidian uses only the standard library plus SpectreHUD core services. CherryTree
also uses SpectreHUD's Markdown-to-HTML conversion and report CSS.

## Differences that must remain plugin-owned

| Concern | Obsidian | CherryTree |
| --- | --- | --- |
| Destination | Persisted vault plus relative folder | Directory chosen for each export |
| Main artifact | Markdown note | Two-file HTML package |
| Project state | Uses target and attacker IP in frontmatter | Not used |
| Loot | Optional append/deduplicate operation | Full Loot snapshot included during package export |
| Existing output | Creates a numbered note copy by default | Reuses the project package directory |
| Post-export action | Optional `obsidian://` URI open | Generic result presentation only |
| Presentation input | No font setting | Report font is required |
| Native application | URI can open Obsidian | No CherryTree process or database access |

The exact frontmatter, Obsidian entry markers, URI construction, HTML document structure,
CherryTree package names, and destination policies are exporter behavior. They must not become
generic host rules.

## A. Mandatory common V1 requirements

These requirements are demonstrated by both existing integrations:

1. Stable plugin identity and display metadata that the host can enumerate without checking a
   plugin name.
2. An explicit report-export capability.
3. An immutable execution context containing the current prepared Markdown, project identity,
   project directory, and only the project data explicitly exposed by the host.
4. A way to declare and obtain required configuration or per-run destination values without
   giving the plugin access to `ConfigManager`, dialogs, or widgets.
5. A headless execution boundary returning the existing structured `ExportResult` model or an
   equally typed result.
6. Controlled unavailable, cancelled, failed, successful-with-warning, and successful states.
7. Lazy loading of executable plugin code so missing optional dependencies cannot break normal
   application startup or metadata discovery.
8. Host-owned error containment: construction, availability checks, and execution failures must
   be converted into a controlled plugin state or export result.
9. A capability query instead of method assumptions. The current Obsidian Loot append workflow
   is a real requirement, but CherryTree does not implement it.

No current integration imports data into SpectreHUD. Import is therefore outside V1 rather than
an optional placeholder capability.

## B. Exporter-specific requirements

### Obsidian

- Persisted vault path, relative export folder, and open-after-export preference.
- Configuration validation before execution.
- Project state fields for frontmatter without direct `ProjectManager` access.
- Copy-versus-overwrite note policy.
- Safe Obsidian URI metadata and optional host-triggered URI opening.
- Independent all-Loot and single-Loot append capability.
- Existing-note requirement, entry-ID deduplication, and skipped-entry reporting.

### CherryTree

- A per-execution destination directory picker owned by the host UI.
- Report font input.
- Current Loot snapshot as part of report-package generation.
- SpectreHUD Markdown-to-HTML conversion and report styling.
- Fixed portable package artifacts: `report.html`, `loot.html`, and `images/`.

## C. Current unnecessary coupling

1. `ui.coordinators.export_coordinator` imports and constructs both concrete exporters and has
   exporter-named methods, branches, messages, settings, and post-export behavior.
2. `ReportExportActions` routes fixed string IDs through explicit Obsidian and CherryTree
   branches and owns a CherryTree-specific directory workflow.
3. `ReportExportTypeDialog` hard-codes both exporter cards, labels, icons, descriptions, badges,
   and style tokens.
4. `SettingsDialog` renders Obsidian-specific fields and imports `ObsidianExporter` for
   validation.
5. Loot UI components expose Obsidian-named callbacks, Qt signals, buttons, menu actions, and
   tooltips from `AppController` through controllers and cards.
6. The package root `core.exporters` eagerly imports both implementations, and the application
   coordinator imports both at module load. This prevents genuine dependency isolation even
   though neither exporter currently has optional third-party dependencies.
7. `CherryTreeExporter` imports `ObsidianExporter` and calls its private
   `_safe_attachment_source()` and `_loot_markdown()` helpers. Shared formatting and attachment
   policy therefore have the wrong owner.
8. `ExternalExporter` is currently unused and too weak to be a contract: it accepts arbitrary
   arguments, assumes every exporter supports `append_loot`, and does not describe metadata,
   configuration, availability, or capabilities. CherryTree does not structurally satisfy it.
9. Generic result presentation still contains Obsidian-specific URI handling and CherryTree
   inference based on artifact formats or filename suffixes.
10. `ExportResult` retains `note_path` and `obsidian_uri` compatibility properties. These are
    migration debt rather than suitable generic plugin concepts; the generic fields are
    `artifacts` and `metadata`.
11. The tests often patch concrete exporter classes inside the coordinator and assert
    exporter-named UI methods. They protect behavior, but they also encode the current coupling.

The marker-cleanup and Loot-to-Markdown behavior used by both exporters are legitimate shared
domain behavior. They should be extracted only as part of a concrete migration need, not as a
general exporter framework.

## D. Requirements deliberately excluded from the first contract

- Import, because neither reference integration currently imports data.
- Arbitrary UI injection, custom widgets, menus, toolbars, or access to `MainWindow`.
- Access to `AppController`, concrete controllers, managers, private services, or Qt objects.
- Network, authentication, credential storage, Jira, or remote API concepts.
- Feature/tool lifecycle hooks, background jobs, clipboard access, hotkeys, or Pentest Mode.
- Marketplace, installation, downloading, updating, dependency resolution, or sandbox claims.
- DOCX/PDF-specific pagination, browser rendering, or print-preview concepts.
- A universal configuration-schema language beyond the concrete field types required by the
  two reference integrations.
- Two-way synchronization, conflict resolution, file watching, or native Obsidian/CherryTree
  database access.
- Plugin-defined localization systems or theme injection before a real requirement exists.

## Existing verification surface

The migration must preserve these test layers:

- `tests/test_obsidian_exporter.py`: output, frontmatter, safe paths, attachment handling,
  copy behavior, URI encoding, marker cleanup, Loot append, and deduplication.
- `tests/test_cherrytree_exporter.py`: package layout, HTML/images, validation, warnings, and
  marker cleanup.
- `tests/test_export_coordinator.py`: application data wiring and result presentation.
- `tests/test_report_export_actions.py` and `tests/test_report_editor_tab.py`: current editor
  content, preparation gate, destination selection, success, and failure UI.
- Loot controller/card/dialog tests: all-Loot and single-entry Obsidian actions.
- Architecture tests: exporters remain headless, and the Report Editor does not own concrete
  adapters.

There is currently no test proving lazy plugin loading, missing-plugin resilience, missing
optional-dependency behavior, metadata-only discovery, capability-driven UI, or removal of one
exporter without structural damage. Those belong to the later discovery and migration gates.

## Phase 0 conclusion

The smallest demonstrated V1 is not a universal plugin platform. It is a discoverable,
headless export integration boundary with a mandatory report-export capability and one optional
Loot-append capability. It must provide host-supplied project/report data, host-mediated
configuration and destination input, structured outcomes, and lazy failure isolation.

Phase 1 should design only that contract. It should not begin by adapting the current
`ExternalExporter` protocol or by generalizing every field in `ExportCoordinator`; both would
preserve assumptions that this audit identifies as concrete-integration leakage.

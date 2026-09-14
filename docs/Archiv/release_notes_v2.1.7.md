# SpectreHUD v2.1.7 – Release Notes

SpectreHUD v2.1.7 turns the Report Workspace into a more cohesive authoring workflow.
The release adds report readiness guidance and transparent Loot synchronization,
improves themed dialogs and structured editing, and substantially simplifies the
Report Editor architecture without changing existing report files or export contracts.

---

## Highlights

### Report Workspace as the Primary Workflow

- The structured Report Workspace is now the default report view, keeping the semantic
  navigator, focused inspector, and live report preview together during authoring.
- Contextual Markdown tools remain available where direct source editing is useful,
  while Editor, Split, Preview, and Workspace modes continue to support different tasks.
- Report Actions groups additive Loot synchronization and full regeneration in one
  compact menu, reducing permanent toolbar noise without hiding destructive semantics.
- Navigator selections now resolve to typed report locations and remain aligned with
  the active inspector and highlighted preview destination.

### Report Readiness Review

- A dedicated readiness inspector evaluates the report before handoff or export.
- Actionable checks surface incomplete metadata, unresolved report content, and other
  conditions that should be reviewed before delivery.
- The assessment stays synchronized with the current workspace document and provides a
  concise overall state instead of requiring a manual section-by-section audit.

### Transparent Loot Synchronization

- Live synchronization status distinguishes new Loot, changed source entries, and
  findings that currently exist only in the report.
- Additive synchronization appends missing material without replacing unrelated report
  edits or moving the current editing position.
- Full regeneration remains an explicit, confirmed operation and saves pending editor
  changes before replacing generated content.

### Theme-Aware Report Experience

- Export, generation, and regeneration dialogs now inherit the active HUD theme instead
  of falling back to an unstyled black surface.
- Export cards retain format-specific accents while resolving their colors through theme
  tokens across the built-in palettes.
- Inspector headers, forms, tables, scroll surfaces, and section panels share a more
  consistent visual hierarchy throughout the Report Workspace.

### Reliability and Recovery

- Restored drafts now refresh the navigator, inspectors, readiness state, and preview as
  one coherent document state.
- Metadata aliases are normalized so known fields do not reappear as duplicate custom
  properties.
- Report loading, saving, crash-draft recovery, regeneration, and additive Loot sync use
  typed outcomes and preserve fail-closed behavior at their UI boundaries.

---

## Architecture and Maintainability

- `ReportEditorTab` has been reduced from roughly 2,300 to about 1,200 lines and now acts
  primarily as the workflow composition root.
- Preview transformation, rendering, typography, semantic focus, and scroll coordination
  live in dedicated preview modules and a `ReportPreviewController`.
- Inspector routing, evidence attachment, the document-action toolbar, and workspace
  construction are owned by focused components with explicit callback contracts.
- Headless session and mutation services own report persistence, recovery, regeneration,
  and additive synchronization outcomes without importing Qt.
- Transitional widget aliases and mirrored preview state were removed. Tests now use the
  public Report Editor workflow API or the component that owns the behavior, with an AST
  architecture guard preventing renewed access to private tab state.

## Compatibility and Upgrade

- Python 3.10 through 3.13.
- Existing valid SpectreHUD v2.1.6 projects, reports, templates, snippets, Loot,
  Quick Notes, and settings remain supported.
- Report section, finding, Loot-marker, export, Obsidian, and CherryTree formats remain
  compatible; no project migration is required.
- Windows remains the primary production platform. Linux X11 support is verified, while
  Wayland behavior continues to depend on compositor security restrictions.

# SpectreHUD System Map

This map covers only contracts and pitfalls that become apparent at the boundaries between multiple components.

## First Run
- `ConfigManager` enables Getting Started and the Report editing-view hint only when no config resource exists yet. Existing and unreadable configs do not acquire first-run prompts merely because these keys are missing; dismissals are persisted separately.
- The Welcome dialog reuses the existing New Project action and project selector menu. It is scheduled after the production window and global hotkeys are ready; construction of `MainWindow` in tests or other embedding contexts does not open it.

## Project Switching
- Non-obvious: The interactive "report dirty" decision and saving of the old session occur prior to activation so the user can abort without side-effects; target activation, unlocking, report loading, and session state loading are orchestrated as an atomic transaction by `WorkspaceApplicationService` with automatic rollback on failure.
- Known pitfall: `activate_project()` discards the old in-memory key and publishes `PROJECT_CHANGED` with the phase `activated` before unlocking and loading succeed; if the operation is aborted or fails, `WorkspaceApplicationService` rolls back to the previous project and restores its key, but listeners that react eagerly to `phase="activated"` see the transient target activation before the rollback event. Components should primarily await `phase="loaded"`.
- Design rationale: The four session components are replaced collectively only after full validation, whereas `report.md` is protected separately due to its own "dirty/save" contract.
- Project-scoped snippet variables use the canonical `core.project_variables` contract. `VariableBar`, `ProjectSessionService`, validation, and `ProjectState` must expose the same complete key set so a project switch or restart cannot silently discard newly introduced variables; missing fields in older schema-1 files receive compatible defaults.

## Toggling Pentest Mode
- Non-obvious: Pentest mode is activated only during creation: unencrypted security metadata is created, and the same `project_state.json` file is subsequently overwritten in encrypted form; the derived key exists only in memory and is valid for a single project at most.
- Known pitfall: The file extension does not indicate whether `project_state.json` is encrypted, and `pentest_mode: true` does not equate to "unlocked"; project switching and shutdown operations discard the in-memory key.
- Known pitfall: There is currently no workflow to disable this mode for existing projects; unchecking the box in the creation dialog merely hides the password fields and clears their input.
- Design rationale: `security_meta.json` remains readable so that the mode, KDF parameters, and password verifier can be checked prior to decryption, avoiding the need to introduce a secondary source of state.

## Report Export

- Not immediately obvious: All exports consume the current Markdown text from the source editor; "Professional Print" segments it semantically and projects structured attack-path steps as a print-only timeline, whereas "Classic Web" renders the Markdown generically—neither path regenerates or saves `report.md`.
- Export actions ask the Report Editor to commit an active editable live preview before reading the source Markdown; a rejected conversion-loss warning aborts the export instead of exporting stale or truncated content.
- Known pitfall: Markdown, Obsidian, CherryTree, and visible HTML formats strip out internal section, finding, and loot markers; consequently, an export is not a lossless substitute for the synchronizable `report.md`.
- The optional Professional Print table of contents is projected from rendered semantic sections and findings after pagination planning. It adds only HTML anchors and navigation markup; it never changes source Markdown and deliberately omits page numbers until a future multi-pass render can resolve them reliably.
- Design rationale: Internal markers carry structural and synchronization identity but are intended to remain invisible in client-facing artifacts and must not be altered by the export process.

## Report Workspace UI

- `ReportEditorTab` is the composition root: preview-only Markdown transformations live in `ui.report.preview_transforms`, workspace destinations cross widget boundaries as `ReportLocation`, and controllers use the tab's public Markdown/export methods rather than its child widgets.
- Tree item data remains a simple `(kind, identity)` tuple for Qt storage compatibility; `ReportWorkspaceNavigator` converts it to `ReportLocation` before emitting navigation requests.
- `ReportWorkspaceRouter` owns semantic destination-to-inspector resolution, the workspace shell owns its active surfaces, and `ReportPreviewController` owns preview focus; `ReportEditorTab` coordinates those components and retains only workflow state such as the current view mode.
- `ReportEvidenceActions` owns picker, import, and evidence-normalization workflows; it receives live project dependencies through providers and reports completed evidence through one callback.
- `ReportActionToolbar` owns document-action widget construction; `ReportEditorTab` retains one `action_toolbar` component instead of copying its widgets and actions onto the tab.
- `build_report_workspace_shell()` owns creation and signal wiring for the navigator, inspectors, source editor, preview, and splitter; `ReportEditorTab` retains the returned `workspace_shell` instead of exposing compatibility aliases for its children.
- The tab's supported integration surface is its public workflow API (`view_mode`, `set_view_mode`, `navigate_to`, `navigate_source_to`, `workspace_document`, and Markdown synchronization methods) plus the two owned components. An architecture test prevents report tests from reaching into private tab state.
- `ReportPreviewController` owns preview-only rendering, typography, semantic landmark focus, and proportional scroll synchronization; the tab still owns explicit rich-preview commit because that changes canonical Markdown and participates in save/export semantics.
- `ReportSessionService` owns headless `report.md` loading, persistence outcomes, and recovery-draft storage; `ReportSessionController` owns recovery prompts and persistence feedback, while the tab retains dirty indicators, timers, and the explicit rich-preview commit before a save.
- Recovery-draft cleanup distinguishes missing, removed, and failed outcomes. A successful `report.md` save remains successful when cleanup fails, but the UI warns and drafts older than the saved report are never offered as recovery candidates.
- Report reads distinguish `NOT_FOUND`, `LOADED`, and `READ_FAILED`. Only `NOT_FOUND` may initialize an empty editable report; `READ_FAILED` aborts project switching or opens the already-active report in a write-blocked state, and all autosave, note-append, regeneration, and Loot mutation paths must fail closed.
- `ReportMutationService` translates fail-closed regeneration and additive Loot-sync operations into typed outcomes; `ReportMutationActions` owns their confirmations and feedback. Both operations save pending editor changes first, but regeneration replaces the document while Loot sync only appends missing entries and preserves the cursor.

## Loot to Report Findings

- `core.reporting.finding_conversion` is the canonical boundary for turning a Loot entry into a structured finding; UI creation and template regeneration must use it instead of maintaining separate field mappings.
- Loot persists an explicit report role: `finding` participates in generated finding sections and synchronization, `evidence` remains available for attachment and appendices, and migrated pre-role entries use `legacy` to preserve prior report behavior.
- Report-ready Loot may persist CVSS score/vector, finding status, references, and multiple targets. `target_ip` remains the first target for legacy filters and integrations, while `targets` is the lossless source used by finding conversion and report rendering.
- `FindingPromotionService` is the headless transaction boundary for assigning those roles and building one finding from a primary Loot entry plus zero or more supporting entries; `ReportFindingPromotionActions` owns its selection dialog and feedback, while `ReportEditorTab` only accepts the completed finding into the workspace document.
- Evidence embedded in editable `report.md` uses versioned invisible envelopes to retain its evidence ID, type, caption, source Loot ID, and language. Rich-preview commits restore those envelopes when the visible evidence body still exists, while export cleanup removes only the envelopes and preserves the client-facing proof.
- A Loot synchronization marker records source identity and the last rendered Loot hash; it does not imply semantic equality after report-side edits. Additive sync therefore reports changed entries but does not overwrite report-authored content.
- `core.reporting.loot_reconciliation` plans and applies explicit per-finding divergence decisions. It edits only structured finding boundaries, snapshots both the reviewed report block and Loot hash to reject concurrent changes, and can append missing findings in the same persisted mutation. `LootReconciliationDialog` only collects decisions; `ReportMutationService` retains backup/save failure semantics.
- Duplicating a finding intentionally removes its Loot synchronization marker and re-keys embedded evidence, while retaining evidence provenance for traceability.

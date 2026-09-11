# SpectreHUD System Map

This map covers only contracts and pitfalls that become apparent at the boundaries between multiple components.

## Project Switching
- Non-obvious: The interactive "report dirty" decision and saving of the old session occur prior to activation so the user can abort without side-effects; target activation, unlocking, report loading, and session state loading are orchestrated as an atomic transaction by `WorkspaceApplicationService` with automatic rollback on failure.
- Known pitfall: `activate_project()` discards the old in-memory key and publishes `PROJECT_CHANGED` with the phase `activated` before unlocking and loading succeed; if the operation is aborted or fails, `WorkspaceApplicationService` rolls back to the previous project and restores its key, but listeners that react eagerly to `phase="activated"` see the transient target activation before the rollback event. Components should primarily await `phase="loaded"`.
- Design rationale: The four session components are replaced collectively only after full validation, whereas `report.md` is protected separately due to its own "dirty/save" contract.

## Toggling Pentest Mode
- Non-obvious: Pentest mode is activated only during creation: unencrypted security metadata is created, and the same `project_state.json` file is subsequently overwritten in encrypted form; the derived key exists only in memory and is valid for a single project at most.
- Known pitfall: The file extension does not indicate whether `project_state.json` is encrypted, and `pentest_mode: true` does not equate to "unlocked"; project switching and shutdown operations discard the in-memory key.
- Known pitfall: There is currently no workflow to disable this mode for existing projects; unchecking the box in the creation dialog merely hides the password fields and clears their input.
- Design rationale: `security_meta.json` remains readable so that the mode, KDF parameters, and password verifier can be checked prior to decryption, avoiding the need to introduce a secondary source of state. ## Report Export
- Not immediately obvious: All exports consume the current Markdown text from the source editor; "Professional Print" segments it semantically and cleans up the presentation, whereas "Classic Web" renders it generically—neither path regenerates or saves `report.md`.
- Known pitfall: Changes made in the editable live preview are only written back upon an explicit preview commit; export actions do not currently perform this commit themselves and may therefore export the source in its previous state.
- Known pitfall: Markdown, Obsidian, CherryTree, and visible HTML formats strip out internal section, finding, and loot markers; consequently, an export is not a lossless substitute for the synchronizable `report.md`.
- Design rationale: Internal markers carry structural and synchronization identity but are intended to remain invisible in client-facing artifacts and must not be altered by the export process.
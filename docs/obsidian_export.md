# Obsidian Export

SpectreHUD can export an active CTF/pentest report to an existing Obsidian
vault. The integration is intentionally a **one-way export**:

```text
SpectreHUD → Obsidian
```

It does not monitor the vault, read the Obsidian database, or attempt
two-way synchronization or conflict resolution.

## Setup

Select an existing vault under **Settings → General & Behavior** and
optionally specify the relative destination folder. The default is
`CTF/SpectreHUD`. The vault itself is never created automatically; only the
selected export subfolder is created upon the first export.

## Report Export

Select **Export to Obsidian...** in the report editor. The export creates a
Markdown note at:

```text
<Vault>/CTF/SpectreHUD/<Project>/<Project>.md
```

An existing note is not overwritten by default. Instead, a numbered copy
such as `<Project>_2.md` is created. The report includes frontmatter
containing the project name, target/attacker IP addresses, a timestamp,
and the tags `ctf` and `spectrehud`. Passwords and credentials are never
included in the frontmatter.

Local Markdown images from the project are copied to `attachments/`, and
their references are updated accordingly. Missing or unsafe attachments
(e.g., symlinks or paths outside the project) are skipped; the report
remains exportable but triggers a warning.

## Sending Loot

In the loot section, the **Obsidian** option appends the entire current session
to the previously exported project note. The `O` button on a loot card exports
only that specific entry. SpectreHUD writes unique entry markers into the
Markdown file for this purpose and skips identical entries during subsequent
exports. Manually edited content within the note is not regenerated or
overwritten. If the **Open exported note in Obsidian** option is enabled, the
Obsidian URI is opened only after the file has been successfully exported. If Obsidian
is not installed or cannot open the URI, the export remains successful nonetheless.
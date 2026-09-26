# Plugin System Phase 6 - Third Exporter Validation

## Reference plugin

`plugins-src/spectrehud-docx` is deliberately not part of `core.export_plugins.bundled` and is
not collected by the main SpectreHUD wheel or executable. It is a separately buildable folder
bundle whose only capability is Report Export.

## Contract findings

The existing V1 capability contract already covers the DOCX workflow:

- passive identity and presentation metadata;
- the current report Markdown and project directory;
- the selected report-font key;
- a per-run destination directory;
- structured success, failure, artifacts, and warnings.

No DOCX-specific Core/UI branch and no new capability or field kind was required. The host did
need a distribution boundary that the bundled reference plugins could not validate: ordered
platform installation roots plus manifest-relative Python loading. `source_root` is discovery
provenance owned by the host descriptor, not a plugin-authored manifest field or new capability.

## Distribution model under validation

- Portable Windows: `plugins` beside `SpectreHUD.exe`, then the per-user data plugin root.
- Debian/Linux: `/usr/lib/spectrehud/plugins`, then the XDG user-data plugin root.
- Plugin bundles may carry platform-specific dependencies in their own `vendor` directory.
- Bundled IDs take precedence over duplicate external IDs.
- Discovery remains passive; plugin and dependency imports occur only when explicitly loaded.

The DOCX implementation depends on `python-docx`; SpectreHUD itself does not. Packaged-runtime
validation, including missing and incompatible native dependency cases, is specified in
`plugin_system_phase7.md`.

## Resolved public-API concern

Phase 8 added passive inline locale catalogs and the stable `spectrehud_plugin_api` facade. The
DOCX reference plugin now carries its German display metadata without a host-side plugin-ID
exception.

# SpectreHUD Export Plugin API V1

This is the stable author-facing contract for local SpectreHUD export plugins. V1 supports
Report Export and the optional Loot Append capability only. Plugins are trusted in-process
Python code; this API is an integration boundary, not a security sandbox.

## Public Python surface

Plugin implementation code imports only from:

```python
from spectrehud_plugin_api import (
    ExportPluginMetadata,
    ExportResult,
    LoadedExportCapabilities,
    PluginAvailability,
    PluginAvailabilityCode,
    ReportExportRequest,
    parse_export_plugin_manifest,
    strip_report_markers,
)
```

Everything below `core.*` or `ui.*` is application-internal and is not covered by plugin
compatibility guarantees. A plugin must not vendor `spectrehud_plugin_api`; the running host
provides it. For development, install the matching SpectreHUD source tree or wheel alongside the
plugin.

`spectrehud_plugin_api.EXPORT_PLUGIN_API_VERSION` is currently `1`.

## Bundle layout

```text
my-exporter/
├── plugin.json
├── my_exporter/
│   ├── __init__.py
│   └── plugin.py
└── vendor/                 # optional platform-specific dependencies
```

The plugin directory is copied below one of SpectreHUD's supported plugin roots. Dependencies
that are not part of the Python standard library or public API belong in `vendor`; compiled
dependencies require separate bundles for each operating system and architecture.

## Required manifest identity and compatibility

```json
{
  "api_version": 1,
  "plugin_version": "1.0.0",
  "minimum_host_version": "2.2.3",
  "plugin_id": "example.my-exporter",
  "display_name": {
    "translation_key": "plugins.example.name",
    "fallback": "Example Export"
  },
  "description": {
    "translation_key": "plugins.example.description",
    "fallback": "Create an example report package."
  },
  "badge": "EXAMPLE",
  "icon_name": "fa5s.file-export",
  "capabilities": ["report_export"],
  "report_data_requirements": [],
  "configuration_fields": [],
  "execution_fields": [],
  "loader": "my_exporter.plugin:create_plugin"
}
```

- `api_version` is an integer and must exactly match the API major supported by the host.
- `plugin_version` identifies the plugin release and uses strict `MAJOR.MINOR.PATCH` syntax.
- `minimum_host_version` uses the same syntax. A newer requirement is rejected passively before
  plugin code or dependencies are imported.
- `plugin_id` is a stable lowercase identifier. Changing it creates a different plugin and a
  different host-owned configuration namespace.
- `loader` names a module-relative factory returning the plugin object.

Unknown manifest fields, unsupported enum values, malformed versions, future API majors, and
future minimum host versions are isolated as discovery issues. They do not prevent SpectreHUD or
other plugins from loading.

`plugin_version` does not select or install updates. V1 has no marketplace, resolver, updater, or
multi-version loader.

## Compatibility policy

Within API major 1, SpectreHUD preserves the documented dataclasses, enum values, capability
method signatures, result types, marker cleanup helper, and passive manifest meaning. Fixes and
new optional public exports may be added without changing the major. Removing or renaming a
documented field, changing required behavior, or adding a required manifest concept requires a
new API major.

Plugins declare one API major, not a range. Hosts do not guess forward compatibility. The
independent `minimum_host_version` is used when a plugin relies on a host fix or behavior added
after API V1 was introduced.

## Localized passive metadata

The English `fallback` in each `PluginText` is mandatory. A plugin may additionally provide an
inline passive catalog:

```json
{
  "display_name": {
    "translation_key": "plugins.example.name",
    "fallback": "Example Export"
  },
  "translations": {
    "de": {
      "plugins.example.name": "Beispielexport"
    },
    "pt-br": {
      "plugins.example.name": "Exportação de exemplo"
    }
  }
}
```

Locale keys are normalized lowercase BCP-47 language tags. The host tries the exact locale, then
its base language, then the normal host translation/fallback path. Catalog keys must correspond
to the manifest's display name, description, configuration labels, or execution labels. Catalogs
remain passive data and cannot execute formatting or UI code.

## Capability and data limits

Every V1 plugin declares `report_export`. `loot_append` is optional and must match the loaded
capability object exactly. A plugin declares only the report data it consumes:

- `project_network`
- `loot`
- `report_font`

Configuration and one-run inputs use only `text`, `directory`, and `boolean`. Plugins receive
immutable snapshots and plain values, never Qt widgets, controllers, managers, credentials, or
mutable project state.

Expected failures return `ExportResult.failure()`. Load defects and missing dependencies are
contained by the host. Successful files are returned as `ExportArtifact` values. Internal report
markers must be removed with the public `strip_report_markers()` helper before client-facing
content is written.

## Reference implementation and validation

The separately distributed reference implementation is
[`plugins-src/spectrehud-docx`](../plugins-src/spectrehud-docx). It demonstrates a passive
manifest, plugin-owned German metadata, per-run destination input, a platform `vendor` folder,
atomic output, and packaged-runtime failure containment.

Before publishing a plugin:

1. Test discovery without importing implementation dependencies.
2. Test metadata equality between `plugin.json` and the loaded plugin.
3. Test every declared capability and failure result.
4. Build each platform bundle with its native dependencies.
5. Validate it through a packaged SpectreHUD runtime rather than only a development interpreter.

Import plugins, custom UI, network/auth integrations, background lifecycle hooks, project
mutation, and feature plugins require separate future contracts backed by real implementations.

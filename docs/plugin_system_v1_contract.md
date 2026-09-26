# Minimal Export Plugin Contract (V1)

Status: stable public V1 export contract, validated by bundled Obsidian and CherryTree plugins
and the separately distributed DOCX reference plugin. The author-facing API is documented in
`export_plugin_api_v1.md`.

## Scope decision

V1 is an **export plugin system**.

Import is not part of V1 because SpectreHUD currently has no Obsidian or CherryTree importer.
Adding import now would create an API without a real implementation to validate it. Import may
receive its own minimal contract when an actual importer exists.

V1 has one required capability and one optional capability:

```text
Report Export [required]
├── Obsidian
│   └── Loot Append [optional]
└── CherryTree
    └── no Loot Append
```

External implementations import the stable `spectrehud_plugin_api` facade. Application-internal
`core.*` and `ui.*` modules are not part of the compatibility promise.

## Architectural direction

```text
Report/Loot UI
      |
      v
generic plugin metadata and capability requests
      |
      v
host-owned discovery, configuration, context building, and failure containment
      |
      v
headless export plugin capabilities
```

The UI must not import, construct, or branch on `ObsidianExporter`, `CherryTreeExporter`, or a
plugin ID. A plugin receives immutable export data and plain configuration values, never
`MainWindow`, `AppController`, a controller, a manager, or a Qt object.

## Contract overview

The following Python-like definitions specify shape and ownership. Names may be adjusted during
implementation, but adding concepts requires another demonstrated Obsidian or CherryTree need.

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping, Protocol

PluginValue = str | bool


class ExportCapability(str, Enum):
    REPORT_EXPORT = "report_export"
    LOOT_APPEND = "loot_append"


class ExportDataRequirement(str, Enum):
    PROJECT_NETWORK = "project_network"
    LOOT = "loot"
    REPORT_FONT = "report_font"


class FieldKind(str, Enum):
    TEXT = "text"
    DIRECTORY = "directory"
    BOOLEAN = "boolean"


@dataclass(frozen=True)
class PluginText:
    translation_key: str
    fallback: str


@dataclass(frozen=True)
class PluginField:
    key: str
    label: PluginText
    kind: FieldKind
    required: bool = False
    default: PluginValue = ""


@dataclass(frozen=True)
class ExportPluginMetadata:
    api_version: int
    plugin_version: str
    minimum_host_version: str
    plugin_id: str
    display_name: PluginText
    description: PluginText
    badge: str
    icon_name: str
    capabilities: frozenset[ExportCapability]
    report_data_requirements: frozenset[ExportDataRequirement]
    configuration_fields: tuple[PluginField, ...] = ()
    execution_fields: tuple[PluginField, ...] = ()
    accent: str | None = None


@dataclass(frozen=True)
class ProjectExportContext:
    name: str
    directory: Path


@dataclass(frozen=True)
class ProjectNetworkContext:
    target_ip: str
    attacker_ip: str


@dataclass(frozen=True)
class LootExportEntry:
    entry_id: str
    entry_type: str
    title: str
    content: str
    recommendation: str
    target_ip: str
    timestamp: str


@dataclass(frozen=True)
class ReportExportContext:
    project: ProjectExportContext
    markdown: str
    network: ProjectNetworkContext | None = None
    loot: tuple[LootExportEntry, ...] | None = None
    report_font: str | None = None


@dataclass(frozen=True)
class ReportExportRequest:
    context: ReportExportContext
    configuration: Mapping[str, PluginValue]
    execution_values: Mapping[str, PluginValue]


@dataclass(frozen=True)
class LootAppendRequest:
    project: ProjectExportContext
    entries: tuple[LootExportEntry, ...]
    configuration: Mapping[str, PluginValue]


class ReportExportCapability(Protocol):
    def export_report(self, request: ReportExportRequest) -> ExportResult: ...


class LootAppendCapability(Protocol):
    def append_loot(self, request: LootAppendRequest) -> ExportResult: ...


@dataclass(frozen=True)
class LoadedExportCapabilities:
    report_export: ReportExportCapability
    loot_append: LootAppendCapability | None = None


class ExportPlugin(Protocol):
    @property
    def metadata(self) -> ExportPluginMetadata: ...

    @property
    def capabilities(self) -> LoadedExportCapabilities: ...

    def validate_configuration(
        self, values: Mapping[str, PluginValue]
    ) -> PluginAvailability: ...
```

`ExportResult` is exposed through `spectrehud_plugin_api`. Plugins use its generic `status`, `artifacts`, `warnings`,
`error`, `skipped_entry_ids`, and `metadata` fields. Phase 5 removed the former positional
constructor and the `note_path`, `attachment_paths`, and `obsidian_uri` compatibility aliases;
callers use artifacts and explicitly defined generic metadata instead.

## Metadata

Metadata exists so discovery and UI composition do not require exporter-name branches.

Required fields have current uses:

| Field | Existing need |
| --- | --- |
| `api_version` | Fail-closed compatibility before executable plugin code loads |
| `plugin_version` | Identify independently released plugin bundles |
| `minimum_host_version` | Declare reliance on a compatible SpectreHUD host baseline |
| `plugin_id` | Stable host storage and selection without comparing display names |
| `display_name` | Existing localized Obsidian and CherryTree labels |
| `description` | Existing localized export-card explanations |
| `badge` | Existing `VAULT` and `PACKAGE` card badges |
| `icon_name` | Existing distinct export-card icons without constructing Qt objects in plugins |
| `accent` | Optional existing card accent expressed as an opaque host-supported visual hint |
| `capabilities` | Obsidian supports Loot append; CherryTree does not |
| `report_data_requirements` | CherryTree needs Loot and font; Obsidian needs network fields |
| `configuration_fields` | Obsidian has persisted vault/folder/open settings |
| `execution_fields` | CherryTree requests a destination for each run |

Metadata contains plain values only. It contains no callables, Qt objects, loaded icons,
controllers, or implementation instances. `accent` is optional and is only a short, safe
identifier for an opaque visual hint: the host may ignore, reject, or replace it with a generic
presentation. It is not a style object, theme token API, stylesheet fragment, arbitrary style
string, or UI-injection capability.

`PluginText` reuses SpectreHUD's existing translation lookup and fallback behavior. External
plugins may provide passive inline locale catalogs keyed by their declared translation keys.
Exact locale and base-language lookup occur before the normal host fallback. Dynamic locale
code and executable formatting hooks remain excluded.

## Capabilities

Every discovered V1 plugin must declare and supply `REPORT_EXPORT`.

`LOOT_APPEND` is optional. The host first queries passive metadata and, after loading, inspects
`LoadedExportCapabilities.loot_append`. It never calls `append_loot()` on the base plugin
interface and never handles absence through `NotImplementedError`.

The capability object, rather than a plugin-name branch, owns execution. The host validates the
loaded capability bundle against the passive declaration. A declared Loot capability without a
matching object, or an undeclared object, is a plugin contract error handled as an unavailable
plugin.

This is sufficient for the two current integrations:

- Obsidian supplies `ReportExportCapability` and `LootAppendCapability`.
- CherryTree supplies only `ReportExportCapability`; its report exporter receives Loot as part
  of the report context because the package includes `loot.html`.

No import or arbitrary action capability is defined.

## Export data context

The host snapshots data before crossing the plugin boundary. Plugins cannot retrieve additional
state through application services.

`ProjectExportContext` and the current prepared Markdown are required for every report export.
Additional data is supplied only when declared in `report_data_requirements`:

| Requirement | Context supplied | Existing consumer |
| --- | --- | --- |
| `PROJECT_NETWORK` | Target and attacker IP only | Obsidian frontmatter |
| `LOOT` | Immutable Loot export entries | CherryTree `loot.html` |
| `REPORT_FONT` | Selected report font key | CherryTree HTML styling |

This deliberately does not expose the full `ProjectState`. In particular, password, hash, and
other unrelated project variables are not handed to an exporter that only needs target and
attacker IP.

`LootExportEntry` contains exactly the fields rendered by the current integrations. Adding CVSS,
evidence, screenshots, or other fields requires an exporter that actually consumes them.

Paths in the context do not grant arbitrary host access. `project.directory` exists because
both current exporters must validate and copy project-local attachments. Plugins remain
responsible for treating it as a read boundary; the host remains responsible for destination
selection and configuration values.

## Configuration and execution input

The host owns persistence and user interaction. Plugins receive values, not `ConfigManager` or
dialogs.

V1 supports only the field kinds currently needed:

- `TEXT`: Obsidian relative export folder;
- `DIRECTORY`: Obsidian vault and CherryTree per-run destination;
- `BOOLEAN`: Obsidian open-after-export preference.

`configuration_fields` are persisted by the host under the plugin ID.
`execution_fields` are collected for one operation and are not persisted unless a later real
requirement changes that rule.

The same descriptor type is reused because both scopes currently need the same three primitive
controls. V1 does not include nested objects, lists, secrets, validation expressions,
dependencies between fields, arbitrary custom widgets, or plugin-executed UI callbacks.

Plugin-specific semantic validation remains headless in `validate_configuration()`. For
example, the Obsidian implementation validates that the vault exists and the relative folder is
safe. The host renders any returned reason but does not reproduce Obsidian path rules.

Execution values are validated again by the capability before writing. Cancellation while the
host collects a per-run field produces `ExportResult.cancelled()` without loading or executing
the capability when possible.

Post-export actions remain host-mediated. An exporter may return a `suggested_open_uri` or
suggested artifact in result metadata, but it cannot call `QDesktopServices`, open a process, or
show a dialog. The Obsidian plugin decides from its own configuration whether to include that
suggestion; the host validates and acts on recognized generic result metadata only after
success.

## Availability and failure model

Availability describes whether a discovered plugin can currently be offered or executed. It is
separate from one export operation's `ExportResult`.

```python
class PluginAvailabilityCode(str, Enum):
    AVAILABLE = "available"
    MISSING_DEPENDENCY = "missing_dependency"
    LOAD_FAILED = "load_failed"
    INVALID_CONFIGURATION = "invalid_configuration"


@dataclass(frozen=True)
class PluginAvailability:
    code: PluginAvailabilityCode
    message: str = ""
    details: str | None = None
```

Every code is required by a current roadmap constraint:

- `AVAILABLE`: normal Obsidian and CherryTree operation.
- `MISSING_DEPENDENCY`: packaged-runtime tests prove optional dependencies do not damage SpectreHUD.
- `LOAD_FAILED`: a broken plugin must not terminate startup or the export UI.
- `INVALID_CONFIGURATION`: Obsidian already distinguishes missing or unsafe configuration from
  execution failure.

A plugin that is not discovered is absent from the registry, not represented by another status.
Host-side enable/disable state is registry policy, not a capability or plugin lifecycle hook.

Expected destination, validation, and content failures return `ExportResult.failure()` with an
existing `ExportErrorCode`. A plugin may raise while loading or due to an implementation defect;
the host catches such exceptions at the loader/execution boundary, logs diagnostics, and
converts them to `LOAD_FAILED` or `ExportErrorCode.INTERNAL_ERROR`. Exceptions never escape into
the Qt event loop.

Warnings remain successful results. Missing or unsafe individual attachments therefore preserve
the current behavior: the main export can succeed and report warnings.

## Lazy-loading boundary

Discovery must keep passive metadata separate from executable plugin code:

```python
@dataclass(frozen=True)
class ExportPluginDescriptor:
    metadata: ExportPluginMetadata
    loader_reference: str


PluginLoader = Callable[[], ExportPlugin]
```

The exact storage and discovery mechanism is a Phase 2 decision. It must satisfy these contract
rules:

1. Listing export cards reads passive descriptors without importing exporter implementation
   modules or their optional dependencies.
2. `loader_reference` is resolved only when availability validation or execution requires the
   plugin.
3. Resolving and invoking the loader occurs inside a host-owned exception boundary.
4. Loading one plugin does not import every other plugin.
5. The plugin instance is validated against its descriptor: identity and capabilities must
   match before execution.

This does not define a marketplace, installer, remote registry, entry-point format, package
layout, dependency resolver, or sandbox. Phase 2 should choose the smallest local mechanism that
can discover the two bundled plugins and demonstrate the rules above.

## Result ownership

Plugins create files and return `ExportResult`; the host presents the result.

Generic host presentation may use:

- status and structured error;
- artifact paths and formats;
- warnings;
- skipped Loot entry IDs;
- explicitly defined generic metadata such as a suggested URI to open.

The presenter must not infer a plugin from an artifact suffix or select text by plugin ID.
User-facing success/failure titles and descriptions belong to passive plugin metadata or generic
host messages; optional post-export opening uses only `suggested_open_uri`.

## Required invariants

1. Plugin contract modules remain pure Python and do not import PyQt6.
2. Context and metadata objects are immutable snapshots.
3. Plugins do not receive SpectreHUD services or mutable domain objects.
4. Every report export still uses the prepared current editor Markdown.
5. A missing, unloaded, or failed plugin cannot prevent SpectreHUD startup or use of other
   exporters.
6. No plugin-specific dependency is imported until that plugin is loaded.
7. Capability availability is explicit and never represented by stub methods.
8. Configuration persistence and all UI remain host-owned.
9. Existing path validation, atomic writes, marker cleanup, attachment warnings, and output
   behavior remain unchanged during migration.

## Why no additional extension points exist

| Potential extension | Reason excluded from V1 |
| --- | --- |
| Import | No current importer |
| Custom UI | Both exporters can use three host-rendered field kinds |
| Network/auth | Neither exporter uses it |
| Background lifecycle | Both operations are user-triggered and synchronous today |
| Clipboard/hotkeys/tools | Not part of export behavior |
| Project mutation | Both integrations are one-way exports |
| Full project state | Existing exporters need only network fields, Loot, and local assets |
| Arbitrary post-export callback | Current URI opening can remain host-mediated |
| API version ranges | V1 uses one exact major plus a minimum host version |
| Dependency installation | V1 only isolates and reports missing dependencies |

## Contract traceability

Every V1 element has a current reference implementation or a mandatory isolation requirement:

| Contract element | Concrete reason |
| --- | --- |
| Stable identity | Host persistence and routing cannot depend on localized exporter names |
| Display metadata | Both exporters already occupy distinct localized export cards |
| Required report capability | Both Obsidian and CherryTree export the current report |
| Optional Loot append | Existing only for Obsidian; absent for CherryTree |
| Project name and directory | Both validate names and resolve project-local attachments |
| Prepared Markdown | Both export the current Report Editor state |
| Network context | Obsidian writes target and attacker IP into frontmatter |
| Loot snapshot | CherryTree produces `loot.html`; Obsidian append consumes selected entries |
| Report font | CherryTree builds styled HTML with the selected font |
| Persisted text/directory/boolean fields | Obsidian vault, folder, and open preference |
| Per-run directory field | CherryTree asks for a destination on every export |
| Configuration validation | Obsidian already rejects missing, unavailable, and unsafe paths |
| Structured result | Both already produce artifacts and attachment/image warnings |
| Skipped entry IDs | Obsidian reports deduplicated Loot appends |
| Suggested open URI | Obsidian can be opened after a successful export |
| Passive descriptor and lazy loader | Current eager imports violate the required dependency isolation |
| Missing-dependency and load-failure states | Required to prove that one optional plugin cannot break startup |

Nothing in the contract exists solely for DOCX, PDF, Jira, import, external authentication, or
feature plugins.

## Historical review gates before Phase 2

Phase 2 must not begin until review confirms:

- the three data requirements cover all and only current Obsidian/CherryTree inputs;
- the three field kinds preserve current configuration and destination workflows;
- `REPORT_EXPORT` plus optional `LOOT_APPEND` preserve all current entry points;
- the availability codes cover current configuration errors and planned dependency isolation;
- metadata is sufficient to build the existing export cards without plugin-ID branches;
- no item grants access to Qt, application services, or unrelated project state;
- no import or feature-plugin concept has re-entered V1.

Any Phase 2 implementation should first add contract tests for these invariants. It must not yet
migrate either exporter.

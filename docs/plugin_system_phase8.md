# Plugin System Phase 8 - Public V1 Stabilization

## Decisions

- The stable plugin import boundary is `spectrehud_plugin_api`; external plugins do not import
  application-internal `core.*` or `ui.*` modules.
- API compatibility is an exact integer major. V1 does not add range negotiation or dependency
  resolution.
- Plugin releases and minimum host requirements use strict `MAJOR.MINOR.PATCH` values.
- Plugin-owned localization is passive inline manifest data with exact/base-language fallback.
- `accent` remains an optional host-interpreted hint and does not become a styling API.
- Existing capabilities, contexts, field kinds, availability states, and failure semantics are
  unchanged.

## Validation basis

Obsidian, CherryTree, and the separately distributed DOCX exporter now exercise the same V1
contract. DOCX imports only the public facade and supplies its own German metadata catalog.
Manifest compatibility is decided before implementation modules or optional dependencies load.

The author-facing compatibility promise, bundle structure, manifest example, localization
format, and publication checklist live in `export_plugin_api_v1.md`.

## Still excluded

Phase 8 does not introduce plugin installation UI, updates, a marketplace, dependency fetching,
signing, sandboxing, multiple installed versions, custom widgets, import plugins, or generic
feature hooks. Each requires a separate threat model and a concrete implementation need.

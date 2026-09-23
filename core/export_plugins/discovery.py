"""Passive local manifest discovery for V1 export plugins."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from core.export_plugins.contract import (
    ExportCapability,
    ExportDataRequirement,
    ExportPluginDescriptor,
    ExportPluginMetadata,
    FieldKind,
    PluginField,
    PluginText,
    PluginValue,
)


_PLUGIN_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_VISUAL_HINT_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_LOADER_RE = re.compile(
    r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$"
)
_MANIFEST_KEYS = {
    "plugin_id",
    "display_name",
    "description",
    "badge",
    "icon_name",
    "accent",
    "capabilities",
    "report_data_requirements",
    "configuration_fields",
    "execution_fields",
    "loader",
}
_REQUIRED_MANIFEST_KEYS = {
    "plugin_id",
    "display_name",
    "description",
    "badge",
    "icon_name",
    "capabilities",
    "report_data_requirements",
    "loader",
}
_TEXT_KEYS = {"translation_key", "fallback"}
_FIELD_KEYS = {"key", "label", "kind", "required", "default"}


class PluginManifestError(ValueError):
    pass


@dataclass(frozen=True)
class PluginDiscoveryIssue:
    manifest_path: Path
    message: str


@dataclass(frozen=True)
class PluginDiscoveryResult:
    descriptors: tuple[ExportPluginDescriptor, ...]
    issues: tuple[PluginDiscoveryIssue, ...]


def _plain_object(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PluginManifestError(f"{field_name} must be an object with string keys.")
    return value


def _text(value: object, field_name: str) -> PluginText:
    raw = _plain_object(value, field_name)
    unknown = set(raw) - _TEXT_KEYS
    missing = _TEXT_KEYS - set(raw)
    if unknown or missing:
        raise PluginManifestError(
            f"{field_name} requires exactly translation_key and fallback; "
            f"unknown={sorted(unknown)}, missing={sorted(missing)}."
        )
    translation_key = raw["translation_key"]
    fallback = raw["fallback"]
    if not isinstance(translation_key, str) or not translation_key.strip():
        raise PluginManifestError(f"{field_name}.translation_key must be a non-empty string.")
    if not isinstance(fallback, str) or not fallback.strip():
        raise PluginManifestError(f"{field_name}.fallback must be a non-empty string.")
    return PluginText(translation_key.strip(), fallback.strip())


def _plugin_value(value: object, field_name: str) -> PluginValue:
    if isinstance(value, bool) or isinstance(value, str):
        return value
    raise PluginManifestError(f"{field_name} must be a string or boolean.")


def _fields(value: object, field_name: str) -> tuple[PluginField, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise PluginManifestError(f"{field_name} must be a list.")
    fields: list[PluginField] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        prefix = f"{field_name}[{index}]"
        raw = _plain_object(item, prefix)
        unknown = set(raw) - _FIELD_KEYS
        if unknown:
            raise PluginManifestError(f"{prefix} contains unknown fields: {sorted(unknown)}.")
        missing = {"key", "label", "kind"} - set(raw)
        if missing:
            raise PluginManifestError(f"{prefix} is missing fields: {sorted(missing)}.")
        key = raw["key"]
        if not isinstance(key, str) or not _PLUGIN_ID_RE.fullmatch(key):
            raise PluginManifestError(f"{prefix}.key must be a safe lowercase identifier.")
        if key in seen:
            raise PluginManifestError(f"{field_name} contains duplicate key {key!r}.")
        seen.add(key)
        try:
            kind = FieldKind(raw["kind"])
        except (TypeError, ValueError) as exc:
            raise PluginManifestError(f"{prefix}.kind is unsupported: {raw['kind']!r}.") from exc
        required = raw.get("required", False)
        if not isinstance(required, bool):
            raise PluginManifestError(f"{prefix}.required must be boolean.")
        default = _plugin_value(raw.get("default", ""), f"{prefix}.default")
        if kind is FieldKind.BOOLEAN and not isinstance(default, bool):
            raise PluginManifestError(f"{prefix}.default must be boolean for a boolean field.")
        if kind is not FieldKind.BOOLEAN and not isinstance(default, str):
            raise PluginManifestError(f"{prefix}.default must be text for {kind.value}.")
        fields.append(
            PluginField(
                key=key,
                label=_text(raw["label"], f"{prefix}.label"),
                kind=kind,
                required=required,
                default=default,
            )
        )
    return tuple(fields)


def _enum_set(value: object, enum_type: type, field_name: str) -> frozenset[Any]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PluginManifestError(f"{field_name} must be a list of strings.")
    if len(value) != len(set(value)):
        raise PluginManifestError(f"{field_name} must not contain duplicates.")
    try:
        return frozenset(enum_type(item) for item in value)
    except ValueError as exc:
        raise PluginManifestError(f"{field_name} contains unsupported value: {exc}.") from exc


def parse_export_plugin_manifest(raw_manifest: object) -> ExportPluginDescriptor:
    raw = _plain_object(raw_manifest, "manifest")
    unknown = set(raw) - _MANIFEST_KEYS
    missing = _REQUIRED_MANIFEST_KEYS - set(raw)
    if unknown:
        raise PluginManifestError(f"Manifest contains unknown fields: {sorted(unknown)}.")
    if missing:
        raise PluginManifestError(f"Manifest is missing fields: {sorted(missing)}.")

    plugin_id = raw["plugin_id"]
    if not isinstance(plugin_id, str) or not _PLUGIN_ID_RE.fullmatch(plugin_id):
        raise PluginManifestError("plugin_id must be a safe lowercase identifier.")
    loader = raw["loader"]
    if not isinstance(loader, str) or not _LOADER_RE.fullmatch(loader):
        raise PluginManifestError("loader must use the form 'package.module:factory'.")
    badge = raw["badge"]
    icon_name = raw["icon_name"]
    if not isinstance(badge, str) or not badge.strip():
        raise PluginManifestError("badge must be a non-empty string.")
    if not isinstance(icon_name, str) or not icon_name.strip():
        raise PluginManifestError("icon_name must be a non-empty string.")
    accent = raw.get("accent")
    if accent is not None and (
        not isinstance(accent, str) or not _VISUAL_HINT_RE.fullmatch(accent)
    ):
        raise PluginManifestError("accent must be a safe host visual-hint identifier.")

    capabilities = _enum_set(raw["capabilities"], ExportCapability, "capabilities")
    if ExportCapability.REPORT_EXPORT not in capabilities:
        raise PluginManifestError("V1 export plugins must declare report_export.")
    requirements = _enum_set(
        raw["report_data_requirements"],
        ExportDataRequirement,
        "report_data_requirements",
    )
    metadata = ExportPluginMetadata(
        plugin_id=plugin_id,
        display_name=_text(raw["display_name"], "display_name"),
        description=_text(raw["description"], "description"),
        badge=badge.strip(),
        icon_name=icon_name.strip(),
        capabilities=capabilities,
        report_data_requirements=requirements,
        configuration_fields=_fields(raw.get("configuration_fields"), "configuration_fields"),
        execution_fields=_fields(raw.get("execution_fields"), "execution_fields"),
        accent=accent.strip() if isinstance(accent, str) else None,
    )
    return ExportPluginDescriptor(metadata=metadata, loader_reference=loader)


def _manifest_paths(roots: Iterable[Path | str]) -> tuple[Path, ...]:
    paths: set[Path] = set()
    for value in roots:
        root = Path(value)
        direct = root / "plugin.json"
        if direct.is_file():
            paths.add(direct)
        if root.is_dir():
            paths.update(path for path in root.glob("*/plugin.json") if path.is_file())
    return tuple(sorted(paths, key=lambda path: str(path).casefold()))


def discover_export_plugins(roots: Iterable[Path | str]) -> PluginDiscoveryResult:
    descriptors: list[ExportPluginDescriptor] = []
    issues: list[PluginDiscoveryIssue] = []
    seen: set[str] = set()
    for manifest_path in _manifest_paths(roots):
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            descriptor = parse_export_plugin_manifest(raw)
            plugin_id = descriptor.metadata.plugin_id
            if plugin_id in seen:
                raise PluginManifestError(f"Duplicate plugin_id: {plugin_id}.")
            seen.add(plugin_id)
            descriptors.append(descriptor)
        except (OSError, UnicodeError, json.JSONDecodeError, PluginManifestError) as exc:
            prefix = "Invalid plugin manifest JSON" if isinstance(exc, json.JSONDecodeError) else "Invalid plugin manifest"
            issues.append(PluginDiscoveryIssue(manifest_path, f"{prefix}: {exc}"))
    return PluginDiscoveryResult(tuple(descriptors), tuple(issues))


__all__ = [
    "PluginDiscoveryIssue",
    "PluginDiscoveryResult",
    "PluginManifestError",
    "discover_export_plugins",
    "parse_export_plugin_manifest",
]

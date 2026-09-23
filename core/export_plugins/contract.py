"""Headless V1 contracts for optional export integrations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Protocol, TypeAlias

from core.reporting import ExportResult


PluginValue: TypeAlias = str | bool


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


class PluginAvailabilityCode(str, Enum):
    AVAILABLE = "available"
    MISSING_DEPENDENCY = "missing_dependency"
    LOAD_FAILED = "load_failed"
    INVALID_CONFIGURATION = "invalid_configuration"


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


def _frozen_values(values: Mapping[str, PluginValue]) -> Mapping[str, PluginValue]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True)
class ReportExportRequest:
    context: ReportExportContext
    configuration: Mapping[str, PluginValue]
    execution_values: Mapping[str, PluginValue]

    def __post_init__(self) -> None:
        object.__setattr__(self, "configuration", _frozen_values(self.configuration))
        object.__setattr__(self, "execution_values", _frozen_values(self.execution_values))


@dataclass(frozen=True)
class LootAppendRequest:
    project: ProjectExportContext
    entries: tuple[LootExportEntry, ...]
    configuration: Mapping[str, PluginValue]

    def __post_init__(self) -> None:
        object.__setattr__(self, "configuration", _frozen_values(self.configuration))


@dataclass(frozen=True)
class PluginAvailability:
    code: PluginAvailabilityCode
    message: str = ""
    details: str | None = None


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


@dataclass(frozen=True)
class ExportPluginDescriptor:
    metadata: ExportPluginMetadata
    loader_reference: str


@dataclass(frozen=True)
class PluginLoadResult:
    descriptor: ExportPluginDescriptor
    plugin: ExportPlugin | None
    availability: PluginAvailability


__all__ = [
    "ExportCapability",
    "ExportDataRequirement",
    "ExportPlugin",
    "ExportPluginDescriptor",
    "ExportPluginMetadata",
    "FieldKind",
    "LoadedExportCapabilities",
    "LootAppendCapability",
    "LootAppendRequest",
    "LootExportEntry",
    "PluginAvailability",
    "PluginAvailabilityCode",
    "PluginField",
    "PluginLoadResult",
    "PluginText",
    "PluginValue",
    "ProjectExportContext",
    "ProjectNetworkContext",
    "ReportExportCapability",
    "ReportExportContext",
    "ReportExportRequest",
]

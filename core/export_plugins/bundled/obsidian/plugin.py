"""V1 capabilities for the bundled Obsidian export integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from core.export_plugins import (
    ExportPluginMetadata,
    LoadedExportCapabilities,
    LootAppendRequest,
    PluginAvailability,
    PluginAvailabilityCode,
    PluginValue,
    ReportExportRequest,
    parse_export_plugin_manifest,
)
from core.export_plugins.bundled.obsidian.exporter import ObsidianExporter
from core.exporters import ExternalExportError
from core.reporting import ExportError, ExportErrorCode, ExportResult


def _metadata() -> ExportPluginMetadata:
    manifest_path = Path(__file__).with_name("plugin.json")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return parse_export_plugin_manifest(raw).metadata


def _text(values: Mapping[str, PluginValue], key: str, default: str = "") -> str:
    return str(values.get(key, default) or "").strip()


def _exporter(configuration: Mapping[str, PluginValue]) -> ObsidianExporter:
    return ObsidianExporter(
        _text(configuration, "obsidian_vault_path"),
        _text(configuration, "obsidian_export_folder", "CTF/SpectreHUD"),
    )


def _entry_mapping(entry) -> dict[str, str]:
    return {
        "id": entry.entry_id,
        "type": entry.entry_type,
        "title": entry.title,
        "content": entry.content,
        "recommendation": entry.recommendation,
        "target_ip": entry.target_ip,
        "timestamp": entry.timestamp,
    }


def _successful_result(
    result: ExportResult,
    configuration: Mapping[str, PluginValue],
) -> ExportResult:
    metadata = dict(result.metadata)
    if bool(configuration.get("obsidian_open_after_export", False)):
        open_uri = str(metadata.get("obsidian_uri", "") or "")
        if open_uri:
            metadata["suggested_open_uri"] = open_uri
    return ExportResult.success(
        artifacts=result.artifacts,
        warnings=result.warnings,
        skipped_entry_ids=result.skipped_entry_ids,
        metadata=metadata,
    )


def _failure(exc: BaseException) -> ExportResult:
    return ExportResult.failure(
        ExportError(
            code=ExportErrorCode.DESTINATION_ERROR,
            message=str(exc),
            details=f"{type(exc).__name__}: {exc}",
        )
    )


class ObsidianReportExportCapability:
    def export_report(self, request: ReportExportRequest) -> ExportResult:
        try:
            network = request.context.network
            project_state = {
                "target_ip": network.target_ip if network else "",
                "attacker_ip": network.attacker_ip if network else "",
            }
            result = _exporter(request.configuration).export_report(
                project_name=request.context.project.name,
                project_dir=request.context.project.directory,
                markdown=request.context.markdown,
                project_state=project_state,
                overwrite="copy",
            )
            return _successful_result(result, request.configuration)
        except (ExternalExportError, OSError, RuntimeError) as exc:
            return _failure(exc)


class ObsidianLootAppendCapability:
    def append_loot(self, request: LootAppendRequest) -> ExportResult:
        try:
            exporter = _exporter(request.configuration)
            note_path = exporter.note_path_for(request.project.name)
            if not note_path.exists():
                raise ExternalExportError(
                    "Export the report to Obsidian first so SpectreHUD can append loot without creating an incomplete note."
                )
            result = exporter.append_loot(
                project_name=request.project.name,
                entries=(_entry_mapping(entry) for entry in request.entries),
                note_path=note_path,
            )
            return _successful_result(result, request.configuration)
        except (ExternalExportError, OSError, RuntimeError) as exc:
            return _failure(exc)


class ObsidianExportPlugin:
    def __init__(self) -> None:
        self._metadata = _metadata()
        self._capabilities = LoadedExportCapabilities(
            report_export=ObsidianReportExportCapability(),
            loot_append=ObsidianLootAppendCapability(),
        )

    @property
    def metadata(self) -> ExportPluginMetadata:
        return self._metadata

    @property
    def capabilities(self) -> LoadedExportCapabilities:
        return self._capabilities

    def validate_configuration(
        self, values: Mapping[str, PluginValue]
    ) -> PluginAvailability:
        try:
            _exporter(values)
        except ExternalExportError as exc:
            return PluginAvailability(
                PluginAvailabilityCode.INVALID_CONFIGURATION,
                str(exc),
                f"{type(exc).__name__}: {exc}",
            )
        return PluginAvailability(PluginAvailabilityCode.AVAILABLE)


def create_plugin() -> ObsidianExportPlugin:
    return ObsidianExportPlugin()

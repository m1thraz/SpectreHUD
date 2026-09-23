"""V1 capability adapter for the bundled CherryTree package export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from core.export_plugins import (
    ExportPluginMetadata,
    LoadedExportCapabilities,
    PluginAvailability,
    PluginAvailabilityCode,
    PluginValue,
    ReportExportRequest,
    parse_export_plugin_manifest,
)
from core.export_plugins.bundled.cherrytree.exporter import CherryTreeExporter
from core.exporters import ExportError, ExportErrorCode, ExportResult, ExternalExportError


def _metadata() -> ExportPluginMetadata:
    manifest_path = Path(__file__).with_name("plugin.json")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return parse_export_plugin_manifest(raw).metadata


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


class CherryTreeReportExportCapability:
    def export_report(self, request: ReportExportRequest) -> ExportResult:
        destination = str(request.execution_values.get("destination", "") or "").strip()
        if not destination:
            return ExportResult.failure(
                ExportError(
                    ExportErrorCode.DESTINATION_ERROR,
                    "Choose a destination directory for the CherryTree export package.",
                )
            )
        try:
            return CherryTreeExporter(destination).export_package(
                project_name=request.context.project.name,
                project_dir=request.context.project.directory,
                report_markdown=request.context.markdown,
                loot_entries=(
                    _entry_mapping(entry) for entry in (request.context.loot or ())
                ),
                report_font=request.context.report_font or "segoe_ui",
            )
        except (ExternalExportError, OSError, RuntimeError) as exc:
            return ExportResult.failure(
                ExportError(
                    ExportErrorCode.DESTINATION_ERROR,
                    str(exc),
                    f"{type(exc).__name__}: {exc}",
                )
            )


class CherryTreeExportPlugin:
    def __init__(self) -> None:
        self._metadata = _metadata()
        self._capabilities = LoadedExportCapabilities(
            report_export=CherryTreeReportExportCapability(),
        )

    @property
    def metadata(self) -> ExportPluginMetadata:
        return self._metadata

    @property
    def capabilities(self) -> LoadedExportCapabilities:
        return self._capabilities

    def validate_configuration(
        self, _values: Mapping[str, PluginValue]
    ) -> PluginAvailability:
        return PluginAvailability(PluginAvailabilityCode.AVAILABLE)


def create_plugin() -> CherryTreeExportPlugin:
    return CherryTreeExportPlugin()

"""SpectreHUD V1 adapter for the optional DOCX exporter."""

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
from core.reporting import ExportError, ExportErrorCode, ExportResult

from spectrehud_docx.exporter import export_docx


_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "plugin.json"


def _metadata() -> ExportPluginMetadata:
    raw = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return parse_export_plugin_manifest(raw).metadata


class DocxReportExportCapability:
    def export_report(self, request: ReportExportRequest) -> ExportResult:
        raw_destination = str(request.execution_values.get("destination", "")).strip()
        if not raw_destination:
            return ExportResult.failure(
                ExportError(
                    ExportErrorCode.DESTINATION_ERROR,
                    "Choose a destination for the DOCX report.",
                )
            )
        destination = Path(raw_destination)
        try:
            return export_docx(
                destination=destination,
                project_name=request.context.project.name,
                project_dir=request.context.project.directory,
                markdown=request.context.markdown,
                report_font=request.context.report_font or "segoe_ui",
            )
        except (OSError, RuntimeError, ValueError) as exc:
            return ExportResult.failure(
                ExportError(
                    ExportErrorCode.DESTINATION_ERROR,
                    "The DOCX report could not be created.",
                    f"{type(exc).__name__}: {exc}",
                )
            )


class DocxExportPlugin:
    def __init__(self) -> None:
        self._metadata = _metadata()
        self._capabilities = LoadedExportCapabilities(
            report_export=DocxReportExportCapability()
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
        return PluginAvailability(PluginAvailabilityCode.AVAILABLE)


def create_plugin() -> DocxExportPlugin:
    return DocxExportPlugin()


__all__ = ["create_plugin"]

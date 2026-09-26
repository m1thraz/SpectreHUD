"""Headless release validation for an installed export-plugin bundle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.export_plugins import (
    ExportDataRequirement,
    FieldKind,
    LootExportEntry,
    PluginAvailabilityCode,
    PluginField,
    PluginValue,
    ProjectExportContext,
    ProjectNetworkContext,
    ReportExportContext,
    ReportExportRequest,
    create_export_plugin_registry,
)


SMOKE_RESULT_SCHEMA = 1


def _field_values(fields: tuple[PluginField, ...], output_dir: Path) -> dict[str, PluginValue]:
    values: dict[str, PluginValue] = {}
    for field in fields:
        if field.kind is FieldKind.DIRECTORY:
            values[field.key] = str(output_dir)
        elif field.kind is FieldKind.BOOLEAN:
            values[field.key] = bool(field.default)
        else:
            default = str(field.default).strip()
            values[field.key] = default or "smoke-test"
    return values


def _write_result(result_file: Path, payload: dict[str, Any]) -> None:
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _base_payload(plugin_id: str) -> dict[str, Any]:
    return {
        "schema": SMOKE_RESULT_SCHEMA,
        "plugin_id": plugin_id,
        "availability": "not_found",
        "export_status": "not_run",
        "artifacts": [],
        "message": "Export plugin was not discovered.",
    }


def run_export_plugin_smoke(
    *,
    plugin_root: Path,
    plugin_id: str,
    output_dir: Path,
    result_file: Path,
) -> int:
    """Load and execute one plugin without importing the desktop application."""
    payload = _base_payload(plugin_id)
    try:
        registry = create_export_plugin_registry(external_roots=(plugin_root,))
        descriptor = registry.get_descriptor(plugin_id)
        if descriptor is None:
            _write_result(result_file, payload)
            return 2

        loaded = registry.load(plugin_id)
        if loaded is None or loaded.plugin is None:
            availability = loaded.availability if loaded is not None else None
            payload.update(
                availability=(
                    availability.code.value if availability is not None else "load_failed"
                ),
                message=(
                    availability.message
                    if availability is not None
                    else "Export plugin could not be loaded."
                ),
            )
            if availability is not None and availability.details:
                payload["details"] = availability.details
            _write_result(result_file, payload)
            return 3

        metadata = descriptor.metadata
        configuration = _field_values(metadata.configuration_fields, output_dir)
        availability = registry.availability(plugin_id, configuration)
        if availability is None or availability.code is not PluginAvailabilityCode.AVAILABLE:
            payload.update(
                availability=(
                    availability.code.value if availability is not None else "load_failed"
                ),
                message=(
                    availability.message
                    if availability is not None
                    else "Plugin configuration could not be validated."
                ),
            )
            if availability is not None and availability.details:
                payload["details"] = availability.details
            _write_result(result_file, payload)
            return 4

        requirements = metadata.report_data_requirements
        project_dir = output_dir / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        context = ReportExportContext(
            project=ProjectExportContext("SpectreHUD Plugin Smoke Test", project_dir),
            markdown="# SpectreHUD Plugin Smoke Test\n\nExternal export execution succeeded.",
            network=(
                ProjectNetworkContext("192.0.2.45", "192.0.2.10")
                if ExportDataRequirement.PROJECT_NETWORK in requirements
                else None
            ),
            loot=(
                (
                    LootExportEntry(
                        entry_id="smoke-loot",
                        entry_type="note",
                        title="Smoke Test",
                        content="Synthetic release validation data.",
                        recommendation="No action required.",
                        target_ip="192.0.2.45",
                        timestamp="2000-01-01T00:00:00+00:00",
                    ),
                )
                if ExportDataRequirement.LOOT in requirements
                else None
            ),
            report_font=(
                "segoe_ui"
                if ExportDataRequirement.REPORT_FONT in requirements
                else None
            ),
        )
        request = ReportExportRequest(
            context=context,
            configuration=configuration,
            execution_values=_field_values(metadata.execution_fields, output_dir),
        )
        export_result = loaded.plugin.capabilities.report_export.export_report(request)
        payload.update(
            availability=PluginAvailabilityCode.AVAILABLE.value,
            export_status=export_result.status.value,
            artifacts=[str(artifact.path) for artifact in export_result.artifacts],
            message=(export_result.error.message if export_result.error else ""),
        )
        if export_result.error is not None and export_result.error.details:
            payload["details"] = export_result.error.details
        _write_result(result_file, payload)
        return 0 if export_result.is_success else 5
    except BaseException as exc:
        payload.update(
            availability="load_failed",
            message="Plugin smoke test raised an unexpected exception.",
            details=f"{type(exc).__name__}: {exc}",
        )
        _write_result(result_file, payload)
        return 6


__all__ = ["SMOKE_RESULT_SCHEMA", "run_export_plugin_smoke"]

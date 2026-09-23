"""
Export Coordinator for SpectreHUD.

Coordinates report and loot export operations (Markdown, HTML, ZIP archives).
"""

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional
from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QWidget

from core.config import ConfigManager
from core.atomic_write import atomic_write_text
from core.exporters import (
    ExportArtifact,
    ExportError,
    ExportErrorCode,
    ExportResult,
    ExportStatus,
)
from core.export_plugins import (
    ExportCapability,
    ExportDataRequirement,
    ExportPluginMetadata,
    ExportPluginRegistry,
    LootAppendRequest,
    LootExportEntry,
    PluginAvailabilityCode,
    PluginValue,
    ProjectExportContext,
    ProjectNetworkContext,
    ReportExportContext,
    ReportExportRequest,
)
from core.reporting import HtmlReportExporter
from core.reporting import ReportExportProfile
from core.i18n import t
from ui.message_boxes import ask_confirmation, show_error_dialog, show_information_dialog
from core.platform import open_path
from core.project import ProjectManager
from core.loot import LootManager
from core.logger import get_logger
from ui.controllers.history_controller import HistoryController

logger = get_logger(__name__)


class ReportExportError(RuntimeError):
    """Raised when a concrete report export operation cannot be completed."""


class ExportCoordinator(QObject):
    """Coordinates reporting and loot export actions across the application."""

    def __init__(
        self,
        project_manager: ProjectManager,
        loot_manager: LootManager,
        history_ctrl: HistoryController,
        target_provider: Callable[[], str],
        config_manager: ConfigManager,
        export_plugin_registry: Optional[ExportPluginRegistry] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.project_manager = project_manager
        self.loot_manager = loot_manager
        self.history_ctrl = history_ctrl
        self.target_provider = target_provider
        self.config = config_manager
        self.export_plugins = export_plugin_registry or ExportPluginRegistry()

    def plugin_metadata(
        self, capability: ExportCapability = ExportCapability.REPORT_EXPORT
    ) -> tuple[ExportPluginMetadata, ...]:
        return tuple(
            descriptor.metadata
            for descriptor in self.export_plugins.descriptors
            if capability in descriptor.metadata.capabilities
        )

    def plugin_metadata_for(self, plugin_id: str) -> Optional[ExportPluginMetadata]:
        descriptor = self.export_plugins.get_descriptor(plugin_id)
        return descriptor.metadata if descriptor is not None else None

    def _plugin_configuration(
        self, metadata: ExportPluginMetadata
    ) -> dict[str, PluginValue]:
        all_plugin_values = self.config.get("export_plugins", {})
        if not isinstance(all_plugin_values, Mapping):
            all_plugin_values = {}
        plugin_values = all_plugin_values.get(metadata.plugin_id, {})
        if not isinstance(plugin_values, Mapping):
            plugin_values = {}
        return {
            field.key: plugin_values.get(field.key, field.default)
            for field in metadata.configuration_fields
        }

    @staticmethod
    def _plugin_name(metadata: ExportPluginMetadata) -> str:
        return t(metadata.display_name.translation_key, metadata.display_name.fallback)

    @staticmethod
    def _loot_snapshot(entries: Iterable[Dict[str, Any]]) -> tuple[LootExportEntry, ...]:
        return tuple(
            LootExportEntry(
                entry_id=str(entry.get("id", "")),
                entry_type=str(entry.get("type", "note")),
                title=str(entry.get("title", "Untitled loot")),
                content=str(entry.get("content", "")),
                recommendation=str(entry.get("recommendation", "") or ""),
                target_ip=str(entry.get("target_ip", "")),
                timestamp=str(entry.get("timestamp", "")),
            )
            for entry in entries
        )

    def _load_available_plugin(self, window: QWidget, plugin_id: str):
        loaded = self.export_plugins.load(plugin_id)
        if loaded is None:
            show_error_dialog(
                window,
                t("plugins.export_unavailable_title", "Export plugin unavailable"),
                t("plugins.export_unavailable", "The selected export plugin is unavailable."),
            )
            return None
        if loaded.plugin is None:
            show_error_dialog(
                window,
                t("plugins.export_unavailable_title", "Export plugin unavailable"),
                loaded.availability.message,
                details=loaded.availability.details,
            )
            return None
        configuration = self._plugin_configuration(loaded.descriptor.metadata)
        availability = self.export_plugins.availability(plugin_id, configuration)
        if availability is None or availability.code is not PluginAvailabilityCode.AVAILABLE:
            plugin_name = self._plugin_name(loaded.descriptor.metadata)
            show_information_dialog(
                window,
                t(
                    "plugins.not_configured_title",
                    "{plugin} is not configured",
                    plugin=plugin_name,
                ),
                availability.message
                if availability
                else t(
                    "plugins.export_unavailable",
                    "The selected export plugin is unavailable.",
                ),
            )
            return None
        return loaded, configuration

    def export_loot(self, window: QWidget) -> None:
        """Exports session loot / report copy."""
        self.export_report(window)

    def export_report(self, window: QWidget) -> None:
        """Exports report copy using HistoryController."""
        target_ip = self.target_provider()
        active_proj = self.project_manager.get_active_project()
        self.history_ctrl.export_report_dialog(window, target_ip, active_proj)

    def export_report_markdown(self, target: Path, markdown: str) -> ExportResult:
        """Write an explicit Markdown copy of the current editor document."""
        from core.reporting import strip_report_markers

        target = Path(target)
        clean_markdown = strip_report_markers(markdown)
        if not atomic_write_text(target, clean_markdown):
            raise ReportExportError(f"Could not write Markdown report: {target}")

        bytes_written = (
            target.stat().st_size if target.exists() else len(clean_markdown.encode("utf-8"))
        )
        return ExportResult.success(
            artifacts=(ExportArtifact(path=target, format="markdown", bytes_written=bytes_written),)
        )

    def export_report_html(
        self,
        *,
        target: Path,
        project_name: str,
        markdown: str,
        theme: str,
        report_font: str,
        language: str = "en",
        profile: ReportExportProfile | str = ReportExportProfile.INTERACTIVE,
        category: Optional[str] = None,
        include_toc: bool = False,
    ) -> ExportResult:
        """Render the current editor document as a standalone HTML report."""
        project_dir = self.project_manager.get_project_dir(project_name)
        target = Path(target)
        res = HtmlReportExporter.export_to_file(
            markdown_content=markdown,
            output_path=target,
            project_dir=project_dir,
            project_name=project_name,
            target_ip="",
            theme=theme,
            report_font=report_font,
            language=language,
            profile=profile,
            category=category,
            include_toc=include_toc,
        )
        if not res:
            err_msg = (
                res.error.message
                if isinstance(res, ExportResult) and res.error
                else f"Could not write HTML report: {target}"
            )
            raise ReportExportError(err_msg)

        if isinstance(res, ExportResult):
            return res
        bytes_written = target.stat().st_size if target.exists() else 0
        return ExportResult.success(
            artifacts=(ExportArtifact(path=target, format="html", bytes_written=bytes_written),)
        )

    def export_report_with_plugin(
        self,
        window: QWidget,
        plugin_id: str,
        project_name: str,
        markdown: str,
        report_font: str,
        execution_values: Optional[Mapping[str, PluginValue]] = None,
    ) -> Optional[ExportResult]:
        resolved = self._load_available_plugin(window, plugin_id)
        if resolved is None:
            return None
        loaded, configuration = resolved
        metadata = loaded.descriptor.metadata
        try:
            project_dir = self.project_manager.get_project_dir(project_name)
            network = None
            if ExportDataRequirement.PROJECT_NETWORK in metadata.report_data_requirements:
                project_state = self.project_manager.load_project_state(project_name)
                network = ProjectNetworkContext(
                    target_ip=project_state.target_ip,
                    attacker_ip=project_state.attacker_ip,
                )
            loot = (
                self._loot_snapshot(self.loot_manager.get_all_entries())
                if ExportDataRequirement.LOOT in metadata.report_data_requirements
                else None
            )
            context = ReportExportContext(
                project=ProjectExportContext(project_name, project_dir),
                markdown=markdown,
                network=network,
                loot=loot,
                report_font=(
                    report_font
                    if ExportDataRequirement.REPORT_FONT in metadata.report_data_requirements
                    else None
                ),
            )
            result = loaded.plugin.capabilities.report_export.export_report(
                ReportExportRequest(
                    context=context,
                    configuration=configuration,
                    execution_values=execution_values or {},
                )
            )
        except BaseException as exc:
            logger.error("Export plugin %s failed: %s", plugin_id, exc, exc_info=True)
            result = ExportResult.failure(
                ExportError(
                    ExportErrorCode.INTERNAL_ERROR,
                    t("plugins.export_failed", "The export plugin failed."),
                    f"{type(exc).__name__}: {exc}",
                )
            )
        plugin_name = self._plugin_name(metadata)
        self.present_export_result(
            window,
            result,
            title=t(
                "plugins.export_complete_title",
                "{plugin} export complete",
                plugin=plugin_name,
            ),
            success_message=t(
                "plugins.report_exported",
                "Exported to {plugin}:\n{path}",
                plugin=plugin_name,
                path=str(result.primary_artifact.path if result.primary_artifact else ""),
            ),
            warning_message=t(
                "plugins.attachment_warning",
                "Some attachments could not be copied.",
            ),
        )
        return result

    def append_loot_with_plugin(
        self,
        window: QWidget,
        plugin_id: str,
        entries: Iterable[Dict[str, Any]],
    ) -> Optional[ExportResult]:
        resolved = self._load_available_plugin(window, plugin_id)
        if resolved is None:
            return None
        loaded, configuration = resolved
        capability = loaded.plugin.capabilities.loot_append
        if capability is None:
            return None
        project_name = self.project_manager.get_active_project()
        try:
            result = capability.append_loot(
                LootAppendRequest(
                    project=ProjectExportContext(
                        project_name,
                        self.project_manager.get_project_dir(project_name),
                    ),
                    entries=self._loot_snapshot(entries),
                    configuration=configuration,
                )
            )
        except BaseException as exc:
            logger.error("Loot plugin %s failed: %s", plugin_id, exc, exc_info=True)
            result = ExportResult.failure(
                ExportError(
                    ExportErrorCode.INTERNAL_ERROR,
                    t("plugins.export_failed", "The export plugin failed."),
                    f"{type(exc).__name__}: {exc}",
                )
            )
        plugin_name = self._plugin_name(loaded.descriptor.metadata)
        if result.skipped_entry_ids:
            message = t(
                "plugins.loot_exported_duplicates",
                "Loot is already up to date in {plugin} ({count} duplicate entries skipped).",
                plugin=plugin_name,
                count=len(result.skipped_entry_ids),
            )
        else:
            message = t(
                "plugins.loot_exported",
                "Loot appended to {plugin}:\n{path}",
                plugin=plugin_name,
                path=str(result.primary_artifact.path if result.primary_artifact else ""),
            )
        self.present_export_result(
            window,
            result,
            title=t(
                "plugins.updated_title",
                "{plugin} updated",
                plugin=plugin_name,
            ),
            success_message=message,
            warning_message=t(
                "plugins.attachment_warning",
                "Some attachments could not be copied.",
            ),
        )
        return result

    def append_single_loot_with_plugin(
        self, window: QWidget, plugin_id: str, entry_id: str
    ) -> None:
        entry = next(
            (item for item in self.loot_manager.get_all_entries() if item.get("id") == entry_id),
            None,
        )
        if entry is not None:
            self.append_loot_with_plugin(window, plugin_id, [entry])

    def present_export_result(
        self,
        window: Optional[QWidget],
        result: Any,
        *,
        title: str,
        success_message: Optional[str] = None,
        ask_open_file: Optional[Path] = None,
        warning_message: Optional[str] = None,
        show_info_dialog_fn: Optional[Callable] = None,
        show_error_dialog_fn: Optional[Callable] = None,
        ask_confirm_fn: Optional[Callable] = None,
    ) -> None:
        """Present any ExportResult to the user in a consistent, UI-standard way."""
        present_export_result(
            window,
            result,
            title=title,
            success_message=success_message,
            ask_open_file=ask_open_file,
            warning_message=warning_message,
            show_info_dialog_fn=show_info_dialog_fn,
            show_error_dialog_fn=show_error_dialog_fn,
            ask_confirm_fn=ask_confirm_fn,
        )


def present_export_result(
    window: Optional[QWidget],
    result: Any,
    *,
    title: str,
    success_message: Optional[str] = None,
    ask_open_file: Optional[Path] = None,
    warning_message: Optional[str] = None,
    show_info_dialog_fn: Optional[Callable] = None,
    show_error_dialog_fn: Optional[Callable] = None,
    ask_confirm_fn: Optional[Callable] = None,
) -> None:
    """Present any ExportResult to the user in a consistent, UI-standard way."""
    status = getattr(result, "status", None)
    if status is ExportStatus.CANCELLED:
        return

    _show_info = show_info_dialog_fn or show_information_dialog
    _show_err = show_error_dialog_fn or show_error_dialog
    _ask_confirm = ask_confirm_fn or ask_confirmation

    if status is ExportStatus.FAILED:
        err = getattr(result, "error", None)
        err_msg = getattr(err, "message", None) if err else "Export failed"
        details = getattr(err, "details", None) if err else None
        _show_err(window, title, str(err_msg), details=details)
        return

    msg = success_message
    if not msg:
        artifacts = getattr(result, "artifacts", ())
        note_path = getattr(result, "note_path", None)
        if artifacts:
            first = artifacts[0].path
            msg = t(
                "report.export_saved_msg",
                "Kopie gespeichert: {filename}",
                filename=first.name,
            )
        elif note_path:
            p = Path(note_path)
            msg = t(
                "report.export_saved_msg",
                "Kopie gespeichert: {filename}",
                filename=p.name,
            )
        else:
            msg = t("report.export_saved_title", "Exportiert")

    warnings = getattr(result, "warnings", ())
    if warnings:
        msg += "\n\n" + (
            warning_message
            or t(
                "plugins.attachment_warning",
                "Some attachments could not be copied.",
            )
        )

    if ask_open_file:
        from PyQt6.QtWidgets import QMessageBox

        reply = _ask_confirm(
            window,
            title,
            t(
                "report.export_html_success_msg",
                "HTML-Report gespeichert:\n{filename}\n\nIm Standard-Browser öffnen?",
                filename=ask_open_file.name,
            ),
            default_button=QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if not open_path(ask_open_file):
                _show_err(
                    window,
                    t("report.open_html_error_title", "Report unavailable"),
                    t(
                        "report.open_html_error_message",
                        "The exported HTML report could not be opened:\n{path}",
                        path=str(ask_open_file),
                    ),
                )
    else:
        _show_info(window, title, msg)

    suggested_open_uri = getattr(result, "metadata", {}).get("suggested_open_uri")
    if suggested_open_uri:
        if not QDesktopServices.openUrl(QUrl(str(suggested_open_uri))):
            logger.warning("Export URI could not be opened: %s", suggested_open_uri)

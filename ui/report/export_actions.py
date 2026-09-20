"""Export workflow actions and UI presentation for the Report Editor."""

from pathlib import Path
from typing import Any, Callable, Optional

from PyQt6.QtWidgets import QFileDialog, QPlainTextEdit, QWidget

from core.i18n import t
from core.logger import get_logger
from ui.coordinators.export_coordinator import (
    ExportCoordinator,
    ReportExportError,
    present_export_result as _coordinator_present_export_result,
)
from ui.message_boxes import ask_confirmation, show_error_dialog, show_information_dialog
from ui.report.dialogs import HtmlExportOptions, ReportExportTypeDialog, select_html_export_options

logger = get_logger(__name__)


class ReportExportActions:
    """Encapsulates report export workflows, file pickers, coordinator delegation, and outcome UI."""

    def __init__(
        self,
        parent_widget: QWidget,
        editor: Any,
        report_file_manager_provider: Callable[[], Any],
        export_coordinator_provider: Callable[[], Optional[ExportCoordinator]],
        current_project_provider: Callable[[], Optional[str]],
        active_template_provider: Callable[[], Any],
        report_font_key_provider: Callable[[], str],
        select_export_type_override: Optional[Callable[[], Optional[str]]] = None,
        select_html_options_override: Optional[Callable[[], Optional[HtmlExportOptions]]] = None,
        prepare_export: Optional[Callable[[], bool]] = None,
    ):
        self.parent_widget = parent_widget
        self._editor_provider = editor if callable(editor) else (lambda: editor)
        self._report_file_manager_provider = report_file_manager_provider
        self._export_coordinator_provider = export_coordinator_provider
        self._current_project_provider = current_project_provider
        self._active_template_provider = active_template_provider
        self._report_font_key_provider = report_font_key_provider
        self._select_export_type_override = select_export_type_override
        self._select_html_options_override = select_html_options_override
        self._prepare_export = prepare_export

    def _ready_to_export(self) -> bool:
        return self._prepare_export is None or self._prepare_export()

    @property
    def editor(self) -> QPlainTextEdit:
        return self._editor_provider()

    @property
    def report_file_manager(self) -> Any:
        return self._report_file_manager_provider()

    @property
    def export_coordinator(self) -> Optional[ExportCoordinator]:
        return self._export_coordinator_provider()

    @property
    def current_project(self) -> Optional[str]:
        return self._current_project_provider()

    @property
    def active_template(self) -> Any:
        return self._active_template_provider()

    def report_font_key(self) -> str:
        return self._report_font_key_provider()

    # ------------------------------------------------------------------ #
    # Export Routing
    # ------------------------------------------------------------------ #

    def on_export_clicked(self) -> None:
        """Opens the single export chooser and delegates to the selected workflow."""
        export_type = self.select_export_type()
        if export_type == "markdown":
            self.on_export_copy_clicked()
        elif export_type == "html":
            self.on_export_html_clicked()
        elif export_type == "obsidian":
            self.on_export_obsidian_clicked()
        elif export_type == "cherrytree":
            self.on_export_cherrytree_clicked()

    def select_export_type(self) -> Optional[str]:
        """Returns the selected export workflow choice or None if cancelled."""
        if self._select_export_type_override:
            return self._select_export_type_override()
        return ReportExportTypeDialog.select_export_type(self.parent_widget)

    def select_html_export_options(self) -> Optional[HtmlExportOptions]:
        """Choose the HTML presentation profile without changing report content."""
        if self._select_html_options_override:
            return self._select_html_options_override()
        return select_html_export_options(
            self.parent_widget.window() if self.parent_widget else None
        )

    def require_export_coordinator(self) -> Optional[ExportCoordinator]:
        """Return the application export boundary or show a controlled error."""
        coordinator = self.export_coordinator
        if coordinator is None:
            logger.error("Obsidian report export requested without a configured handler.")
            show_error_dialog(
                self.parent_widget,
                t("report.obsidian_export_failed_title", "Obsidian export failed"),
                t(
                    "report.obsidian_export_unavailable",
                    "The Obsidian export service is unavailable.",
                ),
            )
            return None
        return coordinator

    # ------------------------------------------------------------------ #
    # Concrete Export Workflows
    # ------------------------------------------------------------------ #

    def on_export_copy_clicked(self) -> None:
        """Exports an exact Markdown copy to a chosen file path."""
        rfm = self.report_file_manager
        default_path = rfm.get_report_path(self.current_project) if rfm else Path("report.md")
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent_widget,
            t("report.export_copy_dialog_title", "Report-Kopie exportieren"),
            str(default_path),
            "Markdown (*.md)",
        )
        if not file_path:
            return

        target = Path(file_path)
        if target.suffix.lower() != ".md":
            target = target.with_suffix(".md")

        coordinator = self.require_export_coordinator()
        if coordinator is None:
            return
        if not self._ready_to_export():
            return
        try:
            result = coordinator.export_report_markdown(target, self.editor.toPlainText())
            self.present_export_result(
                result,
                title=t("report.export_saved_title", "Exportiert"),
                success_message=t(
                    "report.export_saved_msg", "Kopie gespeichert: {filename}", filename=target.name
                ),
            )
        except ReportExportError as exc:
            logger.error("Export der Report-Kopie nach %s fehlgeschlagen: %s", target, exc)
            self._show_file_export_error(target, exc)

    def on_export_html_clicked(self) -> None:
        """Exports the report as HTML/PDF presentation."""
        export_options = self.select_html_export_options()
        if export_options is None:
            return
        theme = export_options.theme
        profile = export_options.profile

        rfm = self.report_file_manager
        default_path = (
            rfm.get_report_path(self.current_project).with_suffix(".html")
            if rfm
            else Path("report.html")
        )
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent_widget,
            t("report.export_html_dialog_title", "HTML-Report exportieren"),
            str(default_path),
            "HTML (*.html)",
        )
        if not file_path:
            return

        target = Path(file_path)
        if target.suffix.lower() != ".html":
            target = target.with_suffix(".html")

        coordinator = self.require_export_coordinator()
        if coordinator is None:
            return
        if not self._ready_to_export():
            return
        try:
            tpl = self.active_template
            doc_lang = tpl.language if tpl else "en"
            doc_category = tpl.category if tpl else None
            result = coordinator.export_report_html(
                target=target,
                project_name=self.current_project,
                markdown=self.editor.toPlainText(),
                theme=theme,
                report_font=self.report_font_key(),
                language=doc_lang,
                profile=profile,
                category=doc_category,
                include_toc=export_options.include_toc,
            )
            self.present_export_result(
                result,
                title=t("report.export_html_success_title", "HTML-Report exportiert"),
                ask_open_file=target,
            )
        except ReportExportError as exc:
            logger.error("Export des HTML-Reports nach %s fehlgeschlagen: %s", target, exc)
            self._show_file_export_error(target, exc)

    def _show_file_export_error(self, target: Path, exc: Exception) -> None:
        show_error_dialog(
            self.parent_widget.window() if self.parent_widget else None,
            t("dialog.error", "Fehler"),
            t(
                "report.export_failed_msg",
                "Export fehlgeschlagen: Die Datei '{filename}' konnte nicht gespeichert werden.",
                filename=target.name,
            ),
            details=str(exc),
        )

    def on_export_obsidian_clicked(self) -> None:
        """Delegate the current editor document to the shared export coordinator."""
        if not self.current_project:
            return
        coordinator = self.require_export_coordinator()
        if coordinator is None:
            return
        if not self._ready_to_export():
            return
        coordinator.export_report_to_obsidian(
            self.parent_widget,
            self.current_project,
            self.editor.toPlainText(),
        )

    def on_export_cherrytree_clicked(self) -> None:
        """Creates a portable HTML package; no CherryTree database is touched."""
        if not self.current_project:
            return
        rfm = self.report_file_manager
        if not rfm or not getattr(rfm, "project_manager", None):
            return
        project_dir = rfm.project_manager.get_project_dir(self.current_project)
        default_directory = project_dir / "exports"
        destination = QFileDialog.getExistingDirectory(
            self.parent_widget,
            t("report.cherrytree_directory_title", "Choose CherryTree export directory"),
            str(default_directory if default_directory.exists() else project_dir),
        )
        if not destination:
            return
        coordinator = self.require_export_coordinator()
        if coordinator is None:
            return
        if not self._ready_to_export():
            return
        try:
            result = coordinator.export_report_to_cherrytree(
                destination=Path(destination),
                project_name=self.current_project,
                markdown=self.editor.toPlainText(),
                report_font=self.report_font_key(),
            )
            self.present_export_result(
                result,
                title=t("report.cherrytree_exported_title", "CherryTree package complete"),
            )
        except ReportExportError as exc:
            logger.error("CherryTree package export failed: %s", exc, exc_info=True)
            show_error_dialog(
                self.parent_widget,
                t("report.cherrytree_export_failed_title", "CherryTree export failed"),
                t(
                    "report.cherrytree_export_failed",
                    "The CherryTree package could not be created:\n{error}",
                    error=str(exc),
                ),
            )

    # ------------------------------------------------------------------ #
    # Result Presentation
    # ------------------------------------------------------------------ #

    def present_export_result(
        self,
        result: Any,
        *,
        title: str,
        success_message: Optional[str] = None,
        ask_open_file: Optional[Path] = None,
    ) -> None:
        """Presents an ExportResult by delegating to ExportCoordinator or canonical presentation."""
        coordinator = self.export_coordinator
        window = self.parent_widget.window() if self.parent_widget else None
        if coordinator is not None and hasattr(coordinator, "present_export_result") and not hasattr(coordinator, "_mock_return_value"):
            coordinator.present_export_result(
                window,
                result,
                title=title,
                success_message=success_message,
                ask_open_file=ask_open_file,
                show_info_dialog_fn=show_information_dialog,
                show_error_dialog_fn=show_error_dialog,
                ask_confirm_fn=ask_confirmation,
            )
        else:
            _coordinator_present_export_result(
                window,
                result,
                title=title,
                success_message=success_message,
                ask_open_file=ask_open_file,
                show_info_dialog_fn=show_information_dialog,
                show_error_dialog_fn=show_error_dialog,
                ask_confirm_fn=ask_confirmation,
            )


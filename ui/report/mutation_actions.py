"""Regeneration and additive Loot-sync workflows for the Report Workspace."""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from PyQt6.QtWidgets import QDialog, QWidget

from core.i18n import t
from core.logger import get_logger
from core.reporting import (
    ReportMutationFailureReason,
    ReportMutationResult,
    ReportMutationService,
    ReportTemplate,
    TemplateRepository,
)
from ui.message_boxes import show_error_dialog
from ui.report.dialogs import ReportGenerationDialog, ReportRegenerationConfirmDialog

logger = get_logger("report_mutation_actions")


@dataclass(frozen=True)
class ReportMutationCallbacks:
    """Live tab state and shell updates required by report mutations."""

    current_project: Callable[[], Optional[str]]
    current_markdown: Callable[[], str]
    is_dirty: Callable[[], bool]
    commit_preview: Callable[[], None]
    save_pending: Callable[[], bool]
    active_template: Callable[[], Optional[ReportTemplate]]
    set_active_template: Callable[[ReportTemplate], None]
    apply_content: Callable[[str, bool], None]
    set_loot_sync_state: Callable[[int, int, int], None]
    set_status: Callable[[str], None]


class ReportMutationActions:
    """Own dialogs, feedback, and orchestration for persisted report mutations."""

    def __init__(
        self,
        *,
        parent: QWidget,
        service: ReportMutationService,
        template_repository: TemplateRepository,
        loot_manager: Callable[[], Any],
        clipboard_history: Callable[[], Any],
        callbacks: ReportMutationCallbacks,
    ):
        self._parent = parent
        self._service = service
        self._template_repository = template_repository
        self._loot_manager = loot_manager
        self._clipboard_history = clipboard_history
        self._callbacks = callbacks

    def regenerate(self) -> None:
        project_name = self._prepare_persisted_mutation("regenerate")
        if project_name is None:
            return

        has_existing = self._service.has_report(project_name)
        if has_existing and self._callbacks.current_markdown().strip():
            confirmation = ReportRegenerationConfirmDialog(parent=self._parent)
            if confirmation.exec() != QDialog.DialogCode.Accepted:
                return

        dialog = ReportGenerationDialog(
            template_repo=self._template_repository,
            selected_template=self._callbacks.active_template(),
            has_existing_report=has_existing,
            parent=self._parent,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selected_template is None:
            return
        template = dialog.selected_template
        self._callbacks.set_active_template(template)

        result = self._service.regenerate(
            project_name=project_name,
            loot_manager=self._loot_manager(),
            clipboard_history=self._clipboard_history(),
            template=template,
        )
        if not result.success:
            self._show_failure(result, operation="regenerate")
            return
        self._callbacks.apply_content(result.content, False)

    def append_missing_loot(self) -> None:
        project_name = self._prepare_persisted_mutation("append missing Loot")
        if project_name is None:
            return

        result = self._service.append_missing_loot(
            project_name=project_name,
            loot_manager=self._loot_manager(),
            template=self._callbacks.active_template(),
        )
        if not result.success:
            self._show_failure(result, operation="append")
            return
        if result.added_count == 0:
            self.refresh_loot_sync_state()
            self._callbacks.set_status(
                t("report.append_loot_no_changes", "No missing loot entries found")
            )
            return

        self._callbacks.apply_content(result.content, True)
        if result.used_fallback:
            self._callbacks.set_status(
                t(
                    "report.append_loot_success_fallback",
                    "{count} entries appended · {fallback_count} category(ies) under 'New Loot Entries'",
                    count=result.added_count,
                    fallback_count=len(result.fallback_categories),
                )
            )
        else:
            self._callbacks.set_status(
                t(
                    "report.append_loot_success",
                    "{count} new loot entries appended",
                    count=result.added_count,
                )
            )

    def refresh_loot_sync_state(self) -> None:
        loot_manager = self._loot_manager()
        if loot_manager is None:
            return
        try:
            state = self._service.compare_loot(
                self._callbacks.current_markdown(), loot_manager
            )
        except Exception:
            logger.exception("Could not compare report markers with project Loot")
            return
        self._callbacks.set_loot_sync_state(
            len(state.missing), len(state.stale), len(state.orphaned_ids)
        )

    def _prepare_persisted_mutation(self, operation: str) -> Optional[str]:
        project_name = self._callbacks.current_project()
        if not project_name:
            return None
        self._callbacks.commit_preview()
        if self._callbacks.is_dirty() and not self._callbacks.save_pending():
            logger.error(
                "Could not save pending report edits before %s for project '%s'",
                operation,
                project_name,
            )
            return None
        return project_name

    def _show_failure(
        self, result: ReportMutationResult, *, operation: str
    ) -> None:
        logger.error(
            "Report %s failed (%s): %s",
            operation,
            result.failure_reason,
            result.detail,
        )
        if result.failure_reason is ReportMutationFailureReason.BACKUP_FAILED:
            title = (
                t("report.backup_failed_title", "Backup fehlgeschlagen")
                if operation == "regenerate"
                else t("dialog.error", "Error")
            )
            message = t(
                "report.backup_failed_msg"
                if operation == "regenerate"
                else "report.append_backup_failed_msg",
                "Das automatische Backup ist fehlgeschlagen. Zum Schutz des bestehenden Reports wurde die Änderung abgebrochen.",
            )
        elif result.failure_reason is ReportMutationFailureReason.SAVE_FAILED:
            title = (
                t("report.save_failed_title", "Speichern fehlgeschlagen")
                if operation == "regenerate"
                else t("dialog.error", "Error")
            )
            message = t(
                "report.save_failed_msg"
                if operation == "regenerate"
                else "report.append_save_failed_msg",
                "Der geänderte Report konnte nicht gespeichert werden. Der bisherige Report bleibt erhalten.",
            )
        else:
            title = t("dialog.error", "Error")
            message = t(
                "report.mutation_failed_msg",
                "The report could not be updated. Details are in the log.",
            )
        show_error_dialog(
            self._parent.window(), title, message, details=result.detail
        )

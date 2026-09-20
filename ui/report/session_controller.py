"""UI policy for loading and persisting an editable report session."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtWidgets import QMessageBox, QWidget

from core.i18n import t
from core.logger import get_logger
from core.reporting import DraftDiscardResult, DraftDiscardStatus, ReportSessionService
from ui.message_boxes import show_error_dialog, show_warning_dialog

logger = get_logger("report_session_controller")


@dataclass(frozen=True)
class LoadedReport:
    """Content selected by the user for the newly loaded editor session."""

    markdown: str
    project_dir: Path
    restored_draft: bool


class ReportSessionController:
    """Own recovery prompts and persistence feedback around the headless service."""

    def __init__(
        self,
        *,
        service: ReportSessionService,
        parent: QWidget,
        set_status: Callable[[str], None],
    ):
        self._service = service
        self._parent = parent
        self._set_status = set_status

    def load_project(self, project_name: str) -> LoadedReport:
        state = self._service.load_project(project_name)
        recovery_draft = state.recovery_draft
        if recovery_draft is None:
            return LoadedReport(state.markdown, state.project_dir, False)

        msg = QMessageBox(self._parent.window())
        msg.setWindowTitle(t("report.draft_recovery_title", "Recover Unsaved Draft"))
        msg.setText(
            t(
                "report.draft_recovery_msg",
                "An unsaved draft for '{project}' from {time} was found.\n\nDo you want to restore it?",
                project=project_name,
                time=recovery_draft.saved_at.strftime("%H:%M:%S"),
            )
        )
        msg.setIcon(QMessageBox.Icon.Question)
        restore_button = msg.addButton(
            t("report.draft_restore_btn", "Restore Draft"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        msg.addButton(
            t("report.draft_discard_btn", "Discard Draft"),
            QMessageBox.ButtonRole.RejectRole,
        )
        msg.setDefaultButton(restore_button)
        msg.exec()

        if msg.clickedButton() is restore_button:
            return LoadedReport(recovery_draft.markdown, state.project_dir, True)
        self._warn_failed_cleanup(self._service.discard_draft(state.project_dir))
        return LoadedReport(state.markdown, state.project_dir, False)

    def save(self, project_name: str, markdown: str) -> bool:
        result = self._service.save_document(project_name, markdown, clear_recovery_draft=True)
        if result.success:
            self._warn_failed_cleanup(result.draft_cleanup)
            return True
        logger.error(
            "Manual save failed for report '%s' (%s): %s",
            project_name,
            result.failure_reason,
            result.detail,
        )
        show_error_dialog(
            self._parent.window(),
            t("dialog.error", "Error"),
            t(
                "report.save_error",
                "The report could not be saved. Details are in the log.",
            ),
        )
        return False

    def autosave(self, project_name: str, markdown: str) -> bool:
        result = self._service.save_document(project_name, markdown, clear_recovery_draft=False)
        if result.success:
            return True
        logger.error(
            "Autosave failed for report '%s' (%s): %s",
            project_name,
            result.failure_reason,
            result.detail,
        )
        self._set_status(t("report.autosave_failed", "Autosave failed — please save manually"))
        return False

    def save_draft(self, project_name: str, markdown: str) -> None:
        self._service.save_draft(project_name, markdown)

    def _warn_failed_cleanup(self, cleanup: Optional[DraftDiscardResult]) -> None:
        if cleanup is None or cleanup.status is not DraftDiscardStatus.FAILED:
            return
        show_warning_dialog(
            self._parent.window(),
            t("dialog.warning", "Warning"),
            t(
                "report.draft_cleanup_warning",
                "The recovery draft could not be removed. The saved report is unchanged, "
                "but you may be prompted about the draft again.",
            ),
        )

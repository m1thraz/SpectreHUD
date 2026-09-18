"""UI orchestration for explicit Loot-to-Finding promotion."""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from PyQt6.QtWidgets import QDialog, QWidget

from core.i18n import t
from core.logger import get_logger
from core.reporting import (
    FindingPromotionFailureReason,
    FindingPromotionResult,
    FindingPromotionService,
    ReportFindingItem,
    extract_report_markers,
)
from ui.message_boxes import show_error_dialog, show_warning_dialog
from ui.report.dialogs import LootFindingPromotionDialog

logger = get_logger("report_finding_promotion_actions")


@dataclass(frozen=True)
class FindingPromotionCallbacks:
    current_markdown: Callable[[], str]
    add_finding: Callable[[ReportFindingItem], None]


class ReportFindingPromotionActions:
    """Own promotion selection, feedback, and delivery to the workspace."""

    def __init__(
        self,
        *,
        parent: QWidget,
        service: FindingPromotionService,
        loot_manager: Callable[[], Any],
        callbacks: FindingPromotionCallbacks,
        config_manager: Optional[Any] = None,
    ):
        self._parent = parent
        self._service = service
        self._loot_manager = loot_manager
        self._callbacks = callbacks
        self._config_manager = config_manager

    def promote(self) -> None:
        loot_manager = self._loot_manager()
        if loot_manager is None:
            return

        markers = extract_report_markers(self._callbacks.current_markdown())
        candidates = [
            entry
            for entry in loot_manager.get_all_entries()
            if entry.get("id") and str(entry["id"]) not in markers
        ]
        if not candidates:
            show_warning_dialog(
                self._parent,
                t("report.no_promotable_loot_title", "No unassigned Loot"),
                t(
                    "report.no_promotable_loot_msg",
                    "All available Loot is already represented by report findings.",
                ),
            )
            return

        suggestions_enabled = True
        correlation_window = 90
        if self._config_manager is not None:
            suggestions_enabled = bool(
                self._config_manager.get("evidence_suggestions_enabled", True)
            )
            correlation_window = self._config_manager.get(
                "evidence_correlation_window_seconds", 90
            )

        dialog = LootFindingPromotionDialog(
            candidates,
            evidence_entries=candidates,
            parent=self._parent,
            suggestions_enabled=suggestions_enabled,
            correlation_window_seconds=correlation_window,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_entry:
            return

        result = self._service.promote(
            loot_store=loot_manager,
            primary_id=str(dialog.selected_entry["id"]),
            evidence_ids=[str(entry.get("id", "")) for entry in dialog.selected_evidence_entries],
            fallback_title=t("report.new_finding_default_title", "New Finding"),
        )
        if not result.success or result.finding is None:
            self._show_failure(result)
            return
        self._callbacks.add_finding(result.finding)

    def _show_failure(self, result: FindingPromotionResult) -> None:
        logger.error(
            "Loot-to-Finding promotion failed (%s): %s",
            result.failure_reason,
            result.detail,
        )
        title = t("report.promote_failed_title", "Could not create finding")
        if result.failure_reason in {
            FindingPromotionFailureReason.PRIMARY_NOT_FOUND,
            FindingPromotionFailureReason.EVIDENCE_NOT_FOUND,
        }:
            show_warning_dialog(
                self._parent,
                title,
                t(
                    "report.promote_loot_changed_msg",
                    "The selected Loot changed before it could be promoted. Please select it again.",
                ),
            )
            return
        show_error_dialog(
            self._parent,
            title,
            t(
                "report.promote_loot_failed_msg",
                "The Loot roles could not be saved, so no finding was created.",
            ),
            details=result.detail,
        )

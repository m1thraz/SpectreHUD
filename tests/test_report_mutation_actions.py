from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QDialog, QWidget

from core.reporting import ReportMutationResult, ReportMutationService
from ui.report.mutation_actions import ReportMutationActions, ReportMutationCallbacks


pytestmark = pytest.mark.integration


def _actions(qapp):
    parent = QWidget()
    service = MagicMock(spec=ReportMutationService)
    loot_manager = MagicMock()
    applied = []
    statuses = []
    callbacks = ReportMutationCallbacks(
        current_project=lambda: "Box",
        current_markdown=lambda: "# Report",
        is_dirty=lambda: False,
        commit_preview=lambda: None,
        save_pending=lambda: True,
        active_template=lambda: None,
        set_active_template=lambda _template: None,
        apply_content=lambda content, preserve_cursor: applied.append(
            (content, preserve_cursor)
        ),
        set_loot_sync_state=lambda _missing, _stale, _orphaned: None,
        set_status=statuses.append,
    )
    actions = ReportMutationActions(
        parent=parent,
        service=service,
        template_repository=MagicMock(),
        loot_manager=lambda: loot_manager,
        clipboard_history=lambda: None,
        callbacks=callbacks,
    )
    return parent, service, actions, applied, statuses


def test_unified_sync_uses_additive_path_when_there_are_no_differences(qapp):
    parent, service, actions, applied, _statuses = _actions(qapp)
    service.compare_loot.return_value = MagicMock(stale=(), orphaned_ids=())
    service.append_missing_loot.return_value = ReportMutationResult(
        success=True, content="# Updated", added_count=1
    )

    actions.synchronize_loot()

    service.append_missing_loot.assert_called_once()
    service.reconcile_loot.assert_not_called()
    assert applied == [("# Updated", True)]
    parent.deleteLater()


def test_unified_sync_applies_reviewed_differences_and_missing_findings(qapp):
    parent, service, actions, applied, statuses = _actions(qapp)
    state = MagicMock(stale=({"id": "loot-1"},), orphaned_ids=(), missing=({"id": "loot-2"},))
    service.compare_loot.return_value = state
    service.describe_loot_differences.return_value = (MagicMock(),)
    service.reconcile_loot.return_value = ReportMutationResult(
        success=True,
        content="# Reconciled",
        resolved_count=1,
        added_count=1,
    )

    with patch("ui.report.mutation_actions.LootReconciliationDialog") as dialog_type:
        dialog = dialog_type.return_value
        dialog.exec.return_value = QDialog.DialogCode.Accepted
        dialog.decisions = {"loot-1": "apply_loot"}
        dialog.append_missing = True
        actions.synchronize_loot()

    service.reconcile_loot.assert_called_once()
    assert applied == [("# Reconciled", True)]
    assert "1" in statuses[-1]
    parent.deleteLater()

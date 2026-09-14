"""Component tests for the Loot-to-Finding promotion UI orchestration."""

from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QDialog, QWidget

from core.reporting import FindingPromotionResult, ReportFindingItem
from ui.report.finding_promotion_actions import (
    FindingPromotionCallbacks,
    ReportFindingPromotionActions,
)

pytestmark = pytest.mark.integration


def test_promotion_actions_filter_reported_loot_and_deliver_finding(monkeypatch):
    available = {"id": "available", "title": "Available", "content": "proof"}
    represented = {"id": "represented", "title": "Existing", "content": "old"}
    loot_manager = MagicMock()
    loot_manager.get_all_entries.return_value = [available, represented]
    service = MagicMock()
    finding = ReportFindingItem(id="available", title="Available")
    service.promote.return_value = FindingPromotionResult(
        success=True,
        finding=finding,
    )
    delivered = []

    class AcceptedDialog:
        def __init__(self, primary_entries, evidence_entries, parent):
            assert primary_entries == [available]
            assert evidence_entries == [available]
            assert isinstance(parent, QWidget)
            self.selected_entry = available
            self.selected_evidence_entries = []

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "ui.report.finding_promotion_actions.LootFindingPromotionDialog",
        AcceptedDialog,
    )
    parent = QWidget()
    actions = ReportFindingPromotionActions(
        parent=parent,
        service=service,
        loot_manager=lambda: loot_manager,
        callbacks=FindingPromotionCallbacks(
            current_markdown=lambda: (
                "<!-- spectre:loot:represented:0123456789ab -->"
            ),
            add_finding=delivered.append,
        ),
    )

    actions.promote()

    service.promote.assert_called_once_with(
        loot_store=loot_manager,
        primary_id="available",
        evidence_ids=[],
        fallback_title="New Finding",
    )
    assert delivered == [finding]
    parent.deleteLater()

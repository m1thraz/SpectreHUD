"""Headless tests for explicit Loot-to-Finding promotion and evidence bundling."""

from unittest.mock import MagicMock

from core.reporting import (
    FindingPromotionFailureReason,
    FindingPromotionService,
)
from core.storage import PersistenceError


def _entry(entry_id: str, **overrides):
    entry = {
        "id": entry_id,
        "type": "note",
        "category": "access",
        "severity": "high",
        "title": entry_id,
        "content": f"content for {entry_id}",
        "report_role": "evidence",
    }
    entry.update(overrides)
    return entry


def test_promote_builds_one_finding_with_multiple_supporting_loot_entries():
    primary = _entry("primary", type="credential", content="admin:secret")
    note = _entry("note", content="Authentication bypass confirmed")
    screenshot = _entry("shot", type="screenshot", content="loot/proof.png")
    store = MagicMock()
    store.get_all_entries.return_value = [primary, note, screenshot]
    store.assign_report_roles.return_value = dict(primary, report_role="finding")

    result = FindingPromotionService().promote(
        loot_store=store,
        primary_id="primary",
        evidence_ids=["note", "shot", "note", "primary"],
    )

    assert result.success
    assert result.finding is not None
    assert result.finding.id == "primary"
    assert [item.source_loot_id for item in result.finding.evidence_items] == [
        "primary",
        "note",
        "shot",
    ]
    assert "Authentication bypass confirmed" in result.finding.description
    assert "loot/proof.png" in result.finding.description
    store.assign_report_roles.assert_called_once_with("primary", ["note", "shot"])


def test_promote_rejects_missing_evidence_before_persisting_roles():
    store = MagicMock()
    store.get_all_entries.return_value = [_entry("primary")]

    result = FindingPromotionService().promote(
        loot_store=store,
        primary_id="primary",
        evidence_ids=["removed"],
    )

    assert not result.success
    assert result.failure_reason is FindingPromotionFailureReason.EVIDENCE_NOT_FOUND
    assert result.detail == "removed"
    store.assign_report_roles.assert_not_called()


def test_promote_maps_role_persistence_failure_without_returning_a_finding():
    store = MagicMock()
    store.get_all_entries.return_value = [_entry("primary")]
    store.assign_report_roles.side_effect = PersistenceError("disk full")

    result = FindingPromotionService().promote(
        loot_store=store,
        primary_id="primary",
    )

    assert not result.success
    assert result.finding is None
    assert result.failure_reason is FindingPromotionFailureReason.PERSISTENCE_FAILED
    assert result.detail == "disk full"

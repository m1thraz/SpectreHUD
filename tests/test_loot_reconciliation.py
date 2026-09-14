from __future__ import annotations

import pytest

from core.reporting import (
    LootDifferenceKind,
    LootReconciliationAction,
    LootReconciliationError,
    LootReconciliationSelection,
    ReportFindingItem,
    analyze_loot_reconciliation,
    classify_loot_report_state,
    finding_from_loot_entry,
    reconcile_loot_report,
)


def _entry(entry_id: str = "loot-1", **updates):
    entry = {
        "id": entry_id,
        "report_role": "finding",
        "category": "recon",
        "type": "note",
        "title": "Original Loot title",
        "content": "Original Loot description",
        "severity": "high",
        "target_ip": "10.10.10.10",
        "timestamp": "2026-09-14 10:00",
    }
    entry.update(updates)
    return entry


def _report_block(entry, *, title="Edited report title", description="Manual report prose"):
    finding = finding_from_loot_entry(entry)
    finding.title = title
    finding.description = description
    return finding.to_markdown(language="en", include_phase=True)


def test_analysis_describes_structured_changed_and_report_only_findings():
    original = _entry()
    orphan = _entry("loot-deleted")
    report = f"# Report\n\n{_report_block(original)}\n\n{_report_block(orphan)}\n"

    items = analyze_loot_reconciliation(
        report,
        [_entry(title="Changed in Loot")],
    )

    assert [(item.entry_id, item.kind) for item in items] == [
        ("loot-1", LootDifferenceKind.CHANGED),
        ("loot-deleted", LootDifferenceKind.REPORT_ONLY),
    ]
    assert items[0].report_title == "Edited report title"
    assert items[0].loot_title == "Changed in Loot"
    assert all(item.resolvable for item in items)


def test_accept_report_preserves_manual_bytes_and_advances_only_marker():
    original = _entry()
    report = _report_block(original)
    changed = _entry(content="Changed Loot prose")

    result = reconcile_loot_report(
        report,
        [changed],
        {"loot-1": LootReconciliationAction.ACCEPT_REPORT},
    )

    assert result.accepted_count == 1
    assert "Manual report prose" in result.text
    assert "Changed Loot prose" not in result.text
    assert not classify_loot_report_state(result.text, [changed]).stale


def test_apply_loot_replaces_only_selected_finding_block():
    original = _entry()
    unrelated = ReportFindingItem(id="manual-1", title="Manual", description="Keep exact")
    report = f"PREFIX\n{_report_block(original)}\n{unrelated.to_markdown('en')}\nSUFFIX"
    changed = _entry(title="Loot wins", content="Fresh source", severity="critical")

    result = reconcile_loot_report(
        report,
        [changed],
        {"loot-1": LootReconciliationAction.APPLY_LOOT},
        language="en",
    )

    assert result.replaced_count == 1
    assert "### Loot wins" in result.text
    assert "Fresh source" in result.text
    assert "Manual report prose" not in result.text
    assert unrelated.to_markdown("en") in result.text
    assert "SUFFIX" in result.text
    assert result.text.startswith("PREFIX\n")


def test_keep_both_detaches_exact_report_copy_and_tracks_fresh_loot_copy():
    original = _entry()
    report = _report_block(original)
    changed = _entry(title="Updated Loot title", content="Updated Loot body")

    result = reconcile_loot_report(
        report,
        [changed],
        {"loot-1": LootReconciliationAction.KEEP_BOTH},
        language="en",
    )

    assert result.duplicated_count == 1
    assert "spectre:finding:start:report-loot-1" in result.text
    assert "Manual report prose" in result.text
    assert result.text.count("spectre:loot:loot-1:") == 1
    assert "### Updated Loot title" in result.text
    state = classify_loot_report_state(result.text, [changed])
    assert len(state.current) == 1
    assert not state.stale


def test_apply_loot_relocates_a_changed_phase_without_reserializing_manual_text():
    original = _entry(category="recon")
    report = (
        "# Report\n\n"
        "## Reconnaissance\n\n"
        f"{_report_block(original)}\n\n"
        "Manual spacing:   keep\n\n"
        "## Initial Access\n\n"
        "_Notes & observations for this phase:_\n"
    )
    changed = _entry(category="access", title="Moved finding")

    result = reconcile_loot_report(
        report,
        [changed],
        {"loot-1": LootReconciliationAction.APPLY_LOOT},
        language="en",
    )

    assert result.text.index("## Initial Access") < result.text.index("### Moved finding")
    assert "Manual spacing:   keep" in result.text


def test_report_only_finding_can_be_detached_or_deleted():
    orphan = _entry("loot-deleted")
    report = f"# Report\n\n{_report_block(orphan)}\n\nTail"

    detached = reconcile_loot_report(
        report,
        [],
        {"loot-deleted": LootReconciliationAction.DETACH_REPORT},
    )
    assert detached.detached_count == 1
    assert "Manual report prose" in detached.text
    assert "spectre:loot:loot-deleted" not in detached.text

    deleted = reconcile_loot_report(
        report,
        [],
        {"loot-deleted": LootReconciliationAction.DELETE_REPORT},
    )
    assert deleted.deleted_count == 1
    assert "Edited report title" not in deleted.text
    assert deleted.text.startswith("# Report")
    assert deleted.text.endswith("Tail")


def test_reconciliation_can_append_missing_findings_in_same_result():
    current = _entry()
    missing = _entry("loot-2", title="New finding", category="misc")
    report = _report_block(current)

    result = reconcile_loot_report(
        report,
        [current, missing],
        {},
        append_missing=True,
        language="en",
    )

    assert result.added_count == 1
    assert "New finding" in result.text


def test_invalid_or_unstructured_decision_fails_before_changing_text():
    changed = _entry(content="new")
    legacy_report = (
        "<!-- spectre:loot:loot-1:deadbeef0000 -->\n"
        "### Legacy finding\n\nDo not guess its boundary."
    )
    item = analyze_loot_reconciliation(legacy_report, [changed])[0]
    assert not item.resolvable

    with pytest.raises(LootReconciliationError, match="structured boundary"):
        reconcile_loot_report(
            legacy_report,
            [changed],
            {"loot-1": LootReconciliationAction.APPLY_LOOT},
        )

    structured = _report_block(_entry())
    with pytest.raises(LootReconciliationError, match="invalid"):
        reconcile_loot_report(
            structured,
            [changed],
            {"loot-1": LootReconciliationAction.DELETE_REPORT},
        )


def test_review_snapshot_rejects_a_later_loot_change():
    original = _entry()
    reviewed = _entry(content="reviewed change")
    report = _report_block(original)
    item = analyze_loot_reconciliation(report, [reviewed])[0]
    selection = LootReconciliationSelection(
        action=LootReconciliationAction.APPLY_LOOT,
        expected_report_hash=item.report_hash,
        expected_loot_hash=item.loot_hash,
    )

    with pytest.raises(LootReconciliationError, match="changed while"):
        reconcile_loot_report(
            report,
            [_entry(content="changed again after dialog opened")],
            {"loot-1": selection},
        )


def test_review_snapshot_rejects_a_later_report_edit():
    original = _entry()
    reviewed = _entry(content="reviewed change")
    report = _report_block(original)
    item = analyze_loot_reconciliation(report, [reviewed])[0]
    selection = LootReconciliationSelection(
        action=LootReconciliationAction.APPLY_LOOT,
        expected_report_hash=item.report_hash,
        expected_loot_hash=item.loot_hash,
    )

    with pytest.raises(LootReconciliationError, match="changed while"):
        reconcile_loot_report(
            report.replace("Manual report prose", "Later report edit"),
            [reviewed],
            {"loot-1": selection},
        )

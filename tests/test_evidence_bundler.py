"""
Unit tests for core/reporting/evidence_bundler.py and LootFindingPromotionDialog suggestion integration.
"""

from typing import Any, Dict

from core.reporting import (
    EvidenceCandidate,
    suggest_related_evidence,
)


def _make_candidate(
    source_type: str,
    entry_id: str,
    timestamp: str,
    phase_id: str = "privesc",
    target_ip: str = "10.10.10.42",
    **kwargs: Any,
) -> EvidenceCandidate:
    entry: Dict[str, Any] = {
        "id": entry_id,
        "timestamp": timestamp,
        "phase_id": phase_id,
        "target_ip": target_ip,
        **kwargs,
    }
    return EvidenceCandidate(source_type=source_type, entry=entry)  # type: ignore[arg-type]


def test_suggest_exact_match_within_90s():
    anchor = _make_candidate("screenshot", "s1", "2026-09-18 14:00:00")
    c1 = _make_candidate("clipboard", "c1", "2026-09-18 14:00:45")

    suggestions = suggest_related_evidence(anchor, [c1])
    assert len(suggestions) == 1
    assert suggestions[0].candidate.id == "c1"
    assert suggestions[0].time_delta_seconds == 45.0
    assert suggestions[0].is_cross_source is True


def test_suggest_boundary_90s_vs_91s():
    anchor = _make_candidate("screenshot", "s1", "2026-09-18 14:00:00")
    c_90 = _make_candidate("clipboard", "c90", "2026-09-18 14:01:30")  # exactly 90s
    c_91 = _make_candidate("clipboard", "c91", "2026-09-18 14:01:31")  # 91s

    sugg_90 = suggest_related_evidence(anchor, [c_90])
    assert len(sugg_90) == 1
    assert sugg_90[0].candidate.id == "c90"

    sugg_91 = suggest_related_evidence(anchor, [c_91])
    assert len(sugg_91) == 0


def test_suggest_target_matrix():
    # 1. Both identical -> match
    anchor_scoped = _make_candidate("screenshot", "s1", "2026-09-18 14:00:00", target_ip="10.10.10.10")
    cand_same = _make_candidate("clipboard", "c1", "2026-09-18 14:00:20", target_ip="10.10.10.10")
    assert len(suggest_related_evidence(anchor_scoped, [cand_same])) == 1

    # 2. Anchor scoped, candidate empty -> match within 90s
    cand_empty_target = _make_candidate("quick_note", "n1", "2026-09-18 14:00:20", target_ip="")
    assert len(suggest_related_evidence(anchor_scoped, [cand_empty_target])) == 1

    # 3. Anchor empty, candidate scoped -> reject
    anchor_empty = _make_candidate("screenshot", "s2", "2026-09-18 14:00:00", target_ip="")
    assert len(suggest_related_evidence(anchor_empty, [cand_same])) == 0

    # 4. Both empty -> matches within 45s, rejected at 46s
    cand_empty_40 = _make_candidate("quick_note", "n40", "2026-09-18 14:00:40", target_ip="")
    cand_empty_46 = _make_candidate("quick_note", "n46", "2026-09-18 14:00:46", target_ip="")
    assert len(suggest_related_evidence(anchor_empty, [cand_empty_40])) == 1
    assert len(suggest_related_evidence(anchor_empty, [cand_empty_46])) == 0

    # 5. Different known targets -> strictly rejected even at 2 seconds
    cand_other = _make_candidate("clipboard", "c_other", "2026-09-18 14:00:02", target_ip="10.10.10.20")
    assert len(suggest_related_evidence(anchor_scoped, [cand_other])) == 0


def test_suggest_phase_matrix():
    # 1. Both identical -> match within 90s
    anchor_privesc = _make_candidate("screenshot", "s1", "2026-09-18 14:00:00", phase_id="privesc")
    cand_privesc = _make_candidate("clipboard", "c1", "2026-09-18 14:01:00", phase_id="privesc")
    assert len(suggest_related_evidence(anchor_privesc, [cand_privesc])) == 1

    # 2. Anchor phase set, candidate empty -> matches only in tighter 45s window
    cand_no_phase_30 = _make_candidate("quick_note", "n30", "2026-09-18 14:00:30", phase_id="")
    cand_no_phase_60 = _make_candidate("quick_note", "n60", "2026-09-18 14:01:00", phase_id="")
    assert len(suggest_related_evidence(anchor_privesc, [cand_no_phase_30])) == 1
    assert len(suggest_related_evidence(anchor_privesc, [cand_no_phase_60])) == 0

    # 3. Anchor phase empty, candidate set -> reject
    anchor_no_phase = _make_candidate("screenshot", "s2", "2026-09-18 14:00:00", phase_id="")
    assert len(suggest_related_evidence(anchor_no_phase, [cand_privesc])) == 0

    # 4. Different known phases -> strictly reject
    cand_recon = _make_candidate("clipboard", "c_rec", "2026-09-18 14:00:05", phase_id="recon")
    assert len(suggest_related_evidence(anchor_privesc, [cand_recon])) == 0


def test_suggest_excludes_anchor_itself():
    anchor = _make_candidate("screenshot", "s1", "2026-09-18 14:00:00")
    assert len(suggest_related_evidence(anchor, [anchor])) == 0


def test_suggest_already_attached_keys():
    anchor = _make_candidate("screenshot", "s1", "2026-09-18 14:00:00")
    c1 = _make_candidate("clipboard", "c1", "2026-09-18 14:00:10")
    c2 = _make_candidate("quick_note", "n2", "2026-09-18 14:00:15")

    # Filter with flat string ID
    sugg1 = suggest_related_evidence(anchor, [c1, c2], already_attached_keys={"c1"})
    assert len(sugg1) == 1
    assert sugg1[0].candidate.id == "n2"

    # Filter with (source_type, id) tuple
    sugg2 = suggest_related_evidence(anchor, [c1, c2], already_attached_keys={("quick_note", "n2")})
    assert len(sugg2) == 1
    assert sugg2[0].candidate.id == "c1"


def test_suggest_clipboard_to_clipboard_rejected():
    anchor = _make_candidate("clipboard", "c1", "2026-09-18 14:00:00")
    cand_clip = _make_candidate("clipboard", "c2", "2026-09-18 14:00:05")
    cand_note = _make_candidate("quick_note", "n1", "2026-09-18 14:00:10")

    suggestions = suggest_related_evidence(anchor, [cand_clip, cand_note])
    assert len(suggestions) == 1
    assert suggestions[0].candidate.id == "n1"


def test_suggest_cross_source_ranked_higher():
    anchor = _make_candidate("screenshot", "s1", "2026-09-18 14:00:00")
    # Same source screenshot 10s away
    same_src = _make_candidate("screenshot", "s2", "2026-09-18 14:00:10")
    # Cross source clipboard 30s away
    cross_src = _make_candidate("clipboard", "c1", "2026-09-18 14:00:30")

    suggestions = suggest_related_evidence(anchor, [same_src, cross_src])
    assert len(suggestions) == 2
    # Cross-source must be ranked first despite larger time delta
    assert suggestions[0].candidate.id == "c1"
    assert suggestions[0].is_cross_source is True
    assert suggestions[1].candidate.id == "s2"
    assert suggestions[1].is_cross_source is False


def test_suggest_graceful_on_bad_timestamps():
    anchor = _make_candidate("screenshot", "s1", "2026-09-18 14:00:00")
    bad1 = _make_candidate("clipboard", "b1", "invalid_timestamp")
    bad2 = _make_candidate("clipboard", "b2", "")

    assert len(suggest_related_evidence(anchor, [bad1, bad2])) == 0

    # Bad anchor timestamp returns empty list without exception
    bad_anchor = _make_candidate("screenshot", "s_bad", "corrupt_date")
    good_cand = _make_candidate("clipboard", "c1", "2026-09-18 14:00:10")
    assert len(suggest_related_evidence(bad_anchor, [good_cand])) == 0


def test_suggest_legacy_entries_with_category():
    # Legacy entry using 'category' instead of 'phase_id'
    anchor = _make_candidate("screenshot", "s1", "2026-09-18 14:00:00", category="access", phase_id="")
    cand = _make_candidate("loot", "l1", "2026-09-18 14:00:25", category="access", phase_id="")
    suggestions = suggest_related_evidence(anchor, [cand])
    assert len(suggestions) == 1
    assert suggestions[0].candidate.id == "l1"


def test_dialog_evidence_suggestion_ui(qapp):
    from ui.report.dialogs import LootFindingPromotionDialog

    entries = [
        {
            "id": "loot_anchor",
            "type": "screenshot",
            "title": "Root Shell",
            "content": "![Root](loot/s1.png)",
            "category": "privesc",
            "target_ip": "10.10.10.42",
            "timestamp": "2026-09-18 14:00:00",
        },
        {
            "id": "loot_cand_related",
            "type": "note",
            "title": "sudo -l output",
            "content": "NOPASSWD less",
            "category": "privesc",
            "target_ip": "10.10.10.42",
            "timestamp": "2026-09-18 14:00:20",
        },
        {
            "id": "loot_cand_unrelated",
            "type": "note",
            "title": "old recon",
            "content": "nmap output",
            "category": "recon",
            "target_ip": "10.10.10.42",
            "timestamp": "2026-09-18 12:00:00",
        },
    ]

    dialog = LootFindingPromotionDialog(primary_entries=entries, evidence_entries=entries)
    # Anchor is loot_anchor
    dialog.primary_list.setCurrentRow(0)

    # Suggestion button should be visible with 1 related evidence
    assert not dialog.btn_suggest.isHidden()
    assert len(dialog._current_suggestions) == 1
    assert dialog._current_suggestions[0].candidate.id == "loot_cand_related"

    # Initially nothing selected
    assert len(dialog.selected_evidence_entries) == 0

    # Click apply suggestions button
    dialog.btn_suggest.click()

    # Now loot_cand_related should be selected
    selected_ids = [e.get("id") for e in dialog.selected_evidence_entries]
    assert "loot_cand_related" in selected_ids
    assert "loot_cand_unrelated" not in selected_ids

    dialog.close()

"""
Unit tests for the pure Python loot filter and counting service.

Runs in memory without Qt or GUI widgets.
"""

import pytest
from core.loot.filter import (
    filter_loot_entries,
    count_loot_by_type,
    count_loot_by_category,
)


@pytest.fixture
def sample_loot():
    return [
        {
            "id": "loot_1",
            "type": "credentials",
            "title": "Admin Password",
            "content": "admin:SecretPass123",
            "target_ip": "10.10.10.55",
            "category": "credentials",
            "severity": "high",
        },
        {
            "id": "loot_2",
            "type": "flag",
            "title": "User Flag",
            "content": "HTB{user_flag_1337}",
            "target_ip": "10.10.10.55",
            "category": "flags",
            "severity": "info",
        },
        {
            "id": "loot_3",
            "type": "screenshot",
            "title": "Web Login Page",
            "content": "![Screenshot](loot/screenshot_01.png)",
            "target_ip": "10.10.10.56",
            "category": "recon",
            "severity": "info",
        },
        {
            "id": "loot_4",
            "type": "note",
            "title": "TODO Port Knocking",
            "content": "Need to knock ports 7000 8000 9000",
            "target_ip": "",
            "category": "misc",
            "severity": "low",
        },
    ]


def test_filter_all_returns_all_entries(sample_loot):
    """No filters returns all entries."""
    results = filter_loot_entries(sample_loot)
    assert len(results) == 4


def test_filter_by_target_ip(sample_loot):
    """Filtering by target IP includes exact IP matches and universal entries without target_ip."""
    results = filter_loot_entries(sample_loot, target_ip="10.10.10.55")
    assert len(results) == 3
    ids = {r["id"] for r in results}
    assert "loot_1" in ids
    assert "loot_2" in ids
    assert "loot_4" in ids  # universal (empty target_ip)


def test_filter_by_entry_type(sample_loot):
    """Filtering by entry type supports canonical types and aliases."""
    results = filter_loot_entries(sample_loot, entry_type="credentials")
    assert len(results) == 1
    assert results[0]["id"] == "loot_1"

    # Test alias 'cred'
    alias_results = filter_loot_entries(sample_loot, entry_type="cred")
    assert len(alias_results) == 1
    assert alias_results[0]["id"] == "loot_1"


def test_filter_by_category(sample_loot):
    """Filtering by category matches specific category ID."""
    results = filter_loot_entries(sample_loot, category="flags")
    assert len(results) == 1
    assert results[0]["id"] == "loot_2"


def test_filter_by_search_query(sample_loot):
    """Search matches title, content, target_ip, or category case-insensitively."""
    results = filter_loot_entries(sample_loot, search_query="SecretPass")
    assert len(results) == 1
    assert results[0]["id"] == "loot_1"

    results_knocking = filter_loot_entries(sample_loot, search_query="knocking")
    assert len(results_knocking) == 1
    assert results_knocking[0]["id"] == "loot_4"


def test_count_by_type(sample_loot):
    """Counts entries grouped by type."""
    type_defs = [
        {"id": "credentials"},
        {"id": "flag"},
        {"id": "screenshot"},
        {"id": "note"},
        {"id": "hash"},
    ]
    counts = count_loot_by_type(sample_loot, type_defs)
    assert counts["all"] == 4
    assert counts["credentials"] == 1
    assert counts["flag"] == 1
    assert counts["screenshot"] == 1
    assert counts["note"] == 1
    assert counts["hash"] == 0


def test_count_by_category(sample_loot):
    """Counts entries grouped by category."""
    cat_defs = [
        {"id": "credentials"},
        {"id": "flags"},
        {"id": "recon"},
        {"id": "misc"},
        {"id": "privesc"},
    ]
    counts = count_loot_by_category(sample_loot, cat_defs)
    assert counts["all"] == 4
    assert counts["credentials"] == 1
    assert counts["flags"] == 1
    assert counts["recon"] == 1
    assert counts["misc"] == 1
    assert counts["privesc"] == 0

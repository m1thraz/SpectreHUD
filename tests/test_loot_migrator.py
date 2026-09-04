"""Tests for the isolated loot schema migrator."""

from core.loot_migrator import LootMigrator


VALID_CATEGORIES = {"recon", "access", "misc"}
TYPE_ALIASES = {"cred": "credentials", "credentials": "credentials", "note": "note"}


def _migrate(entries):
    return LootMigrator.migrate(
        entries,
        valid_category_ids=VALID_CATEGORIES,
        type_aliases=TYPE_ALIASES,
    )


def test_migrate_normalizes_schema_without_mutating_input():
    entries = [
        {
            "id": "legacy",
            "type": "cred",
            "category": "unknown",
            "severity": " HIGH ",
            "position": 7,
        }
    ]
    original = [dict(entry) for entry in entries]

    migrated, changed = _migrate(entries)

    assert changed is True
    assert migrated == [
        {
            "id": "legacy",
            "type": "credentials",
            "category": "misc",
            "severity": "high",
            "position": 0,
        }
    ]
    assert entries == original
    assert migrated[0] is not entries[0]


def test_migrate_assigns_stable_positions_per_category():
    entries = [
        {"id": "late", "type": "note", "category": "recon", "severity": "info", "position": 8},
        {"id": "first", "type": "note", "category": "recon", "severity": "info", "position": 2},
        {"id": "access", "type": "note", "category": "access", "severity": "info", "position": 4},
    ]

    migrated, changed = _migrate(entries)

    assert changed is True
    positions = {entry["id"]: entry["position"] for entry in migrated}
    assert positions == {"late": 1, "first": 0, "access": 0}


def test_migrate_reports_unchanged_for_normalized_entries():
    entries = [
        {"id": "one", "type": "note", "category": "recon", "severity": "info", "position": 0},
        {"id": "two", "type": "note", "category": "recon", "severity": "low", "position": 1},
    ]

    migrated, changed = _migrate(entries)

    assert changed is False
    assert migrated == entries
    assert migrated is not entries

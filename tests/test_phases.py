"""Tests for centralized Phase taxonomy, normalization, and backwards compatibility."""

from core.phases import (
    Phase,
    PHASES,
    PHASES_BY_KEY,
    VALID_PHASE_KEYS,
    DEFAULT_PHASE_KEY,
    get_phase,
    normalize_phase_key,
)
from core.loot.manager import CATEGORIES, VALID_CATEGORY_IDS
from core.loot.migrator import LootMigrator
from core.validators import validate_quick_note_entry


def test_canonical_phases():
    """Verify all 6 canonical phases exist in proper order with expected fields."""
    assert len(PHASES) == 6
    expected_keys = ["recon", "access", "privesc", "postex", "scripts", "misc"]
    assert [p.key for p in PHASES] == expected_keys

    for idx, phase in enumerate(PHASES, start=1):
        assert isinstance(phase, Phase)
        assert phase.order == idx
        assert phase.short.isupper()
        assert len(phase.long) > 0
        assert phase.key in VALID_PHASE_KEYS
        assert PHASES_BY_KEY[phase.key] == phase


def test_normalization_and_get_phase():
    """Verify direct keys, case insensitivity, aliases, and fallbacks."""
    # Direct keys
    assert normalize_phase_key("recon") == "recon"
    assert normalize_phase_key("access") == "access"
    assert normalize_phase_key("privesc") == "privesc"
    assert normalize_phase_key("postex") == "postex"
    assert normalize_phase_key("scripts") == "scripts"
    assert normalize_phase_key("misc") == "misc"

    # Case insensitivity
    assert normalize_phase_key("RECON") == "recon"
    assert normalize_phase_key("Access") == "access"
    assert normalize_phase_key("  priveSC  ") == "privesc"

    # Aliases
    assert normalize_phase_key("initial") == "access"
    assert normalize_phase_key("init") == "access"
    assert normalize_phase_key("lateral") == "postex"
    assert normalize_phase_key("latmove") == "postex"
    assert normalize_phase_key("persist") == "postex"
    assert normalize_phase_key("poc") == "scripts"
    assert normalize_phase_key("script") == "scripts"
    assert normalize_phase_key("enum") == "recon"

    # Long names and legacy numbered strings
    assert normalize_phase_key("1. Reconnaissance & Enumeration") == "recon"
    assert normalize_phase_key("2. Initial Access & Exploitation") == "access"
    assert normalize_phase_key("Reconnaissance & Enumeration") == "recon"
    assert normalize_phase_key("Custom Scripts & PoCs") == "scripts"

    # Digits
    assert normalize_phase_key("1") == "recon"
    assert normalize_phase_key("2") == "access"
    assert normalize_phase_key("5") == "scripts"
    assert normalize_phase_key("6") == "misc"

    # Fallbacks for empty / invalid
    assert normalize_phase_key(None) == DEFAULT_PHASE_KEY
    assert normalize_phase_key("") == DEFAULT_PHASE_KEY
    assert normalize_phase_key("   ") == DEFAULT_PHASE_KEY
    assert normalize_phase_key("invalid_phase_name") == DEFAULT_PHASE_KEY

    # get_phase object retrieval
    phase_access = get_phase("initial")
    assert phase_access.key == "access"
    assert phase_access.short == "ACCESS"
    assert phase_access.long == "Initial Access & Exploitation"

    fallback_phase = get_phase("totally_unknown")
    assert fallback_phase.key == "misc"
    assert fallback_phase.short == "MISC"


def test_loot_manager_backward_compatibility():
    """Ensure CATEGORIES and VALID_CATEGORY_IDS in core.loot.manager remain compatible."""
    assert len(CATEGORIES) == 6
    assert VALID_CATEGORY_IDS == {"recon", "access", "privesc", "postex", "scripts", "misc"}

    # Exact legacy titles check
    assert CATEGORIES[0]["name"] == "1. Reconnaissance & Enumeration"
    assert CATEGORIES[1]["name"] == "2. Initial Access & Exploitation"
    assert CATEGORIES[2]["name"] == "3. Privilege Escalation"
    assert CATEGORIES[3]["name"] == "4. Post-Exploitation & Lateral Movement"
    assert CATEGORIES[4]["name"] == "5. Custom Scripts & PoCs"
    assert CATEGORIES[5]["name"] == "6. Miscellaneous"


def test_loot_migrator_preserves_legacy_and_aliases():
    """Verify LootMigrator normalizes legacy and alias category strings to canonical keys."""
    entries = [
        {"id": "e1", "title": "Scan", "category": "1. Reconnaissance & Enumeration", "severity": "info", "type": "note"},
        {"id": "e2", "title": "Shell", "category": "initial", "severity": "high", "type": "credentials"},
        {"id": "e3", "title": "Passwd", "category": "lateral", "severity": "medium", "type": "hash"},
        {"id": "e4", "title": "Exploit", "category": "poc", "severity": "info", "type": "note"},
        {"id": "e5", "title": "Unknown", "category": "bogus_cat", "severity": "info", "type": "note"},
    ]

    normalized, changed = LootMigrator.migrate(
        entries,
        valid_category_ids=VALID_CATEGORY_IDS,
        type_aliases={"cred": "credentials"},
    )

    assert changed is True
    cat_by_id = {e["id"]: e["category"] for e in normalized}
    assert cat_by_id["e1"] == "recon"
    assert cat_by_id["e2"] == "access"
    assert cat_by_id["e3"] == "postex"
    assert cat_by_id["e4"] == "scripts"
    assert cat_by_id["e5"] == "misc"


def test_validators_quick_note_normalization():
    """Verify validate_quick_note_entry normalizes categories to canonical keys."""
    res_alias = validate_quick_note_entry({"text": "Test note", "category": "initial"})
    assert res_alias is not None
    assert res_alias["category"] == "access"

    res_legacy = validate_quick_note_entry({"text": "Test note", "category": "1. Reconnaissance & Enumeration"})
    assert res_legacy is not None
    assert res_legacy["category"] == "recon"

    res_unknown = validate_quick_note_entry({"text": "Test note", "category": "unknown_value"})
    assert res_unknown is not None
    assert res_unknown["category"] == "misc"

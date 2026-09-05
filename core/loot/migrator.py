"""Schema normalization for persisted loot entries."""

from typing import Any, Collection, Dict, List, Mapping, Tuple

from core.phases import normalize_phase_key
from core.validators import VALID_SEVERITIES


class LootMigrator:
    """Normalize legacy loot data without mutating caller-owned entries."""

    @staticmethod
    def migrate(
        entries: List[Dict[str, Any]],
        *,
        valid_category_ids: Collection[str],
        type_aliases: Mapping[str, str],
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Return ``(normalized_entries, changed)`` for a loot entry list."""
        normalized_entries = [dict(entry) for entry in entries]
        changed = False

        for entry in normalized_entries:
            category = entry.get("category")
            normalized_cat = normalize_phase_key(category)
            if normalized_cat not in valid_category_ids:
                normalized_cat = "misc"
            if normalized_cat != category:
                entry["category"] = normalized_cat
                changed = True

            severity = entry.get("severity")
            normalized_severity = str(severity).lower().strip() if severity else "info"
            if normalized_severity not in VALID_SEVERITIES:
                normalized_severity = "info"
            if normalized_severity != severity:
                entry["severity"] = normalized_severity
                changed = True

            entry_type = entry.get("type")
            normalized_type = type_aliases.get(str(entry_type).lower(), entry_type)
            if normalized_type != entry_type:
                entry["type"] = normalized_type
                changed = True

        for category_id in valid_category_ids:
            category_entries = sorted(
                (
                    entry
                    for entry in normalized_entries
                    if entry.get("category") == category_id
                ),
                key=lambda item: item.get("position", 0),
            )
            for position, entry in enumerate(category_entries):
                if entry.get("position") != position:
                    entry["position"] = position
                    changed = True

        return normalized_entries, changed

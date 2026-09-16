"""
Pure Python filter and aggregation functions for loot items.

Completely decoupled from Qt and UI widgets for fast in-memory execution and testing.
"""

from typing import Any, Dict, List, Mapping, Optional, Sequence


TYPE_ALIASES: Dict[str, str] = {
    "cred": "credentials",
    "credential": "credentials",
    "pass": "credentials",
    "password": "credentials",
    "screenshot": "screenshot",
    "screen": "screenshot",
    "flag": "flag",
    "hash": "hash",
    "note": "note",
    "text": "note",
    "finding": "finding",
}


def _entry_targets(entry: Mapping[str, Any]) -> list[str]:
    values = entry.get("targets")
    targets = (
        [str(value) for value in values if str(value)] if isinstance(values, (list, tuple)) else []
    )
    primary = str(entry.get("target_ip", "") or "")
    if primary and primary not in targets:
        targets.insert(0, primary)
    return targets


def filter_loot_entries(
    entries: Sequence[Mapping[str, Any]],
    target_ip: Optional[str] = None,
    entry_type: Optional[str] = None,
    category: Optional[str] = None,
    search_query: str = "",
) -> List[Dict[str, Any]]:
    """Keep untargeted global loot visible in target views.

    Type aliases normalize comparisons; defensive result copies preserve input values and order.
    """
    if not entries:
        return []

    results = entries

    if target_ip and target_ip != "all":
        results = [e for e in results if target_ip in _entry_targets(e) or not _entry_targets(e)]

    if entry_type and entry_type != "all":
        norm_type = TYPE_ALIASES.get(entry_type.lower(), entry_type)
        results = [
            e
            for e in results
            if TYPE_ALIASES.get(str(e.get("type", "")).lower(), e.get("type")) == norm_type
        ]

    if category and category != "all":
        results = [e for e in results if e.get("category") == category]

    if search_query and search_query.strip():
        q = search_query.strip().lower()
        matched = []
        for e in results:
            title = str(e.get("title", "")).lower()
            content = str(e.get("content", "")).lower()
            targets = " ".join(_entry_targets(e)).lower()
            cat = str(e.get("category", "")).lower()
            recommendation = str(e.get("recommendation", "")).lower()
            cvss = f"{e.get('cvss_score', '')} {e.get('cvss_vector', '')}".lower()
            reference_values = e.get("references")
            if not isinstance(reference_values, (list, tuple)):
                reference_values = []
            references = " ".join(str(value) for value in reference_values).lower()
            if (
                q in title
                or q in content
                or q in targets
                or q in cat
                or q in recommendation
                or q in cvss
                or q in references
            ):
                matched.append(e)
        results = matched

    return [dict(e) for e in results]


def count_loot_by_type(
    entries: Sequence[Mapping[str, Any]],
    type_definitions: Sequence[Mapping[str, Any]],
    target_ip: Optional[str] = None,
) -> Dict[str, int]:
    """Computes entry count per loot type."""
    filtered = filter_loot_entries(entries, target_ip=target_ip)
    counts: Dict[str, int] = {"all": len(filtered)}
    for t in type_definitions:
        tid = t.get("id")
        if tid:
            counts[tid] = sum(1 for e in filtered if e.get("type") == tid)
    return counts


def count_loot_by_category(
    entries: Sequence[Mapping[str, Any]],
    category_definitions: Sequence[Mapping[str, Any]],
    target_ip: Optional[str] = None,
) -> Dict[str, int]:
    """Computes entry count per loot category."""
    filtered = filter_loot_entries(entries, target_ip=target_ip)
    counts: Dict[str, int] = {"all": len(filtered)}
    for c in category_definitions:
        cid = c.get("id")
        if cid:
            counts[cid] = sum(1 for e in filtered if e.get("category") == cid)
    return counts

"""Normalization for optional report-finding metadata stored with Loot."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Optional


VALID_FINDING_STATUSES = {
    "open",
    "in_progress",
    "resolved",
    "accepted_risk",
}
MAX_CVSS_VECTOR_LENGTH = 256
MAX_FINDING_TARGETS = 64
MAX_FINDING_REFERENCES = 128
MAX_FINDING_TARGET_LENGTH = 128
MAX_FINDING_REFERENCE_LENGTH = 2_048


def normalize_cvss_score(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return round(score, 1) if 0.0 <= score <= 10.0 else None


def normalize_finding_status(value: Any) -> str:
    status = str(value or "open").strip().lower()
    return status if status in VALID_FINDING_STATUSES else "open"


def normalize_finding_targets(
    value: Any,
    *,
    fallback_target: str = "",
) -> list[str]:
    if isinstance(value, str):
        candidates: Iterable[Any] = re.split(r"[,;\r\n]+", value)
    elif isinstance(value, (list, tuple, set)):
        candidates = value
    else:
        candidates = ()
    normalized = _normalize_string_list(candidates, MAX_FINDING_TARGETS, MAX_FINDING_TARGET_LENGTH)
    fallback = str(fallback_target or "").strip()[:MAX_FINDING_TARGET_LENGTH]
    if not normalized and fallback:
        normalized = [fallback]
    return normalized


def normalize_finding_references(value: Any) -> list[str]:
    if isinstance(value, str):
        candidates: Iterable[Any] = value.splitlines()
    elif isinstance(value, (list, tuple, set)):
        candidates = value
    else:
        candidates = ()
    return _normalize_string_list(candidates, MAX_FINDING_REFERENCES, MAX_FINDING_REFERENCE_LENGTH)


def normalize_cvss_vector(value: Any) -> str:
    return str(value or "").strip()[:MAX_CVSS_VECTOR_LENGTH]


def normalize_finding_metadata(
    value: Mapping[str, Any],
    *,
    fallback_target: str = "",
) -> dict[str, Any]:
    return {
        "targets": normalize_finding_targets(value.get("targets"), fallback_target=fallback_target),
        "cvss_score": normalize_cvss_score(value.get("cvss_score")),
        "cvss_vector": normalize_cvss_vector(value.get("cvss_vector")),
        "finding_status": normalize_finding_status(value.get("finding_status")),
        "references": normalize_finding_references(value.get("references")),
    }


def _normalize_string_list(values: Iterable[Any], limit: int, item_length: int) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()[:item_length]
        if not item or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
        if len(normalized) >= limit:
            break
    return normalized

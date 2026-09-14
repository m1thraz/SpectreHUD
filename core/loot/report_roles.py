"""Report participation semantics for captured Loot."""

from __future__ import annotations

from typing import Any, Mapping


REPORT_ROLE_EVIDENCE = "evidence"
REPORT_ROLE_FINDING = "finding"
REPORT_ROLE_LEGACY = "legacy"
VALID_REPORT_ROLES = {
    REPORT_ROLE_EVIDENCE,
    REPORT_ROLE_FINDING,
    REPORT_ROLE_LEGACY,
}


def normalize_report_role(value: Any, *, missing_is_legacy: bool = False) -> str:
    """Normalize persisted roles while preserving pre-role Loot compatibility."""
    if value is None and missing_is_legacy:
        return REPORT_ROLE_LEGACY
    role = str(value or REPORT_ROLE_EVIDENCE).strip().lower()
    return role if role in VALID_REPORT_ROLES else REPORT_ROLE_EVIDENCE


def is_report_finding_entry(entry: Mapping[str, Any]) -> bool:
    """Return whether Loot participates as a standalone generated finding."""
    role = normalize_report_role(
        entry.get("report_role"),
        missing_is_legacy="report_role" not in entry,
    )
    return role in {REPORT_ROLE_FINDING, REPORT_ROLE_LEGACY}

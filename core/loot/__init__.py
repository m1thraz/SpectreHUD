"""
Loot domain package for SpectreHUD.

Provides finding/loot storage, lifecycle management, validation,
filtering, aggregation, and legacy migration.
"""

from core.loot.manager import (
    CATEGORIES,
    LOOT_TYPES,
    VALID_CATEGORY_IDS,
    LootLimitError,
    LootManager,
    LootValidationError,
)
from core.loot.migrator import LootMigrator
from core.loot.filter import (
    count_loot_by_category,
    count_loot_by_type,
    filter_loot_entries,
)
from core.loot.report_roles import (
    REPORT_ROLE_EVIDENCE,
    REPORT_ROLE_FINDING,
    REPORT_ROLE_LEGACY,
    VALID_REPORT_ROLES,
    is_report_finding_entry,
    normalize_report_role,
)

__all__ = [
    "CATEGORIES",
    "LOOT_TYPES",
    "VALID_CATEGORY_IDS",
    "LootLimitError",
    "LootManager",
    "LootMigrator",
    "LootValidationError",
    "REPORT_ROLE_EVIDENCE",
    "REPORT_ROLE_FINDING",
    "REPORT_ROLE_LEGACY",
    "VALID_REPORT_ROLES",
    "count_loot_by_category",
    "count_loot_by_type",
    "filter_loot_entries",
    "is_report_finding_entry",
    "normalize_report_role",
]

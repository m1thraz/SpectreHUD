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

__all__ = [
    "CATEGORIES",
    "LOOT_TYPES",
    "VALID_CATEGORY_IDS",
    "LootLimitError",
    "LootManager",
    "LootMigrator",
    "LootValidationError",
    "count_loot_by_category",
    "count_loot_by_type",
    "filter_loot_entries",
]

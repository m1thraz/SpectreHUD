"""Typed, headless workflow for promoting captured Loot to a report finding."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, Sequence

from core.reporting.finding_conversion import (
    finding_from_loot_entry,
    supporting_evidence_from_loot_entry,
)
from core.reporting.workspace_model import ReportFindingItem
from core.storage import StorageError


class LootFindingPromotionStore(Protocol):
    """Minimal Loot API required by the report promotion workflow."""

    def get_all_entries(self) -> list[dict[str, Any]]: ...

    def assign_report_roles(
        self,
        finding_entry_id: str,
        evidence_entry_ids: list[str],
    ) -> Optional[dict[str, Any]]: ...


class FindingPromotionFailureReason(str, Enum):
    PRIMARY_NOT_FOUND = "primary_not_found"
    EVIDENCE_NOT_FOUND = "evidence_not_found"
    PERSISTENCE_FAILED = "persistence_failed"
    UNEXPECTED_ERROR = "unexpected_error"


@dataclass(frozen=True)
class FindingPromotionResult:
    success: bool
    finding: Optional[ReportFindingItem] = None
    failure_reason: Optional[FindingPromotionFailureReason] = None
    detail: str = ""

    @classmethod
    def failed(
        cls,
        reason: FindingPromotionFailureReason,
        *,
        detail: str = "",
    ) -> "FindingPromotionResult":
        return cls(success=False, failure_reason=reason, detail=detail)


class FindingPromotionService:
    """Promote one Loot entry and bundle other entries as supporting evidence."""

    def promote(
        self,
        *,
        loot_store: LootFindingPromotionStore,
        primary_id: str,
        evidence_ids: Sequence[str] = (),
        fallback_title: str = "New Finding",
    ) -> FindingPromotionResult:
        entries = self._index_entries(loot_store.get_all_entries())
        primary = entries.get(str(primary_id))
        if primary is None:
            return FindingPromotionResult.failed(
                FindingPromotionFailureReason.PRIMARY_NOT_FOUND,
                detail=str(primary_id),
            )

        normalized_evidence_ids = tuple(
            dict.fromkeys(
                str(entry_id)
                for entry_id in evidence_ids
                if str(entry_id) and str(entry_id) != str(primary_id)
            )
        )
        missing_ids = [
            entry_id for entry_id in normalized_evidence_ids if entry_id not in entries
        ]
        if missing_ids:
            return FindingPromotionResult.failed(
                FindingPromotionFailureReason.EVIDENCE_NOT_FOUND,
                detail=", ".join(missing_ids),
            )

        try:
            promoted = loot_store.assign_report_roles(
                str(primary_id), list(normalized_evidence_ids)
            )
        except (StorageError, OSError) as exc:
            return FindingPromotionResult.failed(
                FindingPromotionFailureReason.PERSISTENCE_FAILED,
                detail=str(exc),
            )
        except Exception as exc:
            return FindingPromotionResult.failed(
                FindingPromotionFailureReason.UNEXPECTED_ERROR,
                detail=str(exc),
            )
        if promoted is None:
            return FindingPromotionResult.failed(
                FindingPromotionFailureReason.PRIMARY_NOT_FOUND,
                detail=str(primary_id),
            )

        finding = finding_from_loot_entry(promoted, fallback_title=fallback_title)
        existing_sources = {
            evidence.source_loot_id for evidence in finding.evidence_items
        }
        for entry_id in normalized_evidence_ids:
            evidence = supporting_evidence_from_loot_entry(entries[entry_id])
            if evidence is None or evidence.source_loot_id in existing_sources:
                continue
            finding.attach_evidence(evidence, insert_into_description=True)
            existing_sources.add(evidence.source_loot_id)
        return FindingPromotionResult(success=True, finding=finding)

    @staticmethod
    def _index_entries(
        entries: Sequence[Mapping[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        return {
            str(entry["id"]): dict(entry)
            for entry in entries
            if entry.get("id")
        }

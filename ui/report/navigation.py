"""Typed navigation contract shared by Report Workspace UI components."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ReportLocationKind(str, Enum):
    READINESS = "readiness"
    METADATA = "metadata"
    SECTION = "section"
    FINDING = "finding"
    FINDINGS_OVERVIEW = "findings_overview"
    PHASE_GROUP = "phase_group"
    NARRATIVES_ROOT = "narratives_root"
    RAW_MARKDOWN = "raw_markdown"


@dataclass(frozen=True)
class ReportLocation:
    """A semantic destination in the structured report workspace."""

    kind: ReportLocationKind
    identity: Optional[str] = None

    @classmethod
    def from_legacy(cls, view_type: str, item_id: Optional[str] = None) -> "ReportLocation":
        return cls(ReportLocationKind(view_type), item_id)

    @classmethod
    def finding(cls, finding_id: str) -> "ReportLocation":
        return cls(ReportLocationKind.FINDING, finding_id)

    def as_legacy_tuple(self) -> tuple[str, Optional[str]]:
        return self.kind.value, self.identity

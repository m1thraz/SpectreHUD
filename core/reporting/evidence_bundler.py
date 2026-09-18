"""
Evidence bundler for SpectreHUD.

Provides pure Python anchor-based related evidence suggestion without depending
on Qt, UI, or persistent storage modifications.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Literal, Mapping, Optional, Sequence, Set, Tuple, Union

SourceType = Literal["screenshot", "clipboard", "quick_note", "loot"]
# Canonical key is (source_type, entry_id) to prevent cross-source ID collisions.
# Raw string ID is supported strictly as a legacy fallback.
AlreadyAttachedKey = Union[Tuple[SourceType, str], str]

EVIDENCE_PROXIMITY_SECONDS: int = 90
EVIDENCE_UNSCOPED_PROXIMITY_SECONDS: int = 45


@dataclass(frozen=True)
class EvidenceCandidate:
    """Explicitly typed evidence candidate for correlation."""

    source_type: SourceType
    entry: Mapping[str, Any]

    @property
    def id(self) -> str:
        return str(self.entry.get("id") or "")


@dataclass(frozen=True)
class EvidenceSuggestion:
    """Suggested supporting evidence item correlated with the anchor."""

    candidate: EvidenceCandidate
    time_delta_seconds: float
    is_cross_source: bool


def get_phase_id(entry: Mapping[str, Any]) -> str:
    """Central normalizer for pentest phase identifier."""
    val = entry.get("phase_id") or entry.get("category") or ""
    return str(val).strip().lower()


def get_target(entry: Mapping[str, Any]) -> str:
    """Central normalizer for target IP or host scope."""
    return str(entry.get("target_ip") or "").strip()


def parse_entry_datetime(entry: Mapping[str, Any]) -> Optional[datetime]:
    """
    Parses entry timestamp strictly against the two known SpectreHUD formats:
    - Standard 24h: '%Y-%m-%d %H:%M:%S'
    - Legacy 12h: '%Y-%m-%d %I:%M:%S %p'
    """
    raw = str(entry.get("timestamp") or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M:%S %p"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    return None


def is_target_compatible(anchor_target: str, cand_target: str) -> Tuple[bool, bool]:
    """
    Evaluates target scope compatibility between anchor and candidate.
    Returns:
        (compatible: bool, is_unscoped: bool)
    """
    if anchor_target and cand_target:
        return (anchor_target == cand_target, False)
    if anchor_target and not cand_target:
        # Candidate has empty target; allows attaching to known anchor target
        return (True, False)
    if not anchor_target and cand_target:
        # Anchor has no target, but candidate belongs to specific target -> reject
        return (False, False)
    # Both targets empty -> allowed only in defensive tighter window
    return (True, True)


def is_phase_compatible(anchor_phase: str, cand_phase: str) -> Tuple[bool, bool]:
    """
    Evaluates pentest phase compatibility between anchor and candidate.
    Returns:
        (compatible: bool, is_unscoped: bool)
    """
    if anchor_phase and cand_phase:
        return (anchor_phase == cand_phase, False)
    if anchor_phase and not cand_phase:
        # Candidate has no phase tag -> allowed defensively with tighter window
        return (True, True)
    if not anchor_phase and cand_phase:
        # Anchor has no phase tag, but candidate belongs to specific phase -> reject
        return (False, False)
    # Both phases empty -> allowed only in defensive tighter window
    return (True, True)


def suggest_related_evidence(
    anchor: EvidenceCandidate,
    candidates: Sequence[EvidenceCandidate],
    *,
    already_attached_keys: Optional[Set[AlreadyAttachedKey]] = None,
    proximity_seconds: int = EVIDENCE_PROXIMITY_SECONDS,
    unscoped_proximity_seconds: int = EVIDENCE_UNSCOPED_PROXIMITY_SECONDS,
) -> List[EvidenceSuggestion]:
    """
    Suggests candidates that temporally and contextually correlate with the anchor.

    Returns all valid matching candidates without an arbitrary core-level limit,
    enabling presentation-level progressive disclosure or full batch operations.

    Rules:
    - Never suggests the anchor itself.
    - Excludes items present in already_attached_keys (canonical (source_type, id)
      tuples checked first, with raw id strings supported as legacy fallback).
    - Excludes pure clipboard -> clipboard sequences.
    - Requires target and phase compatibility.
    - Enforces proximity window (defensively reduced when target or phase is unscoped).
    - Ranks cross-source suggestions first, then by temporal proximity.
    """
    anchor_dt = parse_entry_datetime(anchor.entry)
    if anchor_dt is None:
        return []

    anchor_target = get_target(anchor.entry)
    anchor_phase = get_phase_id(anchor.entry)
    attached_set = already_attached_keys or set()

    suggestions: List[EvidenceSuggestion] = []

    for cand in candidates:
        c_id = cand.id
        if not c_id or c_id == anchor.id:
            continue

        # Check canonical (source_type, id) tuple first; fallback to legacy raw id
        if (cand.source_type, c_id) in attached_set or c_id in attached_set:
            continue

        # Rule: Exclude pure clipboard -> clipboard series
        if anchor.source_type == "clipboard" and cand.source_type == "clipboard":
            continue

        cand_dt = parse_entry_datetime(cand.entry)
        if cand_dt is None:
            continue

        target_ok, target_unscoped = is_target_compatible(anchor_target, get_target(cand.entry))
        if not target_ok:
            continue

        phase_ok, phase_unscoped = is_phase_compatible(anchor_phase, get_phase_id(cand.entry))
        if not phase_ok:
            continue

        max_dt = (
            unscoped_proximity_seconds
            if (target_unscoped or phase_unscoped)
            else proximity_seconds
        )

        dt = abs((cand_dt - anchor_dt).total_seconds())
        if dt > max_dt:
            continue

        is_cross = cand.source_type != anchor.source_type
        suggestions.append(
            EvidenceSuggestion(
                candidate=cand,
                time_delta_seconds=dt,
                is_cross_source=is_cross,
            )
        )

    # Ranking: cross-source first (0 before 1), then smallest time delta
    suggestions.sort(key=lambda s: (0 if s.is_cross_source else 1, s.time_delta_seconds))
    return suggestions

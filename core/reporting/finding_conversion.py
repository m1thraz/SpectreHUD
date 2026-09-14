"""Canonical conversion from captured Loot into structured report findings."""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from core.phases import normalize_phase_key
from core.reporting.evidence_markers import replace_evidence_block
from core.reporting.workspace_model import ReportEvidenceItem, ReportFindingItem


_IMAGE_TARGET_RE = re.compile(r"^!\[.*?\]\((.*?)\)$", re.DOTALL)
_VALID_STATUSES = {"open", "in_progress", "resolved", "accepted_risk"}


def evidence_from_loot_entry(entry: Mapping[str, Any]) -> Optional[ReportEvidenceItem]:
    """Convert evidence-shaped Loot while retaining its stable source identity."""
    entry_type = str(entry.get("type", "note") or "note").lower()
    entry_id = str(entry.get("id", "") or "")
    title = str(entry.get("title", "") or "")
    content = str(entry.get("content", "") or "").strip()
    if not content:
        return None

    if entry_type in {"screenshot", "image"}:
        image_match = _IMAGE_TARGET_RE.match(content)
        return ReportEvidenceItem(
            id=f"{entry_id}-evidence" if entry_id else "loot-evidence",
            type="screenshot",
            caption=title or "Screenshot",
            content=image_match.group(1) if image_match else content,
            source_loot_id=entry_id or None,
        )
    if entry_type in {"credential", "credentials", "hash", "flag"}:
        return ReportEvidenceItem(
            id=f"{entry_id}-evidence" if entry_id else "loot-evidence",
            type="credential",
            caption=title or entry_type.capitalize(),
            content=content,
            source_loot_id=entry_id or None,
            language=entry_type,
        )
    return None


def finding_from_loot_entry(
    entry: Mapping[str, Any],
    *,
    fallback_title: str = "New Finding",
) -> ReportFindingItem:
    """Map every supported Loot field through one loss-aware conversion boundary."""
    from core.reporting.loot_sync import format_loot_marker, loot_content_hash

    entry_id = str(entry.get("id", "") or "")
    target_values = entry.get("targets")
    if isinstance(target_values, (list, tuple)):
        targets = [str(value).strip() for value in target_values if str(value).strip()]
    else:
        target = str(entry.get("target_ip", "") or "").strip()
        targets = [target] if target else []

    references_value = entry.get("references")
    references = (
        [str(value).strip() for value in references_value if str(value).strip()]
        if isinstance(references_value, (list, tuple))
        else []
    )
    status = str(entry.get("finding_status", "open") or "open").lower()
    if status not in _VALID_STATUSES:
        status = "open"

    cvss_score = None
    try:
        if entry.get("cvss_score") not in (None, ""):
            candidate = float(entry["cvss_score"])
            cvss_score = candidate if 0.0 <= candidate <= 10.0 else None
    except (TypeError, ValueError):
        pass

    evidence = evidence_from_loot_entry(entry)
    content = str(entry.get("content", "") or "").strip()
    description = evidence.to_persisted_markdown() if evidence else content
    return ReportFindingItem(
        id=entry_id,
        title=str(entry.get("title", "") or fallback_title),
        severity=str(entry.get("severity", "info") or "info").lower(),
        cvss_score=cvss_score,
        cvss_vector=str(entry.get("cvss_vector", "") or "").strip() or None,
        status=status,
        phase=normalize_phase_key(entry.get("phase") or entry.get("category") or "recon"),
        targets=targets,
        timestamp=str(entry.get("timestamp", "") or "").strip() or None,
        description=description,
        evidence_items=[evidence] if evidence else [],
        recommendation=str(entry.get("recommendation", "") or "").strip(),
        references=references,
        loot_marker=(format_loot_marker(entry_id, loot_content_hash(entry)) if entry_id else None),
    )


def duplicate_report_finding(
    finding: ReportFindingItem,
    *,
    new_id: str,
    title: Optional[str] = None,
) -> ReportFindingItem:
    """Clone a finding while keeping embedded evidence identities internally consistent."""
    description = finding.description
    evidence_items = []
    for index, item in enumerate(finding.evidence_items, start=1):
        duplicate = ReportEvidenceItem(
            id=f"{new_id}-ev-{index}",
            type=item.type,
            caption=item.caption,
            content=item.content,
            source_loot_id=item.source_loot_id,
            language=item.language,
        )
        description, _ = replace_evidence_block(
            description,
            item.id,
            duplicate.to_persisted_markdown(),
        )
        evidence_items.append(duplicate)

    return ReportFindingItem(
        id=new_id,
        title=finding.title if title is None else title,
        severity=finding.severity,
        cvss_score=finding.cvss_score,
        cvss_vector=finding.cvss_vector,
        status=finding.status,
        phase=finding.phase,
        targets=list(finding.targets),
        timestamp=finding.timestamp,
        description=description,
        evidence_items=evidence_items,
        recommendation=finding.recommendation,
        references=list(finding.references),
        raw_extra=finding.raw_extra,
    )

"""Selective, headless reconciliation of Loot-backed report findings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from typing import Any, Iterable, Mapping, Optional

from core.reporting.findings import FINDING_END_RE, FINDING_START_RE
from core.reporting.loot_sync import (
    MARKER_REGEX,
    append_missing_loot_to_text,
    classify_loot_report_state,
    extract_report_markers,
    format_loot_marker,
    loot_content_hash,
)
from core.reporting.report_finding import ReportFindingItem


class LootDifferenceKind(str, Enum):
    CHANGED = "changed"
    REPORT_ONLY = "report_only"


class LootReconciliationAction(str, Enum):
    LATER = "later"
    ACCEPT_REPORT = "accept_report"
    APPLY_LOOT = "apply_loot"
    KEEP_BOTH = "keep_both"
    DETACH_REPORT = "detach_report"
    DELETE_REPORT = "delete_report"


@dataclass(frozen=True)
class LootReconciliationItem:
    entry_id: str
    kind: LootDifferenceKind
    report_title: str
    loot_title: str = ""
    resolvable: bool = True
    report_hash: str = ""
    loot_hash: str = ""


@dataclass(frozen=True)
class LootReconciliationSelection:
    action: LootReconciliationAction
    expected_report_hash: str
    expected_loot_hash: str = ""


@dataclass(frozen=True)
class LootReconciliationResult:
    text: str
    resolved_count: int = 0
    replaced_count: int = 0
    accepted_count: int = 0
    duplicated_count: int = 0
    detached_count: int = 0
    deleted_count: int = 0
    added_count: int = 0
    used_fallback: bool = False
    fallback_categories: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.resolved_count or self.added_count)


class LootReconciliationError(ValueError):
    """Raised before mutation when a requested reconciliation is unsafe."""


@dataclass(frozen=True)
class _FindingBlock:
    start: int
    end: int
    finding_id: str
    markdown: str


_ALLOWED_ACTIONS = {
    LootDifferenceKind.CHANGED: {
        LootReconciliationAction.LATER,
        LootReconciliationAction.ACCEPT_REPORT,
        LootReconciliationAction.APPLY_LOOT,
        LootReconciliationAction.KEEP_BOTH,
    },
    LootDifferenceKind.REPORT_ONLY: {
        LootReconciliationAction.LATER,
        LootReconciliationAction.DETACH_REPORT,
        LootReconciliationAction.DELETE_REPORT,
    },
}


def _finding_blocks(markdown: str) -> list[_FindingBlock]:
    blocks: list[_FindingBlock] = []
    cursor = 0
    while start := FINDING_START_RE.search(markdown, cursor):
        next_start = FINDING_START_RE.search(markdown, start.end())
        end = next(
            (
                candidate
                for candidate in FINDING_END_RE.finditer(markdown, start.end())
                if candidate.group(1) == start.group(1)
            ),
            None,
        )
        if end is None or (next_start is not None and next_start.start() < end.start()):
            cursor = start.end()
            continue
        blocks.append(
            _FindingBlock(
                start=start.start(),
                end=end.end(),
                finding_id=start.group(1),
                markdown=markdown[start.start() : end.end()],
            )
        )
        cursor = end.end()
    return blocks


def _blocks_by_loot_id(markdown: str) -> dict[str, _FindingBlock]:
    result: dict[str, _FindingBlock] = {}
    for block in _finding_blocks(markdown):
        for marker in MARKER_REGEX.finditer(block.markdown):
            result[marker.group(1)] = block
    return result


def _report_snapshot(block: Optional[_FindingBlock], marker_hash: str) -> str:
    if block is None:
        return marker_hash
    return hashlib.sha256(block.markdown.encode("utf-8")).hexdigest()[:16]


def analyze_loot_reconciliation(
    markdown: str,
    loot_entries: Iterable[Mapping[str, Any]],
) -> tuple[LootReconciliationItem, ...]:
    entries = [dict(entry) for entry in loot_entries]
    state = classify_loot_report_state(markdown, entries)
    markers = extract_report_markers(markdown)
    blocks = _blocks_by_loot_id(markdown)
    items: list[LootReconciliationItem] = []

    for entry in state.stale:
        entry_id = str(entry.get("id", "") or "")
        block = blocks.get(entry_id)
        report_title = entry_id
        if block is not None:
            report_title = (
                ReportFindingItem.from_markdown(
                    block.markdown, block.finding_id
                ).title
                or entry_id
            )
        items.append(
            LootReconciliationItem(
                entry_id=entry_id,
                kind=LootDifferenceKind.CHANGED,
                report_title=report_title,
                loot_title=str(entry.get("title", "") or entry_id),
                resolvable=block is not None,
                report_hash=_report_snapshot(block, markers.get(entry_id, "")),
                loot_hash=loot_content_hash(entry),
            )
        )

    for entry_id in state.orphaned_ids:
        block = blocks.get(entry_id)
        report_title = entry_id
        if block is not None:
            report_title = (
                ReportFindingItem.from_markdown(
                    block.markdown, block.finding_id
                ).title
                or entry_id
            )
        items.append(
            LootReconciliationItem(
                entry_id=entry_id,
                kind=LootDifferenceKind.REPORT_ONLY,
                report_title=report_title,
                resolvable=block is not None,
                report_hash=_report_snapshot(block, markers.get(entry_id, "")),
            )
        )
    return tuple(items)


def _replace_marker(block: str, entry_id: str, replacement: str) -> str:
    marker = re.compile(
        rf"<!--\s*spectre:loot:{re.escape(entry_id)}:[a-fA-F0-9]+\s*-->"
    )
    updated, count = marker.subn(replacement, block, count=1)
    if count != 1:
        raise LootReconciliationError(f"Loot marker '{entry_id}' is not unique in its finding")
    return updated


def _detach_block(block: _FindingBlock, entry_id: str, new_id: Optional[str] = None) -> str:
    updated = _replace_marker(block.markdown, entry_id, "")
    updated = re.sub(r"\n{3,}", "\n\n", updated, count=1)
    if new_id is not None:
        updated = updated.replace(
            f"<!-- spectre:finding:start:{block.finding_id} -->",
            f"<!-- spectre:finding:start:{new_id} -->",
            1,
        )
        updated = updated.replace(
            f"<!-- spectre:finding:end:{block.finding_id} -->",
            f"<!-- spectre:finding:end:{new_id} -->",
            1,
        )
    return updated


def _unique_report_id(entry_id: str, existing_ids: set[str]) -> str:
    base = f"report-{entry_id}"
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    existing_ids.add(candidate)
    return candidate


def reconcile_loot_report(
    report_text: str,
    loot_entries: Iterable[Mapping[str, Any]],
    decisions: Mapping[
        str, LootReconciliationAction | LootReconciliationSelection | str
    ],
    *,
    append_missing: bool = False,
    template: Any = None,
    language: str = "de",
) -> LootReconciliationResult:
    """Apply explicit per-finding decisions and optionally append missing Loot atomically."""
    entries = [dict(entry) for entry in loot_entries]
    entry_map = {
        str(entry.get("id", "") or ""): entry
        for entry in entries
        if entry.get("id")
    }
    items = {item.entry_id: item for item in analyze_loot_reconciliation(report_text, entries)}
    blocks = _blocks_by_loot_id(report_text)
    normalized: dict[str, LootReconciliationAction] = {}

    for entry_id, raw_action in decisions.items():
        selection = (
            raw_action if isinstance(raw_action, LootReconciliationSelection) else None
        )
        try:
            action = (
                selection.action
                if selection is not None
                else LootReconciliationAction(raw_action)
            )
        except ValueError as exc:
            raise LootReconciliationError(
                f"Unsupported reconciliation action for '{entry_id}'"
            ) from exc
        item = items.get(entry_id)
        if item is None:
            raise LootReconciliationError(f"Loot difference '{entry_id}' is no longer current")
        if not item.resolvable or entry_id not in blocks:
            raise LootReconciliationError(
                f"Finding '{entry_id}' has no safe structured boundary"
            )
        if action not in _ALLOWED_ACTIONS[item.kind]:
            raise LootReconciliationError(
                f"Action '{action.value}' is invalid for '{item.kind.value}'"
            )
        if selection is not None and (
            selection.expected_report_hash != item.report_hash
            or selection.expected_loot_hash != item.loot_hash
        ):
            raise LootReconciliationError(
                f"Loot difference '{entry_id}' changed while it was being reviewed"
            )
        normalized[entry_id] = action

    replacements: list[tuple[int, int, str]] = []
    reinsert_entries: list[dict[str, Any]] = []
    existing_ids = {match.group(1) for match in FINDING_START_RE.finditer(report_text)}
    accepted = replaced = duplicated = detached = deleted = 0

    for entry_id, action in normalized.items():
        if action is LootReconciliationAction.LATER:
            continue
        item = items[entry_id]
        block = blocks[entry_id]
        replacement = block.markdown
        if action is LootReconciliationAction.ACCEPT_REPORT:
            entry = entry_map[entry_id]
            replacement = _replace_marker(
                replacement,
                entry_id,
                format_loot_marker(entry_id, loot_content_hash(entry)),
            )
            accepted += 1
        elif action is LootReconciliationAction.APPLY_LOOT:
            entry = entry_map[entry_id]
            replacement = ""
            reinsert_entries.append(entry)
            replaced += 1
        elif action is LootReconciliationAction.KEEP_BOTH:
            entry = entry_map[entry_id]
            detached_id = _unique_report_id(entry_id, existing_ids)
            report_copy = _detach_block(block, entry_id, detached_id).rstrip()
            replacement = report_copy
            reinsert_entries.append(entry)
            duplicated += 1
        elif action is LootReconciliationAction.DETACH_REPORT:
            replacement = _detach_block(block, entry_id)
            detached += 1
        elif action is LootReconciliationAction.DELETE_REPORT:
            replacement = ""
            deleted += 1
        replacements.append((block.start, block.end, replacement))

    reconciled = report_text
    for start, end, replacement in sorted(replacements, reverse=True):
        reconciled = reconciled[:start] + replacement + reconciled[end:]

    if reinsert_entries:
        # Reuse structural insertion so a Loot-side phase change moves the fresh
        # version into the correct report section without reserializing the document.
        reconciled = append_missing_loot_to_text(
            reconciled,
            reinsert_entries,
            template=template,
            language=language,
        ).text

    append_result = append_missing_loot_to_text(
        reconciled,
        entries,
        template=template,
        language=language,
    ) if append_missing else None
    final_text = append_result.text if append_result is not None else reconciled
    resolved = accepted + replaced + duplicated + detached + deleted
    return LootReconciliationResult(
        text=final_text,
        resolved_count=resolved,
        replaced_count=replaced,
        accepted_count=accepted,
        duplicated_count=duplicated,
        detached_count=detached,
        deleted_count=deleted,
        added_count=append_result.added_count if append_result is not None else 0,
        used_fallback=append_result.used_fallback if append_result is not None else False,
        fallback_categories=(
            append_result.fallback_categories if append_result is not None else ()
        ),
    )

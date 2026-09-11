"""Pure state machine for Quick Note focus review triage sessions."""

from typing import Any, Dict, List, Optional, Set, Tuple


class QuickNoteReviewSession:
    """Manages review queue order, cycling, and completion metrics for focus review."""

    def __init__(self) -> None:
        self.queue_ids: List[str] = []
        self.seen_count: int = 0
        self.completed_count: int = 0
        self.total: int = 0
        self.cycle_notice_pending: bool = False

    def reset(self) -> None:
        self.queue_ids = []
        self.seen_count = 0
        self.completed_count = 0
        self.total = 0
        self.cycle_notice_pending = False

    @property
    def current_position(self) -> int:
        return min(self.seen_count + 1, self.total)

    def _initialize_queue(self, eligible: List[Dict[str, Any]]) -> None:
        self.queue_ids = [n["id"] for n in eligible if n.get("id")]
        self.total = len(self.queue_ids)

    def _prune_missing(self, valid_ids: Set[str]) -> None:
        self.queue_ids = [eid for eid in self.queue_ids if eid in valid_ids]

    def _recycle_queue(self, eligible: List[Dict[str, Any]]) -> bool:
        self.queue_ids = [n["id"] for n in eligible if n.get("id")]
        self.seen_count = 0
        self.total = len(self.queue_ids)
        if self.cycle_notice_pending:
            self.cycle_notice_pending = False
            return True
        return False

    def prepare_step(
        self, eligible: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Synchronizes queue against currently eligible notes and returns (active_entry, show_cycle_notice)."""
        entries_by_id = {n["id"]: n for n in eligible if n.get("id")}

        if not self.queue_ids and self.total == 0:
            self._initialize_queue(eligible)
        else:
            self._prune_missing(set(entries_by_id.keys()))

        show_cycle_notice = False
        if not self.queue_ids and eligible and self.total > 0:
            show_cycle_notice = self._recycle_queue(eligible)

        if not self.queue_ids:
            self.cycle_notice_pending = False
            return None, False

        return entries_by_id.get(self.queue_ids[0]), show_cycle_notice

    def advance(self, entry_id: str, *, completed: bool) -> None:
        if entry_id in self.queue_ids:
            self.queue_ids.remove(entry_id)
        self.seen_count += 1
        if completed:
            self.completed_count += 1
        if not self.queue_ids:
            self.cycle_notice_pending = True

    def skip_next(self) -> None:
        if not self.queue_ids:
            return
        self.queue_ids.pop(0)
        self.seen_count += 1
        if not self.queue_ids:
            self.cycle_notice_pending = True

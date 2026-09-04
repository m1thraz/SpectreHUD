"""Pure selection state for Quick Note bulk actions."""

from typing import AbstractSet, Iterable, Set


class NoteSelectionModel:
    """Track selected note IDs without depending on Qt widgets."""

    def __init__(self) -> None:
        self._selected_ids: Set[str] = set()

    @property
    def selected_ids(self) -> AbstractSet[str]:
        return frozenset(self._selected_ids)

    def __len__(self) -> int:
        return len(self._selected_ids)

    def __contains__(self, entry_id: str) -> bool:
        return entry_id in self._selected_ids

    def set_selected(self, entry_id: str, selected: bool) -> None:
        if selected:
            self._selected_ids.add(entry_id)
        else:
            self._selected_ids.discard(entry_id)

    def discard(self, entry_id: str) -> None:
        self._selected_ids.discard(entry_id)

    def retain(self, entry_ids: Iterable[str]) -> None:
        self._selected_ids.intersection_update(entry_ids)

    def clear(self) -> bool:
        had_selection = bool(self._selected_ids)
        self._selected_ids.clear()
        return had_selection

    def snapshot(self) -> Set[str]:
        return set(self._selected_ids)

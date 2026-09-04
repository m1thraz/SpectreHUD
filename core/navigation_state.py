"""
Pure Python navigation state machine for SpectreHUD.

Tracks mode transitions, cycling sequence, history stack, and dirty-state guards
completely independent of Qt UI widgets.
"""

from typing import List, Optional, Set


VALID_MODES: Set[str] = {"cheatsheet", "history", "notes", "loot", "report"}
TAB_CYCLE_MODES: List[str] = ["cheatsheet", "history", "notes", "loot"]


class NavigationStateMachine:
    """
    Manages active mode state and navigation transitions without Qt dependencies.
    """

    def __init__(self, initial_mode: str = "cheatsheet", max_history: int = 50):
        self._active_mode: str = initial_mode if initial_mode in VALID_MODES else "cheatsheet"
        self._history: List[str] = [self._active_mode]
        self._max_history = max_history

    @property
    def active_mode(self) -> str:
        return self._active_mode

    @property
    def history(self) -> List[str]:
        return list(self._history)

    def can_switch_mode(self, target_mode: str, report_is_dirty: bool = False) -> bool:
        """Checks if a transition to target_mode is permitted."""
        if target_mode not in VALID_MODES:
            return False
        # Guard against unconfirmed navigation away from dirty report
        if self._active_mode == "report" and target_mode != "report" and report_is_dirty:
            return False
        return True

    def switch_mode(self, target_mode: str, report_is_dirty: bool = False) -> bool:
        """
        Executes mode transition if valid and allowed.
        Returns True if mode was updated, False if transition was rejected.
        """
        if not self.can_switch_mode(target_mode, report_is_dirty=report_is_dirty):
            return False

        if target_mode != self._active_mode:
            self._active_mode = target_mode
            self._history.append(target_mode)
            if len(self._history) > self._max_history:
                self._history.pop(0)

        return True

    def get_next_tab_mode(self) -> str:
        """Calculates the next mode in the standard Tab cycle."""
        if self._active_mode in TAB_CYCLE_MODES:
            current_idx = TAB_CYCLE_MODES.index(self._active_mode)
            next_idx = (current_idx + 1) % len(TAB_CYCLE_MODES)
            return TAB_CYCLE_MODES[next_idx]
        return TAB_CYCLE_MODES[0]

    def cycle_tab_mode(self, report_is_dirty: bool = False) -> Optional[str]:
        """Cycles to the next Tab mode and updates active state if allowed."""
        next_mode = self.get_next_tab_mode()
        if self.switch_mode(next_mode, report_is_dirty=report_is_dirty):
            return next_mode
        return None

"""
Unit tests for the pure Python navigation state machine.

Runs in memory without Qt or GUI widgets.
"""

from core.navigation_state import NavigationStateMachine


def test_initial_state():
    """Default mode is cheatsheet with initial history."""
    sm = NavigationStateMachine()
    assert sm.active_mode == "cheatsheet"
    assert sm.history == ["cheatsheet"]


def test_valid_mode_transitions():
    """Transitions to valid modes succeed and record history."""
    sm = NavigationStateMachine()
    assert sm.switch_mode("loot") is True
    assert sm.active_mode == "loot"

    assert sm.switch_mode("report") is True
    assert sm.active_mode == "report"

    assert sm.history == ["cheatsheet", "loot", "report"]


def test_invalid_mode_rejected():
    """Transition to unknown mode returns False and does not change state."""
    sm = NavigationStateMachine()
    assert sm.switch_mode("invalid_mode") is False
    assert sm.active_mode == "cheatsheet"


def test_report_dirty_guard():
    """Transition away from dirty report is blocked when not confirmed."""
    sm = NavigationStateMachine(initial_mode="report")
    assert sm.can_switch_mode("cheatsheet", report_is_dirty=True) is False
    assert sm.switch_mode("cheatsheet", report_is_dirty=True) is False
    assert sm.active_mode == "report"

    # When report is not dirty (or user confirmed discard), switch succeeds
    assert sm.switch_mode("cheatsheet", report_is_dirty=False) is True
    assert sm.active_mode == "cheatsheet"


def test_tab_cycling():
    """Tab shortcut cycles in order cheatsheet -> loot -> history -> cheatsheet."""
    sm = NavigationStateMachine(initial_mode="cheatsheet")

    assert sm.get_next_tab_mode() == "loot"
    assert sm.cycle_tab_mode() == "loot"
    assert sm.active_mode == "loot"

    assert sm.get_next_tab_mode() == "history"
    assert sm.cycle_tab_mode() == "history"
    assert sm.active_mode == "history"

    assert sm.get_next_tab_mode() == "cheatsheet"
    assert sm.cycle_tab_mode() == "cheatsheet"
    assert sm.active_mode == "cheatsheet"


def test_tab_cycling_from_report_mode():
    """Cycling tab while in report mode jumps to standard first tab."""
    sm = NavigationStateMachine(initial_mode="report")
    assert sm.get_next_tab_mode() == "cheatsheet"
    assert sm.cycle_tab_mode() == "cheatsheet"
    assert sm.active_mode == "cheatsheet"

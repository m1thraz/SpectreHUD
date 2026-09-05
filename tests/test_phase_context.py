"""Pure Core Logic unit tests for PhaseContext (Tier 0, Zero-Qt)."""

from core.phase_context import PhaseContext
from core.event_bus import EventBus, EventType
from core.phases import PHASES


def test_phase_context_default_unassigned():
    ctx = PhaseContext()
    assert ctx.active_phase_id is None


def test_phase_context_set_valid_phases():
    ctx = PhaseContext()
    for phase in PHASES:
        changed = ctx.set_active_phase(phase.key)
        assert changed is True
        assert ctx.active_phase_id == phase.key

        # Setting the same phase again returns False
        assert ctx.set_active_phase(phase.key) is False


def test_phase_context_set_aliases_and_names():
    ctx = PhaseContext()
    # Test short badge name
    assert ctx.set_active_phase("RECON") is True
    assert ctx.active_phase_id == "recon"

    # Test alias
    assert ctx.set_active_phase("poc") is True
    assert ctx.active_phase_id == "scripts"

    # Test order digit string
    assert ctx.set_active_phase("3") is True
    assert ctx.active_phase_id == "privesc"


def test_phase_context_clear_active_phase():
    ctx = PhaseContext(initial_phase="access")
    assert ctx.active_phase_id == "access"

    changed = ctx.clear_active_phase()
    assert changed is True
    assert ctx.active_phase_id is None

    # Clearing again returns False
    assert ctx.clear_active_phase() is False

    # Setting None or empty string also clears
    ctx.set_active_phase("recon")
    assert ctx.active_phase_id == "recon"
    assert ctx.set_active_phase(None) is True
    assert ctx.active_phase_id is None

    ctx.set_active_phase("recon")
    assert ctx.set_active_phase("") is True
    assert ctx.active_phase_id is None


def test_phase_context_rejects_invalid_phases():
    ctx = PhaseContext(initial_phase="access")
    assert ctx.set_active_phase("invalid_phase_xyz_123") is False
    assert ctx.active_phase_id == "access"


def test_phase_context_publishes_event_bus():
    bus = EventBus()
    events = []
    bus.subscribe(EventType.ACTIVE_PHASE_CHANGED, events.append)

    ctx = PhaseContext(event_bus=bus)
    ctx.set_active_phase("recon", source="hotkey")
    assert len(events) == 1
    assert events[0] == {"phase_id": "recon", "source": "hotkey"}

    ctx.clear_active_phase(source="ui")
    assert len(events) == 2
    assert events[1] == {"phase_id": None, "source": "ui"}

    # notify=False suppresses publication
    ctx.set_active_phase("postex", notify=False)
    assert len(events) == 2

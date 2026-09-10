"""
Centralized Pentest Phase Context for SpectreHUD.

Tracks the globally active pentest phase per project/session.
Pure Python, Zero-Qt, headless.
"""

from typing import Optional
from core.phases import VALID_PHASE_KEYS, try_normalize_phase_key
from core.event_bus import ActivePhaseChangedPayload, EventBus, EventType


class PhaseContext:
    """Holds and manages the active pentest phase context."""

    def __init__(self, initial_phase: Optional[str] = None, event_bus: Optional[EventBus] = None):
        self._active_phase_id: Optional[str] = None
        self._event_bus = event_bus
        if initial_phase:
            self.set_active_phase(initial_phase, notify=False)

    @property
    def active_phase_id(self) -> Optional[str]:
        """Returns the current active phase key, or None if unassigned."""
        return self._active_phase_id

    def set_active_phase(
        self,
        phase_id: Optional[str],
        notify: bool = True,
        source: str = "programmatic",
    ) -> bool:
        """
        Sets the active phase.
        Accepts any canonical key or alias (from core.phases), or None/empty for Unassigned.
        Returns True if the phase changed.
        """
        if not phase_id:
            return self.clear_active_phase(notify=notify, source=source)

        norm_key = try_normalize_phase_key(phase_id)
        if not norm_key or norm_key not in VALID_PHASE_KEYS:
            return False

        if norm_key == self._active_phase_id:
            return False

        self._active_phase_id = norm_key
        if notify and self._event_bus:
            self._event_bus.publish(
                EventType.ACTIVE_PHASE_CHANGED,
                ActivePhaseChangedPayload(phase_id=self._active_phase_id, source=source),
            )
        return True

    def clear_active_phase(self, notify: bool = True, source: str = "programmatic") -> bool:
        """Clears the active phase, resetting state to Unassigned (None)."""
        if self._active_phase_id is None:
            return False
        self._active_phase_id = None
        if notify and self._event_bus:
            self._event_bus.publish(
                EventType.ACTIVE_PHASE_CHANGED,
                ActivePhaseChangedPayload(phase_id=None, source=source),
            )
        return True

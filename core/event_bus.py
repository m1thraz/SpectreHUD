"""
Central Thread-Safe and UI-Independent EventBus for SpectreHUD.

Allows decoupled publish/subscribe event routing across core managers,
domain controllers, and UI panels without direct object dependencies.
"""

from typing import Dict, List, Callable, Any, Optional
from enum import Enum
import threading
import warnings
from core.logger import get_logger

logger = get_logger("event_bus")


class EventType(str, Enum):
    """Standardized event topics across SpectreHUD."""
    PROJECT_CHANGED = "project_changed"
    PROJECT_CREATED = "project_created"
    PROJECT_ACTIVATED = "project_activated"
    LOOT_UPDATED = "loot_updated"
    HISTORY_UPDATED = "history_updated"
    SNIPPETS_UPDATED = "snippets_updated"
    LOGGING_STATE_CHANGED = "logging_state_changed"
    MODE_CHANGED = "mode_changed"
    SCREENSHOT_SAVED = "screenshot_saved"
    LANGUAGE_CHANGED = "language_changed"
    SEARCH_CHANGED = "search_changed"
    VARIABLES_CHANGED = "variables_changed"
    HOTKEY_SETTINGS_CHANGED = "hotkey_settings_changed"


class EventBus:
    """
    Lightweight, thread-safe publish-subscribe event broker.
    Supports pure Python callbacks and exception isolation.

    Thread Safety Contract
    ----------------------
    ``publish()`` executes all subscriber callbacks **synchronously in the calling thread**.

    **Rule:** EventBus is domain-level only. Subscribers must not directly mutate Qt widgets
    from a background thread. UI updates triggered by domain events must cross the Qt signal
    boundary first (e.g. ``QMetaObject.invokeMethod(..., Qt.ConnectionType.QueuedConnection)``
    or a ``pyqtSignal`` connection with ``Qt.ConnectionType.QueuedConnection``).

    Background publishers in SpectreHUD (``ClipboardWatcher``, ``HotkeyListener``) emit
    Qt signals to transfer control to the main thread before any widget interaction occurs.
    Subscribers that update UI state must follow the same pattern.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_type: str, callback: Callable[[Any], None]) -> Callable[[], None]:
        """
        Subscribes a callback to an event type.
        Returns a parameterless unsubscribe function for convenient cleanup.
        """
        key = str(event_type)
        with self._lock:
            if key not in self._subscribers:
                self._subscribers[key] = []
            if callback not in self._subscribers[key]:
                self._subscribers[key].append(callback)

        def _unsubscribe():
            self.unsubscribe(key, callback)

        return _unsubscribe

    def unsubscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        """Removes a subscriber callback from an event topic."""
        key = str(event_type)
        with self._lock:
            if key in self._subscribers:
                if callback in self._subscribers[key]:
                    self._subscribers[key].remove(callback)
                if not self._subscribers[key]:
                    del self._subscribers[key]

    def publish(self, event_type: str, data: Any = None) -> None:
        """
        Publishes an event to all registered subscribers.
        Ensures exception isolation so that one failing subscriber
        does not prevent others from receiving the notification.
        """
        key = str(event_type)
        with self._lock:
            callbacks = list(self._subscribers.get(key, []))

        for cb in callbacks:
            try:
                cb(data)
            except Exception as e:
                logger.error(
                    f"Error in EventBus subscriber '{getattr(cb, '__qualname__', str(cb))}' "
                    f"handling event '{key}': {e}",
                    exc_info=True
                )

    def clear(self) -> None:
        """Clears all registered subscribers. Useful for test isolation."""
        with self._lock:
            self._subscribers.clear()

    def get_subscriber_count(self, event_type: Optional[str] = None) -> int:
        """Returns the number of active subscribers for a specific topic or in total."""
        with self._lock:
            if event_type is not None:
                return len(self._subscribers.get(str(event_type), []))
            return sum(len(cbs) for cbs in self._subscribers.values())


# Global Singleton EventBus Instance
_GLOBAL_EVENT_BUS: Optional[EventBus] = None
_GLOBAL_LOCK = threading.Lock()


def get_event_bus() -> EventBus:
    """Deprecated compatibility access to the process-wide EventBus instance."""
    warnings.warn(
        "get_event_bus() is deprecated; inject an EventBus from ServiceContainer instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    global _GLOBAL_EVENT_BUS
    if _GLOBAL_EVENT_BUS is None:
        with _GLOBAL_LOCK:
            if _GLOBAL_EVENT_BUS is None:
                _GLOBAL_EVENT_BUS = EventBus()
    return _GLOBAL_EVENT_BUS

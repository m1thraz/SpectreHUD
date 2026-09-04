"""Headless tests for clipboard-history domain behavior."""

import subprocess
import sys

import pytest

from core.clipboard_history import (
    MAX_CLIPBOARD_TEXT_SIZE,
    MAX_HISTORY_ENTRIES,
    ClipboardHistory,
)
from core.event_bus import EventBus, EventType
from core.storage import InMemoryStorageBackend, PersistenceError, StorageBackend


class FailingStorage(StorageBackend):
    def load_json(self, resource_name):
        return None

    def save_json(self, resource_name, data):
        return False

    def exists(self, resource_name):
        return False

    def delete(self, resource_name):
        return False

    def clear(self):
        pass


def test_module_import_is_qt_free():
    code = (
        "import sys\n"
        "import core.clipboard_history\n"
        "assert not [name for name in sys.modules if name.startswith('PyQt6')]\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_add_deduplicates_limits_and_returns_defensive_copies():
    history = ClipboardHistory(storage=InMemoryStorageBackend())
    assert history.add_entry("  whoami  ")["text"] == "whoami"
    assert history.add_entry("whoami") is None

    history._last_copied_text = None
    for index in range(MAX_HISTORY_ENTRIES + 5):
        history.add_entry(f"entry-{index}")

    entries = history.get_all_history()
    assert len(entries) == MAX_HISTORY_ENTRIES
    entries[0]["text"] = "mutated"
    assert history.get_all_history()[0]["text"] != "mutated"


def test_oversized_and_blank_entries_are_ignored():
    history = ClipboardHistory(storage=InMemoryStorageBackend())
    assert history.add_entry("   ") is None
    assert history.add_entry("x" * (MAX_CLIPBOARD_TEXT_SIZE + 1)) is None
    assert history.get_all_history() == []


def test_failed_persistence_does_not_change_memory_or_deduplication_state():
    history = ClipboardHistory(storage=FailingStorage())
    with pytest.raises(PersistenceError):
        history.add_entry("secret")

    assert history.get_all_history() == []
    assert history._last_copied_text is None


def test_successful_mutation_publishes_one_domain_event():
    event_bus = EventBus()
    received = []
    event_bus.subscribe(EventType.HISTORY_UPDATED, received.append)
    history = ClipboardHistory(storage=InMemoryStorageBackend(), event_bus=event_bus)

    entry = history.add_entry("id")

    assert entry is not None
    assert len(received) == 1
    assert received[0]["action"] == "add"
    assert received[0]["entry"] == entry

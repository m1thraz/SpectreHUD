"""Focused tests for the Qt clipboard capture adapter."""

from unittest.mock import patch

from core.clipboard_history import ClipboardHistory
from core.storage import InMemoryStorageBackend
from ui.clipboard_monitor import ClipboardMonitor


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def disconnect(self, callback):
        self.callbacks.remove(callback)

    def emit(self):
        for callback in list(self.callbacks):
            callback()


class FakeClipboard:
    def __init__(self):
        self.dataChanged = FakeSignal()
        self.value = ""

    def text(self):
        return self.value


class FakeApplication:
    def __init__(self, clipboard):
        self._clipboard = clipboard

    def clipboard(self):
        return self._clipboard


def test_start_and_stop_are_idempotent(qapp):
    clipboard = FakeClipboard()
    monitor = ClipboardMonitor(ClipboardHistory(storage=InMemoryStorageBackend()))

    with patch("ui.clipboard_monitor.QApplication.instance", return_value=FakeApplication(clipboard)):
        assert monitor.start_listening()
        assert monitor.start_listening()
        assert len(clipboard.dataChanged.callbacks) == 1
        monitor.stop_listening()
        monitor.stop_listening()
        assert clipboard.dataChanged.callbacks == []


def test_capture_uses_target_and_emits_only_for_new_entries(qapp):
    clipboard = FakeClipboard()
    history = ClipboardHistory(storage=InMemoryStorageBackend())
    monitor = ClipboardMonitor(history)
    emitted = []
    monitor.entry_added.connect(emitted.append)
    monitor.set_target_provider(lambda: "10.10.10.8")

    with patch("ui.clipboard_monitor.QApplication.instance", return_value=FakeApplication(clipboard)):
        monitor.start_listening()
        monitor.set_paused(False)
        clipboard.value = " whoami "
        clipboard.dataChanged.emit()
        clipboard.dataChanged.emit()

    assert len(emitted) == 1
    assert emitted[0]["text"] == "whoami"
    assert emitted[0]["target_ip"] == "10.10.10.8"
    assert history.get_all_history() == emitted


def test_paused_monitor_ignores_clipboard_changes(qapp):
    clipboard = FakeClipboard()
    history = ClipboardHistory(storage=InMemoryStorageBackend())
    monitor = ClipboardMonitor(history)

    with patch("ui.clipboard_monitor.QApplication.instance", return_value=FakeApplication(clipboard)):
        monitor.start_listening()
        clipboard.value = "id"
        clipboard.dataChanged.emit()

    assert history.get_all_history() == []

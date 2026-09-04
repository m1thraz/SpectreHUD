"""Qt adapter that captures system clipboard changes into ClipboardHistory."""

from typing import Callable, Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.clipboard_history import ClipboardHistory
from core.logger import get_logger

logger = get_logger("clipboard")


class ClipboardMonitor(QObject):
    """Own Qt clipboard lifecycle and recording state, but no history data."""

    entry_added = pyqtSignal(dict)
    logging_state_changed = pyqtSignal(bool)

    def __init__(
        self,
        history: ClipboardHistory,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.history = history
        self._is_paused = True
        self._target_provider: Optional[Callable[[], str]] = None
        self._clipboard = None

    def set_target_provider(self, provider: Callable[[], str]) -> None:
        self._target_provider = provider

    def start_listening(self) -> bool:
        """Connect once to the current QApplication clipboard."""
        app = QApplication.instance()
        if app is None:
            return False
        clipboard = app.clipboard()
        if self._clipboard is clipboard:
            return True
        self.stop_listening()
        clipboard.dataChanged.connect(self._on_clipboard_changed)
        self._clipboard = clipboard
        return True

    def stop_listening(self) -> None:
        """Disconnect safely and make repeated shutdown calls harmless."""
        if self._clipboard is None:
            return
        try:
            self._clipboard.dataChanged.disconnect(self._on_clipboard_changed)
        except (TypeError, RuntimeError):
            pass
        self._clipboard = None

    def _on_clipboard_changed(self) -> None:
        if self._is_paused or self._clipboard is None:
            return
        try:
            text = self._clipboard.text()
            if not text:
                return
            target_ip = ""
            if self._target_provider:
                try:
                    target_ip = self._target_provider() or ""
                except (TypeError, ValueError, AttributeError) as exc:
                    logger.debug("Error resolving target_ip in clipboard provider: %s", exc)
            entry = self.history.add_entry(text, target_ip=target_ip, persist=False)
            if entry is not None:
                self.entry_added.emit(entry)
        except (RuntimeError, OSError) as exc:
            logger.error("Error reading clipboard content: %s", exc, exc_info=True)

    def toggle_pause(self) -> bool:
        """Toggle recording and return whether it is now paused."""
        self._is_paused = not self._is_paused
        self.logging_state_changed.emit(not self._is_paused)
        logger.info(
            "Clipboard logging state toggled: %s",
            "PAUSED" if self._is_paused else "ACTIVE",
        )
        return self._is_paused

    def set_paused(self, paused: bool) -> None:
        if self._is_paused != paused:
            self._is_paused = paused
            self.logging_state_changed.emit(not self._is_paused)
            logger.info(
                "Clipboard logging state set: %s",
                "PAUSED" if self._is_paused else "ACTIVE",
            )

    @property
    def is_paused(self) -> bool:
        return self._is_paused

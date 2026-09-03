"""
Global Hotkey Listener for SpectreHUD.

Provides dynamic, configurable system-wide keyboard shortcuts for:
- Overlay Toggle
- Screenshot & Region Snip
- Complete Application Quit
"""

import time
from dataclasses import dataclass
from typing import Optional, Dict, Callable
from PyQt6.QtCore import QObject, pyqtSignal

from core.logger import get_logger

logger = get_logger(__name__)


from core.platform import (
    PlatformCapabilities,
    detect_platform_capabilities,
)


@dataclass(frozen=True)
class HotkeyConfig:
    """Immutable configuration for global hotkey mappings."""

    toggle: str = "<ctrl>+<alt>+h"
    screenshot: str = "<ctrl>+<alt>+x"
    quick_note: str = "<ctrl>+<alt>+n"
    quick_ip: str = "<ctrl>+<alt>+i"
    quit: str = "<ctrl>+<alt>+q"


def normalize_hotkey_for_pynput(hotkey_str: str) -> str:
    """
    Normalizes human-friendly hotkey strings to pynput GlobalHotKeys format.
    E.g.:
      'Strg + Super + <' -> '<ctrl>+<cmd>+<'
      'Ctrl + Alt + H'   -> '<ctrl>+<alt>+h'
      'F12'              -> '<f12>'
    """
    if not hotkey_str:
        return "<ctrl>+<alt>+h"

    s = hotkey_str.strip().lower()
    s = s.replace("strg", "ctrl").replace("super", "cmd").replace("win", "cmd")
    parts = [p.strip() for p in s.replace("+", " ").split() if p.strip()]

    normalized_parts = []
    for p in parts:
        if p in ("<", ">"):
            normalized_parts.append(p)
            continue
        clean_p = p.strip("<>")
        if clean_p in ("ctrl", "cmd", "alt", "shift", "space", "enter", "tab", "esc") or (
            clean_p.startswith("f") and clean_p[1:].isdigit()
        ):
            normalized_parts.append(f"<{clean_p}>")
        else:
            normalized_parts.append(clean_p)

    return "+".join(normalized_parts)


class HotkeyListener(QObject):
    """
    Dynamic global hotkey listener supporting configurable key combinations
    via pynput.keyboard.GlobalHotKeys with hot-reload capability.
    """

    toggle_requested = pyqtSignal()
    screenshot_requested = pyqtSignal()
    quick_note_requested = pyqtSignal()
    quick_ip_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(
        self,
        hotkey_str: str = "<ctrl>+<alt>+h",
        config: Optional[HotkeyConfig] = None,
        capabilities: Optional[PlatformCapabilities] = None,
    ):
        super().__init__()
        self._capabilities = (
            capabilities if capabilities is not None else detect_platform_capabilities()
        )
        if config is not None:
            self.config = config
        else:
            self.config = HotkeyConfig(toggle=hotkey_str)

        self._listener = None
        self._running = False
        self._available = self._capabilities.global_hotkeys
        self._last_trigger_time = 0.0
        self._last_screenshot_time = 0.0
        self._last_quick_note_time = 0.0
        self._last_quick_ip_time = 0.0
        self._last_quit_time = 0.0
        self._debounce_cooldown = 0.35  # seconds

    @property
    def capabilities(self) -> PlatformCapabilities:
        return self._capabilities

    def is_available(self) -> bool:
        """Return True if system-wide global hotkeys are supported on the active desktop session."""
        return self._available

    def is_running(self) -> bool:
        """Return True if the background global hotkey listener thread is running."""
        return self._running

    def update_config(self, new_config: HotkeyConfig) -> bool:
        """Dynamically updates the hotkey configuration and reloads listener if active."""
        if new_config == self.config and self._running:
            return True

        self.config = new_config
        logger.info(
            f"Updated hotkey config: Toggle='{self.config.toggle}', Snip='{self.config.screenshot}', Note='{self.config.quick_note}', IP='{self.config.quick_ip}', Quit='{self.config.quit}'"
        )
        if self._running:
            self.stop()
            self.start()
        return True

    def start(self) -> bool:
        """Starts the pynput GlobalHotKeys listener if supported."""
        if not self.is_available():
            if self._capabilities.wayland:
                logger.warning(
                    "Global system hotkeys are unavailable or restricted in this Wayland session."
                )
            else:
                logger.warning(
                    f"Global system hotkeys are not supported on platform '{self._capabilities.system}'."
                )
            self._running = False
            return False

        try:
            from pynput import keyboard

            norm_toggle = normalize_hotkey_for_pynput(self.config.toggle)
            norm_snip = normalize_hotkey_for_pynput(self.config.screenshot)
            norm_note = normalize_hotkey_for_pynput(self.config.quick_note)
            norm_ip = normalize_hotkey_for_pynput(self.config.quick_ip)
            norm_quit = normalize_hotkey_for_pynput(self.config.quit)

            hotkey_mapping: Dict[str, Callable[[], None]] = {}

            if norm_toggle:
                hotkey_mapping[norm_toggle] = self._fire_trigger
            if norm_snip:
                hotkey_mapping[norm_snip] = self._fire_screenshot_trigger
            if norm_note:
                hotkey_mapping[norm_note] = self._fire_quick_note_trigger
            if norm_ip:
                hotkey_mapping[norm_ip] = self._fire_quick_ip_trigger
            if norm_quit:
                hotkey_mapping[norm_quit] = self._fire_quit_trigger

            self._listener = keyboard.GlobalHotKeys(hotkey_mapping)
            self._listener.daemon = True
            self._listener.start()
            self._running = True
            logger.info(f"Registered global hotkeys: {list(hotkey_mapping.keys())}")
            return True
        except (ImportError, ValueError, OSError, RuntimeError, Exception) as e:
            logger.warning(
                f"Failed to start global hotkey listener ({e}). Continuing with in-app shortcuts only."
            )
            self._running = False
            self._available = False
            return False

    def _fire_trigger(self) -> None:
        """Debounces and emits toggle signal safely."""
        now = time.time()
        if now - self._last_trigger_time >= self._debounce_cooldown:
            self._last_trigger_time = now
            self.toggle_requested.emit()

    def _fire_screenshot_trigger(self) -> None:
        """Debounces and emits screenshot signal safely."""
        now = time.time()
        if now - self._last_screenshot_time >= self._debounce_cooldown:
            self._last_screenshot_time = now
            self.screenshot_requested.emit()

    def _fire_quick_note_trigger(self) -> None:
        """Debounces and emits quick note signal safely."""
        now = time.time()
        if now - self._last_quick_note_time >= self._debounce_cooldown:
            self._last_quick_note_time = now
            self.quick_note_requested.emit()

    def _fire_quick_ip_trigger(self) -> None:
        """Debounces and emits quick IP signal safely."""
        now = time.time()
        if now - self._last_quick_ip_time >= self._debounce_cooldown:
            self._last_quick_ip_time = now
            self.quick_ip_requested.emit()

    def _fire_quit_trigger(self) -> None:
        """Debounces and emits quit signal safely."""
        now = time.time()
        if now - self._last_quit_time >= self._debounce_cooldown:
            self._last_quit_time = now
            self.quit_requested.emit()

    def stop(self) -> None:
        """Stops the global hotkey listener."""
        if self._listener:
            try:
                self._listener.stop()
                # pynput uses a native hook thread on Windows.  Waiting a
                # bounded amount here prevents it from outliving application
                # shutdown while keeping quit responsive if the OS hook is
                # already unavailable.
                if self._listener.is_alive():
                    self._listener.join(timeout=1.0)
            except (RuntimeError, OSError) as e:
                logger.debug(f"Error stopping hotkey listener: {e}")
            self._listener = None
        self._running = False

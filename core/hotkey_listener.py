import time
import threading
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal

class HotkeyListener(QObject):
    """
    Robust global hotkey listener supporting:
    - Strg + Super + < (HUD Toggle)
    - Strg + Super + X (Screenshot & Region Snipping)
    across all keyboard layouts and Windows virtual keycodes.
    """
    toggle_requested = pyqtSignal()
    screenshot_requested = pyqtSignal()

    def __init__(self, hotkey_str: str = "<ctrl>+<cmd>+<"):
        super().__init__()
        # Normalize hotkey string
        normalized = hotkey_str.lower().replace("strg", "ctrl").replace("super", "cmd").replace("win", "cmd")
        self.hotkey_str = normalized
        
        self._listener = None
        self._running = False
        self._last_trigger_time = 0.0
        self._last_screenshot_time = 0.0
        self._debounce_cooldown = 0.35  # seconds
        
        # State tracking for modifier keys
        self._ctrl_down = False
        self._cmd_down = False
        self._alt_down = False
        self._shift_down = False

    def start(self) -> None:
        """Starts the robust low-level keyboard listener."""
        try:
            from pynput import keyboard

            def on_press(key):
                # Update modifier states
                if key in [keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
                    self._ctrl_down = True
                elif key in [keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r]:
                    self._cmd_down = True
                elif key in [keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr]:
                    self._alt_down = True
                elif key in [keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r]:
                    self._shift_down = True

                # Check for trigger keys
                is_less_than_key = False
                is_x_key = False
                try:
                    if hasattr(key, 'char') and key.char:
                        if key.char in ['<', '>', '«', '»']:
                            is_less_than_key = True
                        elif key.char.lower() == 'x':
                            is_x_key = True
                    
                    if hasattr(key, 'vk') and key.vk:
                        if key.vk in [226, 188]:
                            is_less_than_key = True
                        elif key.vk in [88, 120]:  # 'X' / 'x'
                            is_x_key = True
                except Exception:
                    pass

                # 1. Primary Shortcut: Strg + Super/Win + < -> HUD Toggle
                if self._ctrl_down and self._cmd_down and is_less_than_key:
                    self._fire_trigger()

                # 2. Screenshot Shortcut: Strg + Super/Win + X -> Snip Tool
                if self._ctrl_down and self._cmd_down and is_x_key:
                    self._fire_screenshot_trigger()

            def on_release(key):
                # Release modifier states
                if key in [keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
                    self._ctrl_down = False
                elif key in [keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r]:
                    self._cmd_down = False
                elif key in [keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr]:
                    self._alt_down = False
                elif key in [keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r]:
                    self._shift_down = False

            self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self._listener.daemon = True
            self._listener.start()
            self._running = True
            print(f"[HotkeyListener] Registered robust global hotkeys: Strg+Super+< (Toggle), Strg+Super+X (Screenshot)")
        except Exception as e:
            print(f"[HotkeyListener] Failed to start global hotkey listener: {e}")

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

    def stop(self) -> None:
        """Stops the global hotkey listener."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._running = False

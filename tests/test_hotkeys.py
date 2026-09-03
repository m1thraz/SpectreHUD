"""
Tests for Global Hotkey Listener and Dynamic Hotkey Configuration.
"""

import unittest
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch
from core.hotkey_listener import HotkeyConfig, HotkeyListener, normalize_hotkey_for_pynput


class TestHotkeys(unittest.TestCase):
    def test_hotkey_config_immutability(self):
        cfg = HotkeyConfig(toggle="<ctrl>+<alt>+s", screenshot="<ctrl>+<shift>+x")
        self.assertEqual(cfg.toggle, "<ctrl>+<alt>+s")
        self.assertEqual(cfg.screenshot, "<ctrl>+<shift>+x")
        self.assertEqual(cfg.quick_note, "<ctrl>+<cmd>+n")
        self.assertEqual(cfg.quit, "<ctrl>+<cmd>+q")

    def test_normalize_hotkey_strings(self):
        self.assertEqual(normalize_hotkey_for_pynput("Strg + Super + <"), "<ctrl>+<cmd>+<")
        self.assertEqual(normalize_hotkey_for_pynput("Ctrl + Alt + S"), "<ctrl>+<alt>+s")
        self.assertEqual(normalize_hotkey_for_pynput("Ctrl + Shift + H"), "<ctrl>+<shift>+h")
        self.assertEqual(normalize_hotkey_for_pynput("F12"), "<f12>")
        self.assertEqual(normalize_hotkey_for_pynput("<f11>"), "<f11>")
        self.assertEqual(normalize_hotkey_for_pynput(""), "<ctrl>+<cmd>+<")

    def test_hotkey_listener_initialization_and_update(self):
        listener = HotkeyListener(hotkey_str="<ctrl>+<alt>+t")
        self.assertEqual(listener.config.toggle, "<ctrl>+<alt>+t")

        new_cfg = HotkeyConfig(
            toggle="<ctrl>+<shift>+h",
            screenshot="<f11>",
            quick_note="<ctrl>+<alt>+n",
            quit="<ctrl>+<alt>+q",
        )
        updated = listener.update_config(new_cfg)
        self.assertTrue(updated)
        self.assertEqual(listener.config.toggle, "<ctrl>+<shift>+h")
        self.assertEqual(listener.config.screenshot, "<f11>")
        self.assertEqual(listener.config.quick_note, "<ctrl>+<alt>+n")
        self.assertEqual(listener.config.quit, "<ctrl>+<alt>+q")

    def test_invalid_hotkey_does_not_crash(self):
        listener = HotkeyListener(hotkey_str="invalid+++key+++combo")
        # Unit tests must neither install a real system-wide keyboard hook nor
        # import pynput's platform backend (which requires X11 on Linux).
        fake_keyboard = ModuleType("pynput.keyboard")
        fake_keyboard.GlobalHotKeys = MagicMock(side_effect=ValueError("invalid hotkey"))
        fake_pynput = ModuleType("pynput")
        fake_pynput.keyboard = fake_keyboard
        with patch.dict(sys.modules, {"pynput": fake_pynput, "pynput.keyboard": fake_keyboard}):
            listener.start()
        listener.stop()
        self.assertFalse(listener._running)

    def test_stop_waits_for_active_listener_thread(self):
        listener = HotkeyListener()
        hook = unittest.mock.MagicMock()
        hook.is_alive.return_value = True
        listener._listener = hook
        listener._running = True

        listener.stop()

        hook.stop.assert_called_once()
        hook.join.assert_called_once_with(timeout=1.0)
        self.assertFalse(listener._running)

    def test_signal_emission_helpers(self):
        listener = HotkeyListener()
        toggle_called = []
        snip_called = []
        quick_note_called = []
        quit_called = []

        listener.toggle_requested.connect(lambda: toggle_called.append(True))
        listener.screenshot_requested.connect(lambda: snip_called.append(True))
        listener.quick_note_requested.connect(lambda: quick_note_called.append(True))
        listener.quit_requested.connect(lambda: quit_called.append(True))

        listener._fire_trigger()
        listener._fire_screenshot_trigger()
        listener._fire_quick_note_trigger()
        listener._fire_quit_trigger()

        self.assertEqual(len(toggle_called), 1)
        self.assertEqual(len(snip_called), 1)
        self.assertEqual(len(quick_note_called), 1)
        self.assertEqual(len(quit_called), 1)

    def test_hotkey_listener_respects_wayland_capability_restriction(self):
        """Ticket 21 & 23: On Wayland, listener is marked unavailable and start returns False gracefully."""
        from core.platform import PlatformCapabilities

        wayland_caps = PlatformCapabilities(
            system="linux",
            global_hotkeys=False,
            screen_capture=False,
            wayland=True,
            x11=False,
        )
        listener = HotkeyListener(capabilities=wayland_caps)
        self.assertFalse(listener.is_available())
        self.assertFalse(listener.is_running())

        # Calling start must return False without attempting to hook
        started = listener.start()
        self.assertFalse(started)
        self.assertFalse(listener.is_running())

    def test_hotkey_listener_startup_failure_degrades_gracefully(self):
        """Ticket 23: If backend hook raises RuntimeError during start, it degrades gracefully."""
        from core.platform import PlatformCapabilities

        caps = PlatformCapabilities(
            system="windows",
            global_hotkeys=True,
            screen_capture=True,
            wayland=False,
            x11=False,
        )
        listener = HotkeyListener(capabilities=caps)
        self.assertTrue(listener.is_available())

        fake_keyboard = ModuleType("pynput.keyboard")
        fake_keyboard.GlobalHotKeys = MagicMock(side_effect=RuntimeError("Display connection lost"))
        fake_pynput = ModuleType("pynput")
        fake_pynput.keyboard = fake_keyboard
        with patch.dict(sys.modules, {"pynput": fake_pynput, "pynput.keyboard": fake_keyboard}):
            started = listener.start()

        self.assertFalse(started)
        self.assertFalse(listener.is_running())
        self.assertFalse(listener.is_available())


if __name__ == "__main__":
    unittest.main()


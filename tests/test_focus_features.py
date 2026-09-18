"""
Tests for ADHS-friendliness focus features:
- Session recap banner upon return after inactivity
- Documentation time nudge during active clipboard recording
"""

import time
import unittest
from unittest.mock import MagicMock

from ui.clipboard_monitor import ClipboardMonitor
from ui.panels.header_panel import HeaderPanel
from ui.session_recap_banner import SessionRecapBanner


class TestSessionRecapBanner(unittest.TestCase):
    def test_recap_banner_display_and_dismiss(self):
        banner = SessionRecapBanner(auto_dismiss_ms=5000)
        self.assertTrue(banner.isHidden())

        info = {
            "phase_name": "Recon",
            "last_action": "Letzte Note (12:30): \"Found open SSH port\"",
            "open_notes": 3,
            "unsynced_loot": 1,
        }
        banner.show_recap(info)
        self.assertFalse(banner.isHidden())
        self.assertIn("Recon", banner.lbl_phase.text())
        self.assertIn("Found open SSH", banner.lbl_last_action.text())
        self.assertIn("3 offene Notes", banner.lbl_badges.text())
        self.assertIn("1 ungesynctes Loot", banner.lbl_badges.text())

        # Click close button
        banner.btn_close.click()
        self.assertTrue(banner.isHidden())
        banner.deleteLater()


class TestClipboardMonitorIsRecording(unittest.TestCase):
    def test_is_recording_property(self):
        history = MagicMock()
        monitor = ClipboardMonitor(history=history)
        self.assertTrue(monitor._is_paused)
        self.assertFalse(monitor.is_recording)

        monitor._is_paused = False
        self.assertTrue(monitor.is_recording)


class TestHeaderPanelNudge(unittest.TestCase):
    def test_rec_nudge_click_triggers_quick_note(self):
        header = HeaderPanel()
        header.update_rec_indicator(True)
        self.assertTrue(getattr(header, "_rec_active", False))

        quick_note_called = []
        toggle_rec_called = []
        header.quick_note_requested.connect(lambda: quick_note_called.append(True))
        header.toggle_rec_requested.connect(lambda: toggle_rec_called.append(True))

        # 1. When NOT nudged: normal click toggles REC
        header.btn_rec_indicator.click()
        self.assertEqual(len(toggle_rec_called), 1)
        self.assertEqual(len(quick_note_called), 0)

        # 2. When nudged: click opens quick note and clears nudge
        header.set_rec_nudged(True)
        self.assertTrue(getattr(header, "_rec_nudged", False))

        header.btn_rec_indicator.click()
        self.assertEqual(len(quick_note_called), 1)
        self.assertFalse(getattr(header, "_rec_nudged", False))
        header.deleteLater()


class TestAppControllerFocusNudgeLogic(unittest.TestCase):
    def test_check_rec_nudge_and_reset(self):
        from ui.app_controller import AppController

        ctrl = MagicMock(spec=AppController)
        ctrl.config = {"nudge_enabled": True, "nudge_interval_minutes": 25}
        ctrl.header = MagicMock()
        ctrl.clipboard_monitor = MagicMock()
        ctrl.clipboard_monitor.is_recording = True
        ctrl._last_doc_activity_time = time.time() - (26 * 60)  # 26 minutes ago

        # Bind methods under test
        ctrl._check_rec_nudge = AppController._check_rec_nudge.__get__(ctrl)
        ctrl._reset_rec_nudge = AppController._reset_rec_nudge.__get__(ctrl)

        # Elapsed 26m >= 25m -> trigger nudge
        ctrl._check_rec_nudge()
        ctrl.header.set_rec_nudged.assert_called_with(True)

        # Reset nudge on new capture
        ctrl._reset_rec_nudge()
        ctrl.header.set_rec_nudged.assert_called_with(False)
        self.assertAlmostEqual(ctrl._last_doc_activity_time, time.time(), delta=2)

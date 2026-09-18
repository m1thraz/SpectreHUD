"""
Tests for ADHS-friendliness focus features:
- Session recap banner upon return after inactivity
- Documentation time nudge during active clipboard recording
"""

import time
import unittest
from unittest.mock import MagicMock

from core.i18n import t
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
            "target": "10.10.10.42",
            "unsynced_loot": 1,
            "resume_context": {"mode": "notes", "id": "note_123"},
        }
        banner.show_recap(info)
        self.assertFalse(banner.isHidden())
        self.assertIn("Recon", banner.lbl_phase.text())
        self.assertIn("10.10.10.42", banner.lbl_target.text())
        self.assertTrue(banner.lbl_target.isVisible())
        self.assertIn("Found open SSH", banner.lbl_last_action.text())
        self.assertIn(t("recap.open_notes", "{count} offene Notes", count=3), banner.lbl_badges.text())
        self.assertIn(t("recap.unsynced_loot", "{count} ungesynctes Loot", count=1), banner.lbl_badges.text())

        # Click resume button emits resume_clicked and hides
        resumed = []
        banner.resume_clicked.connect(resumed.append)
        banner.btn_resume.click()
        self.assertTrue(banner.isHidden())
        self.assertEqual(len(resumed), 1)
        self.assertEqual(resumed[0], {"mode": "notes", "id": "note_123"})

        # Show again and test close button
        banner.show_recap(info)
        self.assertFalse(banner.isHidden())
        banner.btn_close.click()
        self.assertTrue(banner.isHidden())
        banner.deleteLater()

    def test_recap_without_target_hides_target_label(self):
        banner = SessionRecapBanner(auto_dismiss_ms=5000)
        banner.show_recap({"phase_name": "PrivEsc", "target": ""})
        self.assertTrue(banner.lbl_target.isHidden())
        self.assertTrue(banner.lbl_sep_target.isHidden())
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


class TestAppControllerResume(unittest.TestCase):
    def test_handle_resume_switches_mode(self):
        from ui.app_controller import AppController

        ctrl = MagicMock(spec=AppController)
        ctrl.active_mode = "cheatsheet"
        ctrl.switch_mode = MagicMock()
        ctrl.handle_resume = AppController.handle_resume.__get__(ctrl)

        ctrl.handle_resume({"mode": "notes", "id": "n1"})
        ctrl.switch_mode.assert_called_once_with("notes")

    def test_handle_resume_fallback_to_active_mode(self):
        from ui.app_controller import AppController

        ctrl = MagicMock(spec=AppController)
        ctrl.active_mode = "loot"
        ctrl.switch_mode = MagicMock()
        ctrl.handle_resume = AppController.handle_resume.__get__(ctrl)

        ctrl.handle_resume({})
        ctrl.switch_mode.assert_called_once_with("loot")


class TestAppControllerNextAttention(unittest.TestCase):
    def test_attention_priority_followup_over_inbox(self):
        from ui.app_controller import AppController

        ctrl = MagicMock(spec=AppController)
        ctrl.quick_note_manager = MagicMock()
        ctrl.loot_manager = MagicMock()
        ctrl.quick_note_manager.get_all_entries.return_value = [
            {"id": "n1", "status": "inbox", "text": "Inbox Note"},
            {"id": "n2", "status": "followup", "text": "Followup Note"},
        ]
        ctrl.get_next_attention_item = AppController.get_next_attention_item.__get__(ctrl)

        item = ctrl.get_next_attention_item()
        self.assertIsNotNone(item)
        self.assertEqual(item["type"], "followup")
        self.assertIn("Followup Note", item["text"])
        self.assertEqual(item["context"]["id"], "n2")

    def test_attention_priority_inbox_when_no_followup(self):
        from ui.app_controller import AppController

        ctrl = MagicMock(spec=AppController)
        ctrl.quick_note_manager = MagicMock()
        ctrl.loot_manager = MagicMock()
        ctrl.quick_note_manager.get_all_entries.return_value = [
            {"id": "n1", "status": "inbox", "text": "First Inbox Note"},
        ]
        ctrl.get_next_attention_item = AppController.get_next_attention_item.__get__(ctrl)

        item = ctrl.get_next_attention_item()
        self.assertIsNotNone(item)
        self.assertEqual(item["type"], "inbox")
        self.assertIn("First Inbox Note", item["text"])

    def test_attention_returns_none_when_all_done(self):
        from ui.app_controller import AppController

        ctrl = MagicMock(spec=AppController)
        ctrl.quick_note_manager = MagicMock()
        ctrl.loot_manager = MagicMock()
        ctrl.loot_manager.get_all_entries.return_value = []
        ctrl.quick_note_manager.get_all_entries.return_value = [
            {"id": "n1", "status": "resolved", "text": "Done Note"},
        ]
        ctrl.get_next_attention_item = AppController.get_next_attention_item.__get__(ctrl)

        item = ctrl.get_next_attention_item()
        self.assertIsNone(item)


class TestWorkflowAcceptanceScenario(unittest.TestCase):
    """Programmatic verification of the 9-step Manual Acceptance Scenario:
    1. Set project, target (10.10.10.42), phase RECON.
    2. Terminal focused, Spectre visible in background.
    3. Screenshot trigger:
       - Screenshot saved with RECON + Target.
       - Terminal keeps focus (no raise_ / activateWindow on Spectre).
       - Spectre does not switch to Loot.
    4. Terminal text copied (captured with RECON + Target).
    5. Phase switched to ACCESS.
    6. Promote old clipboard item to Loot:
       - Retains captured RECON + Target (not overwritten by active ACCESS).
    7. Quick Note created & marked as Later:
       - status='followup'.
       - Prioritized in next attention item.
    8. Session recap / resume:
       - Phase and Target visible.
       - Last activity visible.
       - Resume routes to appropriate mode.
    9. Quick Loot draft fault-tolerance:
       - Unintentional focus loss / cancel preserves draft and restores it.
    """

    def test_full_acceptance_scenario(self):
        from core.screenshots.manager import ScreenshotManager
        from ui.add_loot_dialog import AddLootDialog
        from ui.app_controller import AppController
        from ui.coordinators.clipboard_coordinator import ClipboardCoordinator

        # --- Steps 1, 2, 3: Capture & Continue without stealing focus or switching mode ---
        sm = ScreenshotManager(capabilities=MagicMock())
        parent_window = MagicMock()
        # Spectre is visible in background, but NOT active (terminal has focus)
        sm._restore_parent_window(parent_window, was_visible=True, was_active=False)
        parent_window.show.assert_called_once()
        parent_window.raise_.assert_not_called()
        parent_window.activateWindow.assert_not_called()

        ctrl = MagicMock(spec=AppController)
        ctrl.active_mode = "cheatsheet"
        ctrl.switch_mode = MagicMock()
        ctrl.phase_toast_hud = MagicMock()
        ctrl.screenshot_transaction = MagicMock()
        ctrl.event_bus = MagicMock()
        ctrl._on_screenshot_saved = AppController._on_screenshot_saved.__get__(ctrl)
        ctrl._on_screenshot_saved({"category": "recon", "target_ip": "10.10.10.42"})
        # Spectre must NOT switch to loot
        ctrl.switch_mode.assert_not_called()

        # --- Steps 4, 5, 6: Context Provenance in Promotion (RECON retained over ACCESS) ---
        loot_ctrl = MagicMock()
        coord = ClipboardCoordinator(
            clipboard_monitor=MagicMock(),
            history_ctrl=MagicMock(),
            loot_ctrl=loot_ctrl,
            quick_note_ctrl=MagicMock(),
            target_provider=lambda: "10.10.10.99",  # active target
            phase_provider=lambda: "access",  # active phase changed to ACCESS
        )
        history_item = {
            "text": "nmap -sV 10.10.10.42",
            "phase_id": "recon",  # captured during RECON
            "target_ip": "10.10.10.42",  # captured target
            "timestamp": "12:00",
        }
        coord.add_history_to_loot(MagicMock(), history_item)
        loot_ctrl.open_add_dialog.assert_called_once()
        call_kwargs = loot_ctrl.open_add_dialog.call_args[1]
        self.assertEqual(call_kwargs["default_category"], "recon")
        self.assertEqual(call_kwargs["target_ip"], "10.10.10.42")

        # --- Step 7: Quick note marked as 'later' (status=followup) in Next Attention ---
        ctrl.quick_note_manager = MagicMock()
        ctrl.loot_manager = MagicMock()
        ctrl.loot_manager.get_all_entries.return_value = []
        ctrl.quick_note_manager.get_all_entries.return_value = [
            {"id": "n_later", "status": "followup", "text": "Check SMB signing later"}
        ]
        ctrl.get_next_attention_item = AppController.get_next_attention_item.__get__(ctrl)
        attention = ctrl.get_next_attention_item()
        self.assertIsNotNone(attention)
        self.assertEqual(attention["type"], "followup")
        self.assertIn("Check SMB signing later", attention["text"])

        # --- Step 8: Session recap reflects Phase, Target, Last Action, and Resume ---
        ctrl.phase_context = MagicMock()
        ctrl.phase_context.active_phase_id = "access"
        ctrl.phase_context.active_phase_name = "Initial Access"
        ctrl._target_provider = lambda: "10.10.10.42"
        ctrl.get_session_recap_info = AppController.get_session_recap_info.__get__(ctrl)
        ctrl._get_last_action_summary_and_context = (
            AppController._get_last_action_summary_and_context.__get__(ctrl)
        )
        ctrl.handle_resume = AppController.handle_resume.__get__(ctrl)

        recap = ctrl.get_session_recap_info()
        self.assertEqual(recap["phase_name"], "ACCESS")
        self.assertEqual(recap["target"], "10.10.10.42")
        self.assertIsNotNone(recap["last_action"])
        self.assertEqual(recap["resume_context"]["mode"], "notes")

        ctrl.handle_resume(recap["resume_context"])
        ctrl.switch_mode.assert_called_with("notes")

        # --- Step 9: Quick Loot draft preserved on cancel/blur ---
        AddLootDialog._cached_draft = None
        dlg1 = AddLootDialog(target_ip="10.10.10.42")
        dlg1.txt_title.setText("Kerberoasting Hash")
        dlg1.txt_content.setPlainText("$krb5tgs$23$...")
        dlg1.reject()  # simulate cancel / unintentional focus loss
        dlg1.deleteLater()

        self.assertIsNotNone(AddLootDialog._cached_draft)
        self.assertEqual(AddLootDialog._cached_draft["title"], "Kerberoasting Hash")

        dlg2 = AddLootDialog(target_ip="10.10.10.42")
        self.assertEqual(dlg2.txt_title.text(), "Kerberoasting Hash")
        self.assertEqual(dlg2.txt_content.toPlainText(), "$krb5tgs$23$...")
        self.assertFalse(dlg2.recovery_banner.isHidden())
        dlg2.deleteLater()
        AddLootDialog._cached_draft = None


"""
Tests for HistoryCard Promote button and ClipboardCoordinator.add_history_to_note.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QGraphicsOpacityEffect, QWidget

from ui.history_card import HistoryCard
from ui.coordinators.clipboard_coordinator import ClipboardCoordinator

class TestHistoryCardPromoteButton(unittest.TestCase):
    def setUp(self):
        self.entry = {
            "id": "hist-123",
            "text": "nmap -sC -sV 10.10.10.50",
            "timestamp": "23:30:00",
            "is_command": True,
            "target_ip": "10.10.10.50",
        }
        self.card = HistoryCard(self.entry)

    def tearDown(self):
        self.card.close()

    def test_promote_button_initial_state(self):
        self.assertIsNotNone(self.card.btn_promote)
        label = self.card.btn_promote.text()
        self.assertTrue(
            "Promote" in label or "Übernehmen" in label,
            f"Unexpected button label: {label!r}",
        )
        # No pre-attached QMenu — menu is created dynamically on click.
        self.assertIsNone(self.card.btn_promote.menu())

    def test_no_permanent_edit_or_delete_buttons(self):
        self.assertFalse(hasattr(self.card, "btn_edit"))
        self.assertFalse(hasattr(self.card, "btn_delete"))

    def test_promote_note_emits_transfer_to_note_and_disables_button(self):
        notes_emitted = []
        loot_emitted = []
        self.card.transfer_to_note.connect(notes_emitted.append)
        self.card.transfer_to_loot.connect(loot_emitted.append)

        self.card._on_promote_note()

        self.assertEqual(len(notes_emitted), 1)
        self.assertEqual(notes_emitted[0]["id"], "hist-123")
        self.assertEqual(len(loot_emitted), 0)
        # Button must be disabled after promoting to notes (no double-promote).
        self.assertFalse(self.card.btn_promote.isEnabled())

    def test_promote_loot_emits_transfer_to_loot(self):
        loot_emitted = []
        notes_emitted = []
        self.card.transfer_to_loot.connect(loot_emitted.append)
        self.card.transfer_to_note.connect(notes_emitted.append)

        self.card._on_promote_loot()

        self.assertEqual(len(loot_emitted), 1)
        self.assertEqual(loot_emitted[0]["id"], "hist-123")
        self.assertEqual(len(notes_emitted), 0)

    def test_promote_note_feedback_label_contains_expected_text(self):
        from core.i18n import t
        self.card._on_promote_note()
        # Text should be the promoted feedback, not the original label.
        promoted_text = t("history.promoted_as_note", "Note ✓")
        self.assertEqual(self.card.btn_promote.text(), promoted_text)

    def test_reset_promote_btn_restores_initial_state(self):
        self.card._on_promote_note()
        self.card._reset_promote_btn()
        label = self.card.btn_promote.text()
        self.assertTrue(
            "Promote" in label or "Übernehmen" in label,
            f"Unexpected button label after reset: {label!r}",
        )
        self.assertTrue(self.card.btn_promote.isEnabled())

    def test_context_menu_has_edit_and_delete_actions(self):
        """contextMenuEvent must produce a menu with exactly two actions."""
        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QContextMenuEvent

        menus_created = []
        original_exec = None

        # Intercept QMenu.exec to avoid blocking on native menu.
        import ui.history_card as hc_mod

        original_QMenu = hc_mod.QMenu

        class CapturingMenu(original_QMenu):
            def exec(self, pos=None):  # type: ignore[override]
                menus_created.append(self)

        with patch.object(hc_mod, "QMenu", CapturingMenu):
            ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5))
            self.card.contextMenuEvent(ev)

        self.assertEqual(len(menus_created), 1)
        actions = [a for a in menus_created[0].actions() if not a.isSeparator()]
        self.assertEqual(
            len(actions), 3, f"Expected 3 context actions (report, edit, delete), got {len(actions)}"
        )

    def test_report_checkbox_initial_state_and_toggle(self):
        self.assertIsNotNone(self.card.chk_report)
        self.assertFalse(self.card.chk_report.isChecked())

        # Creating card with include_in_report=True sets checked state
        card_marked = HistoryCard({"id": "h-2", "text": "id", "include_in_report": True})
        self.assertTrue(card_marked.chk_report.isChecked())
        card_marked.close()

        # Toggling emits report_toggled signal
        emitted = []
        self.card.report_toggled.connect(lambda entry, checked: emitted.append((entry, checked)))
        self.card.chk_report.setChecked(True)
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0][0]["id"], "hist-123")
        self.assertTrue(emitted[0][1])

        # Test context menu toggle helper
        self.card._toggle_report_from_menu()
        self.assertFalse(self.card.chk_report.isChecked())
        self.assertEqual(len(emitted), 2)
        self.assertFalse(emitted[1][1])

    def test_copy_button_present_and_permanent(self):
        self.assertTrue(hasattr(self.card, "btn_copy"))
        # Not explicitly hidden — permanent in the resting layout.
        self.assertFalse(self.card.btn_copy.isHidden())


class TestHistoryCardAgeOpacity(unittest.TestCase):
    def _make_card(self, age_hours: float) -> HistoryCard:
        ts = (datetime.now() - timedelta(hours=age_hours)).strftime("%Y-%m-%d %H:%M:%S")
        entry = {"id": "x", "text": "test", "timestamp": ts}
        return HistoryCard(entry)

    def tearDown(self):
        # Cards are closed in individual tests where created.
        pass

    def test_fresh_entry_no_opacity_reduction(self):
        card = self._make_card(0.1)
        effect = card.graphicsEffect()
        if effect is not None:
            self.assertIsInstance(effect, QGraphicsOpacityEffect)
            self.assertAlmostEqual(effect.opacity(), 1.0, places=2)
        card.close()

    def test_old_entry_opacity_at_floor(self):
        card = self._make_card(8.0)
        effect = card.graphicsEffect()
        self.assertIsNotNone(effect, "Old entry must have an opacity effect")
        self.assertIsInstance(effect, QGraphicsOpacityEffect)
        self.assertAlmostEqual(effect.opacity(), 0.5, places=2)
        card.close()

    def test_medium_age_entry_partial_fade(self):
        card = self._make_card(3.0)  # 2 < 3 < 6 → 0.65
        effect = card.graphicsEffect()
        self.assertIsNotNone(effect)
        self.assertIsInstance(effect, QGraphicsOpacityEffect)
        self.assertAlmostEqual(effect.opacity(), 0.65, places=2)
        card.close()

    def test_no_timestamp_no_effect(self):
        """Entry without parseable timestamp must not crash and has no effect."""
        card = HistoryCard({"id": "y", "text": "no ts"})
        # Either no effect, or full opacity — never raises.
        effect = card.graphicsEffect()
        if effect is not None:
            self.assertIsInstance(effect, QGraphicsOpacityEffect)
            self.assertAlmostEqual(effect.opacity(), 1.0, places=2)
        card.close()


class TestHistoryCardMetaLine(unittest.TestCase):
    def test_meta_line_contains_time_and_target(self):
        entry = {
            "id": "m1",
            "text": "ls",
            "timestamp": "2026-09-06 10:00:00",
            "target_ip": "10.0.0.1",
        }
        card = HistoryCard(entry)
        meta = card.lbl_meta.text()
        self.assertIn("10:00:00", meta)
        self.assertIn("10.0.0.1", meta)
        card.close()

    def test_meta_line_omits_missing_fields(self):
        entry = {"id": "m2", "text": "whoami", "timestamp": ""}
        card = HistoryCard(entry)
        meta = card.lbl_meta.text()
        # Should not contain stray separators from empty fields.
        self.assertNotIn("·  ·", meta)
        card.close()


class TestClipboardCoordinatorCapture(unittest.TestCase):
    def setUp(self):
        self.clipboard_watcher = MagicMock()
        self.history_ctrl = MagicMock()
        self.loot_ctrl = MagicMock()
        self.target_provider = MagicMock(return_value="10.10.10.100")
        self.quick_note_ctrl = MagicMock()
        self.quick_note_ctrl.current_category = "privesc"
        self.quick_note_ctrl.last_category = "privesc"
        self.quick_note_ctrl.add_entry.return_value = {"id": "note-1", "text": "cmd"}

        self.coordinator = ClipboardCoordinator(
            clipboard_monitor=self.clipboard_watcher,
            history_ctrl=self.history_ctrl,
            loot_ctrl=self.loot_ctrl,
            target_provider=self.target_provider,
            quick_note_ctrl=self.quick_note_ctrl,
        )

    def test_add_history_to_note_success_with_priority_category(self):
        notes_mutated = []
        self.coordinator.notes_mutated.connect(lambda: notes_mutated.append(True))

        window = QWidget()
        history_item = {
            "id": "h-1",
            "text": "whoami /priv",
            "is_command": True,
            "target_ip": "10.10.10.50",
        }

        success = self.coordinator.add_history_to_note(window, history_item)

        self.assertTrue(success)
        self.assertEqual(len(notes_mutated), 1)
        self.quick_note_ctrl.add_entry.assert_called_once_with(
            text="whoami /priv",
            category="privesc",  # Priority from quick_note_ctrl
            target_ip="10.10.10.50",
        )
        # Verify history_item remains unchanged (non-destructive)
        self.assertEqual(history_item["id"], "h-1")
        self.assertEqual(history_item["text"], "whoami /priv")

    def test_add_history_to_note_heuristic_category_fallback(self):
        self.quick_note_ctrl.current_category = "misc"
        self.quick_note_ctrl.last_category = "misc"

        window = QWidget()
        # Case 1: is_command is True -> access
        item_cmd = {"text": "ssh root@box", "is_command": True}
        self.coordinator.add_history_to_note(window, item_cmd)
        self.quick_note_ctrl.add_entry.assert_called_with(
            text="ssh root@box",
            category="access",
            target_ip="10.10.10.100",
        )

        # Case 2: is_command is False -> recon
        item_text = {"text": "Found robots.txt entries", "is_command": False}
        self.coordinator.add_history_to_note(window, item_text)
        self.quick_note_ctrl.add_entry.assert_called_with(
            text="Found robots.txt entries",
            category="recon",
            target_ip="10.10.10.100",
        )

    def test_add_history_to_note_empty_text_ignored(self):
        window = QWidget()
        item_empty = {"text": "   "}
        success = self.coordinator.add_history_to_note(window, item_empty)
        self.assertFalse(success)
        self.quick_note_ctrl.add_entry.assert_not_called()



class TestHistoryControllerFilterPills(unittest.TestCase):
    def test_history_controller_has_no_notes_filter(self):
        from ui.controllers.history_controller import HistoryController

        mock_clip = MagicMock()
        mock_clip.get_history.return_value = [
            {"id": "c1", "text": "cmd1", "include_in_report": True},
            {"id": "c2", "text": "cmd2", "include_in_report": False},
        ]
        controller = HistoryController(
            clipboard_history=mock_clip,
            loot_manager=MagicMock(),
            project_manager=MagicMock(),
        )
        actions = controller.get_filter_actions()
        filter_ids = [a.data.get("filter") for a in actions]
        self.assertNotIn("notes", filter_ids)
        self.assertIn("all", filter_ids)
        self.assertIn("report", filter_ids)
        self.assertIn("commands", filter_ids)
        self.assertIn("outputs", filter_ids)

        # Ensure "report" filter action has count 1
        report_action = next(a for a in actions if a.data.get("filter") == "report")
        self.assertIn("(1)", report_action.text)


if __name__ == "__main__":
    unittest.main()

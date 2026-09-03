"""
Tests for HistoryCard Split-Button Capture and ClipboardCoordinator.add_history_to_note.
"""

import unittest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QMouseEvent

from ui.history_card import HistoryCard
from ui.coordinators.clipboard_coordinator import ClipboardCoordinator

# Ensure QApplication exists for GUI tests
app = QApplication.instance() or QApplication([])


class TestHistoryCardSplitButton(unittest.TestCase):
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

    def test_split_button_initial_state(self):
        self.assertIsNotNone(self.card.btn_capture)
        # Backwards compatibility alias
        self.assertIs(self.card.btn_to_loot, self.card.btn_capture)
        self.assertIn("Erfassen", self.card.btn_capture.text())
        self.assertIsNotNone(self.card.btn_capture.menu())

    def test_main_click_emits_transfer_to_note(self):
        notes_emitted = []
        loot_emitted = []
        self.card.transfer_to_note.connect(notes_emitted.append)
        self.card.transfer_to_loot.connect(loot_emitted.append)

        # Click the main button
        self.card.btn_capture.click()

        self.assertEqual(len(notes_emitted), 1)
        self.assertEqual(notes_emitted[0]["id"], "hist-123")
        self.assertEqual(notes_emitted[0]["text"], "nmap -sC -sV 10.10.10.50")
        self.assertEqual(len(loot_emitted), 0)
        # Verify visual feedback
        self.assertIn("✓", self.card.btn_capture.text())

    def test_mouse_press_left_part_triggers_note(self):
        notes_emitted = []
        self.card.transfer_to_note.connect(notes_emitted.append)

        # Simulate mouse click on the left portion of the button (x = 20)
        self.card.btn_capture.resize(100, 30)
        ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(20, 15),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.card.btn_capture.mousePressEvent(ev)

        self.assertEqual(len(notes_emitted), 1)
        self.assertEqual(notes_emitted[0]["id"], "hist-123")

    def test_menu_actions_exist_and_trigger_signals(self):
        menu = self.card.btn_capture.menu()
        self.assertIsNotNone(menu)
        actions = menu.actions()
        self.assertEqual(len(actions), 2)

        # Action 0: Als Note erfassen
        notes_emitted = []
        self.card.transfer_to_note.connect(notes_emitted.append)
        actions[0].trigger()
        self.assertEqual(len(notes_emitted), 1)
        self.assertEqual(notes_emitted[0]["id"], "hist-123")

        # Action 1: Als Loot erfassen
        loot_emitted = []
        self.card.transfer_to_loot.connect(loot_emitted.append)
        actions[1].trigger()
        self.assertEqual(len(loot_emitted), 1)
        self.assertEqual(loot_emitted[0]["id"], "hist-123")

    def test_visual_feedback_resets(self):
        self.card._on_capture_note()
        self.assertIn("✓", self.card.btn_capture.text())
        self.card._reset_capture_btn()
        self.assertIn("Erfassen", self.card.btn_capture.text())


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
            clipboard_watcher=self.clipboard_watcher,
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


if __name__ == "__main__":
    unittest.main()

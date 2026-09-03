"""
Tests for QuickNoteController and QuickNotePopup.
"""

import unittest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication

from core.quick_note_manager import QuickNoteManager
from core.storage import InMemoryStorageBackend
from core.event_bus import EventBus
from ui.controllers.quick_note_controller import QuickNoteController
from ui.quick_note_popup import QuickNotePopup

# Ensure QApplication exists for GUI tests
app = QApplication.instance() or QApplication([])


class TestQuickNoteController(unittest.TestCase):
    def setUp(self):
        self.storage = InMemoryStorageBackend()
        self.event_bus = EventBus()
        self.manager = QuickNoteManager(storage=self.storage, event_bus=self.event_bus)
        self.loot_ctrl = MagicMock()
        self.target_provider = MagicMock(return_value="10.10.10.50")
        self.controller = QuickNoteController(
            quick_note_manager=self.manager,
            loot_controller=self.loot_ctrl,
            target_provider=self.target_provider,
            event_bus=self.event_bus,
        )

    def test_submit_note_saves_and_emits(self):
        added_entries = []
        self.controller.note_added.connect(added_entries.append)

        entry = self.controller.submit_note("Check SMB null session", category="recon")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["text"], "Check SMB null session")
        self.assertEqual(entry["category"], "recon")
        self.assertEqual(entry["target_ip"], "10.10.10.50")
        self.assertEqual(self.controller.last_category, "recon")
        self.assertEqual(len(added_entries), 1)

    def test_delete_note(self):
        entry = self.controller.submit_note("Temp thought", category="misc")
        self.assertEqual(len(self.manager.get_all_entries()), 1)

        success = self.controller.delete_note(entry["id"])
        self.assertTrue(success)
        self.assertEqual(len(self.manager.get_all_entries()), 0)

    def test_promote_to_loot_calls_dialog_and_removes_note(self):
        entry = self.controller.submit_note("Found admin:admin123 creds", category="access")
        self.loot_ctrl.open_add_dialog.return_value = True

        promoted = self.controller.promote_to_loot(entry)
        self.assertTrue(promoted)
        self.loot_ctrl.open_add_dialog.assert_called_once()
        # Verify note is deleted from inbox
        self.assertEqual(len(self.manager.get_all_entries()), 0)

    def test_promote_to_loot_cancelled_preserves_note(self):
        entry = self.controller.submit_note("Potential LFI parameter", category="recon")
        self.loot_ctrl.open_add_dialog.return_value = False

        promoted = self.controller.promote_to_loot(entry)
        self.assertFalse(promoted)
        # Note still in inbox
        self.assertEqual(len(self.manager.get_all_entries()), 1)


class TestQuickNotePopup(unittest.TestCase):
    def setUp(self):
        self.popup = QuickNotePopup(default_category="recon")

    def tearDown(self):
        self.popup.close()

    def test_initial_category(self):
        self.assertEqual(self.popup.current_category, "recon")

    def test_select_category(self):
        self.popup.select_category("privesc")
        self.assertEqual(self.popup.current_category, "privesc")

    def test_accept_and_submit_signal(self):
        submitted = []
        self.popup.note_submitted.connect(lambda text, cat: submitted.append((text, cat)))

        self.popup.text_edit.setPlainText("Discovered port 8888 open")
        self.popup.select_category("recon")
        self.popup.accept()

        self.assertEqual(len(submitted), 1)
        self.assertEqual(submitted[0][0], "Discovered port 8888 open")
        self.assertEqual(submitted[0][1], "recon")

    def test_reject_cancels(self):
        cancelled = []
        self.popup.cancelled.connect(lambda: cancelled.append(True))
        self.popup.reject()
        self.assertEqual(len(cancelled), 1)


if __name__ == "__main__":
    unittest.main()

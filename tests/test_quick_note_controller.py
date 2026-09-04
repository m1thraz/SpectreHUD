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

    def test_build_filter_pills_and_select_filter(self):
        from PyQt6.QtWidgets import QWidget, QHBoxLayout

        self.controller.submit_note("Recon note", category="recon")
        self.controller.submit_note("Access note", category="access")

        container = QWidget()
        layout = QHBoxLayout(container)
        selected_filters = []
        cleared = []

        self.controller.build_filter_pills(
            layout,
            on_select_filter=selected_filters.append,
            on_clear=lambda: cleared.append(True),
        )

        self.assertIn("all", self.controller.filter_buttons)
        self.assertIn("recon", self.controller.filter_buttons)
        self.assertIn("access", self.controller.filter_buttons)

        # Test selecting a filter
        self.controller.select_filter("recon")
        self.assertEqual(self.controller.current_category_filter, "recon")
        self.assertEqual(
            self.controller.filter_buttons["recon"].property("class"),
            "FilterPillActive",
        )
        container.close()

    def test_clear_all_notes(self):
        self.controller.submit_note("Note 1", category="misc")
        self.controller.submit_note("Note 2", category="recon")
        self.assertEqual(len(self.manager.get_all_entries()), 2)

        # Calling without parent_widget skips modal dialog and clears
        success = self.controller.clear_all_notes(parent_widget=None)
        self.assertTrue(success)
        self.assertEqual(len(self.manager.get_all_entries()), 0)

    def test_render_content(self):
        from PyQt6.QtWidgets import QWidget, QVBoxLayout

        self.controller.submit_note("Note for testing render", category="recon")
        container = QWidget()
        layout = QVBoxLayout(container)
        empty_fn = MagicMock()

        cards = self.controller.render_content(
            content_layout=layout,
            search_query="",
            on_copied=MagicMock(),
            parent_widget=container,
            show_empty_state_fn=empty_fn,
        )

        self.assertEqual(len(cards), 1)
        empty_fn.assert_not_called()

        # Test empty state when filtered with no matches
        empty_layout = QVBoxLayout(container)
        self.controller.select_filter("privesc")
        empty_cards = self.controller.render_content(
            content_layout=empty_layout,
            search_query="",
            on_copied=MagicMock(),
            parent_widget=container,
            show_empty_state_fn=empty_fn,
        )
        self.assertEqual(len(empty_cards), 0)
        empty_fn.assert_called_once()
        container.close()


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


class TestAppControllerAddButtonAndNotesIntegration(unittest.TestCase):
    def setUp(self):
        from ui.app_controller import AppController

        self.controller = MagicMock(spec=AppController)
        self.controller.active_mode = "notes"
        self.controller._target_provider = MagicMock(return_value="10.10.10.50")
        self.controller.window = MagicMock()
        self.controller.cheatsheet_ctrl = MagicMock()
        self.controller.loot_ctrl = MagicMock()
        self.controller.quick_note_ctrl = MagicMock()
        self.controller.quick_note_manager = MagicMock()
        self.controller.header = MagicMock()
        self.controller.refresh_filter_pills = MagicMock()
        self.controller.refresh_content = MagicMock()

        # Bind methods under test
        self.controller._on_add_button_clicked = AppController._on_add_button_clicked.__get__(
            self.controller
        )
        self.controller._on_notes_updated = AppController._on_notes_updated.__get__(
            self.controller
        )
        self.controller._update_notes_badge = AppController._update_notes_badge.__get__(
            self.controller
        )

    def test_add_button_in_notes_mode_opens_quick_note_popup(self):
        self.controller.active_mode = "notes"
        self.controller._on_add_button_clicked()

        self.controller.quick_note_ctrl.show_popup.assert_called_once()
        self.controller.loot_ctrl.open_add_dialog.assert_not_called()
        self.controller.cheatsheet_ctrl.open_add_dialog.assert_not_called()

    def test_add_button_in_history_mode_opens_quick_note_popup(self):
        self.controller.active_mode = "history"
        self.controller._on_add_button_clicked()

        self.controller.quick_note_ctrl.show_popup.assert_called_once()
        self.controller.loot_ctrl.open_add_dialog.assert_not_called()

    def test_add_button_in_report_mode_does_nothing(self):
        self.controller.active_mode = "report"
        self.controller._on_add_button_clicked()

        self.controller.quick_note_ctrl.show_popup.assert_not_called()
        self.controller.loot_ctrl.open_add_dialog.assert_not_called()

    def test_on_notes_updated_updates_notes_badge(self):
        self.controller.active_mode = "notes"
        self.controller.quick_note_manager.get_all_entries.return_value = [
            {"id": "n1"},
            {"id": "n2"},
        ]

        self.controller._on_notes_updated()

        self.controller.header.update_notes_badge.assert_called_once_with(2)
        self.controller.refresh_filter_pills.assert_called_once()
        self.controller.refresh_content.assert_called_once()


if __name__ == "__main__":
    unittest.main()

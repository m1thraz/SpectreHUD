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
        self.report_ctrl = MagicMock()
        self.target_provider = MagicMock(return_value="10.10.10.50")
        self.controller = QuickNoteController(
            quick_note_manager=self.manager,
            loot_controller=self.loot_ctrl,
            report_controller=self.report_ctrl,
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

    def test_update_note_text(self):
        entry = self.controller.submit_note("Original note text", category="recon")
        note_id = entry["id"]

        success = self.controller.update_note_text(note_id, "Updated note text")
        self.assertTrue(success)

        stored = self.manager.get_all_entries()[0]
        self.assertEqual(stored["text"], "Updated note text")

    def test_set_note_status(self):
        entry = self.controller.submit_note("Follow up on this", category="access")
        note_id = entry["id"]
        self.assertEqual(entry.get("status"), "inbox")

        self.assertTrue(self.controller.set_note_status(note_id, "followup"))
        stored = self.manager.get_all_entries()[0]
        self.assertEqual(stored["status"], "followup")

        self.assertTrue(self.controller.set_note_status(note_id, "resolved"))
        stored = self.manager.get_all_entries()[0]
        self.assertEqual(stored["status"], "resolved")

    def test_toggle_note_pinned(self):
        entry = self.controller.submit_note("Pin me", category="misc")
        note_id = entry["id"]
        self.assertFalse(entry.get("pinned", False))

        self.assertTrue(self.controller.toggle_note_pinned(note_id, True))
        stored = self.manager.get_all_entries()[0]
        self.assertTrue(stored["pinned"])

        self.assertTrue(self.controller.toggle_note_pinned(note_id, False))
        stored = self.manager.get_all_entries()[0]
        self.assertFalse(stored["pinned"])

    def test_send_to_report_success_marks_resolved(self):
        entry = self.controller.submit_note("Crucial finding for report", category="privesc")
        self.report_ctrl.append_note.return_value = True

        success = self.controller.send_to_report(entry)
        self.assertTrue(success)
        self.report_ctrl.append_note.assert_called_once_with(entry)

        # Note should now be resolved in manager
        stored = self.manager.get_all_entries()[0]
        self.assertEqual(stored["status"], "resolved")

    def test_bulk_triage_actions(self):
        e1 = self.controller.submit_note("Note 1", category="recon")
        e2 = self.controller.submit_note("Note 2", category="access")

        # Selection tracking
        self.controller.on_card_selection_changed(e1["id"], True)
        self.controller.on_card_selection_changed(e2["id"], True)
        self.assertEqual(self.controller.selected_note_ids, {e1["id"], e2["id"]})

        # Bulk mark as followup
        self.controller.bulk_set_status("followup")
        self.assertEqual(len(self.controller.selected_note_ids), 0)
        entries = self.manager.get_all_entries()
        for e in entries:
            self.assertEqual(e["status"], "followup")

        # Select e1 again and bulk delete
        self.controller.on_card_selection_changed(e1["id"], True)
        self.assertTrue(self.controller.bulk_delete_notes(parent_widget=None))
        self.assertEqual(len(self.controller.selected_note_ids), 0)
        remaining = self.manager.get_all_entries()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["id"], e2["id"])

    def test_render_content_with_status_filter(self):
        from PyQt6.QtWidgets import QWidget, QVBoxLayout

        e1 = self.controller.submit_note("Inbox note", category="recon")
        e2 = self.controller.submit_note("Resolved note", category="access")
        self.controller.set_note_status(e2["id"], "resolved")

        container = QWidget()
        layout = QVBoxLayout(container)
        empty_fn = MagicMock()

        # Default all filter renders both
        cards = self.controller.render_content(
            content_layout=layout,
            search_query="",
            on_copied=None,
            parent_widget=container,
            show_empty_state_fn=empty_fn,
        )
        self.assertEqual(len(cards), 2)

        # Filter by inbox
        self.controller.select_filter("inbox")
        layout_inbox = QVBoxLayout(container)
        cards_inbox = self.controller.render_content(
            content_layout=layout_inbox,
            search_query="",
            on_copied=None,
            parent_widget=container,
            show_empty_state_fn=empty_fn,
        )
        self.assertEqual(len(cards_inbox), 1)
        self.assertEqual(cards_inbox[0].entry["id"], e1["id"])

        # Filter by resolved
        self.controller.select_filter("resolved")
        layout_res = QVBoxLayout(container)
        cards_res = self.controller.render_content(
            content_layout=layout_res,
            search_query="",
            on_copied=None,
            parent_widget=container,
            show_empty_state_fn=empty_fn,
        )
        self.assertEqual(len(cards_res), 1)
        self.assertEqual(cards_res[0].entry["id"], e2["id"])
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

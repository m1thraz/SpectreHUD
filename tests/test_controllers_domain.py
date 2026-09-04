"""
Unit tests for UI-independent domain controllers and MenuAction DTOs.
Verifies that controllers execute pure business logic without requiring interactive Qt widgets.
"""

import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout

app = QApplication.instance()
if app is None:
    app = QApplication([])

from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project import ProjectManager
from core.event_bus import EventBus, EventType
from ui.controllers.project_controller import ProjectController
from ui.controllers.cheatsheet_controller import CheatsheetController
from ui.controllers.loot_controller import LootController
from ui.controllers.history_controller import HistoryController


class TestControllersDomain(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path)

        self.event_bus = EventBus()
        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.snippet_mgr = SnippetManager(user_snippets_path=self.temp_path / "user_snippets.json")
        self.loot_mgr = LootManager(
            storage_file=self.temp_path / "loot.json", event_bus=self.event_bus
        )
        self.clip_watcher = ClipboardWatcher(
            storage_file=self.temp_path / "clipboard.json", event_bus=self.event_bus
        )

        self.project_ctrl = ProjectController(self.project_mgr, event_bus=self.event_bus)
        self.cheatsheet_ctrl = CheatsheetController(self.snippet_mgr, event_bus=self.event_bus)
        self.loot_ctrl = LootController(self.loot_mgr, self.project_mgr, event_bus=self.event_bus)
        self.history_ctrl = HistoryController(
            self.clip_watcher, self.loot_mgr, self.project_mgr, event_bus=self.event_bus
        )

    def tearDown(self):
        self.event_bus.clear()
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        self.temp_dir.cleanup()

    def test_project_controller_domain_and_menu_actions(self):
        """ProjectController provides pure domain actions and MenuAction DTOs."""
        # Create projects
        self.project_ctrl.create_project("BoxOmega", target_ip="10.10.10.100")
        self.project_ctrl.create_project("BoxBeta", target_ip="10.10.10.200")

        projects = self.project_ctrl.list_projects()
        self.assertIn("BoxOmega", projects)
        self.assertIn("BoxBeta", projects)

        # MenuAction DTO generation
        actions = self.project_ctrl.get_project_menu_actions()
        action_ids = [a.id for a in actions]

        self.assertIn("switch_project:BoxOmega", action_ids)
        self.assertIn("switch_project:BoxBeta", action_ids)
        self.assertIn("new_project", action_ids)
        self.assertIn("import_folder", action_ids)
        self.assertIn("archive_box", action_ids)
        self.assertIn("open_folder", action_ids)

    def test_cheatsheet_controller_domain(self):
        """CheatsheetController manages snippets, favorites, and categories purely in-memory and publishes events."""
        events_received = []
        self.event_bus.subscribe(EventType.SNIPPETS_UPDATED, lambda d: events_received.append(d))

        sid = self.cheatsheet_ctrl.add_custom_snippet(
            title="Domain Test Snip",
            category="linux_shell",
            subcategory="Recon",
            template="uname -a",
        )
        self.assertTrue(bool(sid))
        self.assertEqual(len(events_received), 1)
        self.assertEqual(events_received[0]["action"], "add")

        snippets = self.cheatsheet_ctrl.get_snippets(category_id="custom_snippets")
        titles = [s.get("title") for s in snippets]
        self.assertIn("Domain Test Snip", titles)

        # Toggle favorite
        is_fav = self.cheatsheet_ctrl.toggle_favorite(sid)
        self.assertTrue(is_fav)
        self.assertEqual(len(events_received), 2)
        self.assertEqual(events_received[1]["action"], "favorite")

        fav_snippets = self.cheatsheet_ctrl.get_snippets(category_id="favorites")
        self.assertTrue(any(s.get("id") == sid for s in fav_snippets))

        # Overflow menu actions
        overflow_actions = self.cheatsheet_ctrl.get_overflow_category_actions()
        self.assertTrue(isinstance(overflow_actions, list))

        # Delete
        self.cheatsheet_ctrl.delete_snippet(sid)
        self.assertEqual(len(events_received), 3)
        self.assertEqual(events_received[2]["action"], "delete")
        snippets_after = self.cheatsheet_ctrl.get_snippets(category_id="custom_snippets")
        self.assertFalse(any(s.get("id") == sid for s in snippets_after))

    def test_loot_controller_domain(self):
        """LootController manages loot entries, filter actions, and publishes events."""
        loot_events = []
        self.event_bus.subscribe(EventType.LOOT_UPDATED, lambda d: loot_events.append(d))

        entry = self.loot_ctrl.add_entry(
            entry_type="credentials",
            title="Root Cred",
            content="root:toor",
            target_ip="10.10.10.55",
            category="access",
        )
        eid = entry.get("id")
        self.assertTrue(bool(eid))
        self.assertEqual(len(loot_events), 1)
        self.assertEqual(loot_events[0]["action"], "add")
        self.assertEqual(set(loot_events[0]), {"action", "entry", "entries"})
        self.assertEqual(loot_events[0]["entry"]["id"], eid)

        entries = self.loot_ctrl.get_entries(target_ip="10.10.10.55")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Root Cred")

        counts = self.loot_ctrl.get_type_counts()
        self.assertEqual(counts.get("credentials"), 1)

        filter_actions = self.loot_ctrl.get_type_filter_actions()
        self.assertTrue(any(a.id == "type:credentials" for a in filter_actions))

        # Update entry
        self.loot_ctrl.update_entry(
            entry_id=eid,
            title="Updated Root Cred",
            content="root:SuperSecret!",
            target_ip="10.10.10.55",
            category="access",
        )
        self.assertEqual(len(loot_events), 2)
        self.assertEqual(loot_events[1]["action"], "update")
        self.assertEqual(loot_events[1]["entry"]["id"], eid)

        updated_entries = self.loot_ctrl.get_entries()
        self.assertEqual(updated_entries[0]["title"], "Updated Root Cred")
        self.assertEqual(updated_entries[0]["content"], "root:SuperSecret!")

        # Delete
        self.loot_ctrl.delete_entry(eid)
        self.assertEqual(len(loot_events), 3)
        self.assertEqual(loot_events[2]["action"], "delete")
        self.assertEqual(loot_events[2]["entry"]["id"], eid)
        self.assertEqual(loot_events[2]["entries"], [])
        self.assertEqual(len(self.loot_ctrl.get_entries()), 0)

        self.loot_ctrl.add_entry("note", "Clear me", "temporary")
        self.loot_ctrl.clear_entries()
        self.assertEqual(len(loot_events), 5)
        self.assertEqual(loot_events[4]["action"], "clear")
        self.assertIsNone(loot_events[4]["entry"])
        self.assertEqual(loot_events[4]["entries"], [])

    def test_loot_entry_file_export_uses_category_folder_and_safe_filename(self):
        entry = self.loot_ctrl.add_entry(
            entry_type="note",
            title="../ Nmap Scan: 10.10.10.55",
            content="nmap -sC -sV 10.10.10.55",
            category="scripts",
        )

        exported = self.loot_ctrl.export_entry_to_file(entry["id"])

        project_dir = self.project_mgr.get_project_dir()
        self.assertTrue(exported.is_file())
        self.assertTrue(exported.is_relative_to(project_dir / "scripts"))
        self.assertNotIn("..", exported.name)
        self.assertIn("Nmap_Scan_10.10.10.55", exported.name)
        self.assertIn("nmap -sC -sV 10.10.10.55", exported.read_text(encoding="utf-8"))

        second_export = self.loot_ctrl.export_entry_to_file(entry["id"])
        self.assertNotEqual(exported, second_export)
        self.assertTrue(second_export.is_file())

    def test_loot_controller_moves_entry_between_categories(self):
        entry = self.loot_ctrl.add_entry("note", "Move me", "content", category="recon")

        self.assertTrue(self.loot_ctrl.move_entry_to_category(entry["id"], "postex", 0))
        self.assertEqual(self.loot_ctrl.get_entries()[0]["category"], "postex")
        self.assertFalse(self.loot_ctrl.move_entry_to_category(entry["id"], "not-a-category", 0))

    def test_loot_entry_file_export_surfaces_atomic_write_failure(self):
        from core.storage import PersistenceError

        entry = self.loot_ctrl.add_entry("note", "Cannot write", "content", category="recon")
        with patch(
            "ui.controllers.loot_controller.atomic_write_text", side_effect=OSError("disk full")
        ):
            with self.assertRaises(PersistenceError):
                self.loot_ctrl.export_entry_to_file(entry["id"])

    def test_loot_add_dialog_accepts_new_button_prefill_arguments(self):
        """Loot and History New actions can pass their target and dialog defaults."""
        dialog_data = {
            "type": "note",
            "severity": "info",
            "category": "recon",
            "title": "New note",
            "content": "Captured from history",
            "target_ip": "10.10.10.55",
        }
        with patch("ui.controllers.loot_controller.AddLootDialog") as dialog_class:
            dialog = dialog_class.return_value
            dialog.exec.return_value = True
            dialog.get_data.return_value = dialog_data

            self.assertTrue(
                self.loot_ctrl.open_add_dialog(
                    parent_widget=None,
                    target_ip="10.10.10.55",
                    default_type="note",
                    default_category="recon",
                    default_title="New note",
                    default_content="Captured from history",
                )
            )

        dialog_class.assert_called_once_with(
            parent=None,
            target_ip="10.10.10.55",
            default_type="note",
            default_category="recon",
            default_title="New note",
            default_content="Captured from history",
            default_severity="info",
        )
        entries = self.loot_ctrl.get_entries(target_ip="10.10.10.55")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "New note")

    def test_history_controller_domain(self):
        """HistoryController manages clipboard history, filter actions, and publishes events."""
        history_events = []
        logging_events = []
        self.event_bus.subscribe(EventType.HISTORY_UPDATED, lambda d: history_events.append(d))
        self.event_bus.subscribe(
            EventType.LOGGING_STATE_CHANGED, lambda d: logging_events.append(d)
        )

        self.history_ctrl.add_entry("whoami", target_ip="10.10.10.55")
        self.history_ctrl.add_entry("id", target_ip="10.10.10.55")
        self.assertEqual(len(history_events), 2)
        self.assertEqual(set(history_events[0]), {"action", "entry", "history"})
        self.assertEqual(history_events[0]["action"], "add")

        history = self.history_ctrl.get_history()
        self.assertEqual(len(history), 2)

        self.history_ctrl.delete_entry(history[0]["id"])
        self.assertEqual(len(history_events), 3)
        self.assertEqual(history_events[2]["action"], "delete")
        self.assertEqual(history_events[2]["entry"]["id"], history[0]["id"])

        # Toggle pause
        initial_paused = self.history_ctrl.is_paused()
        toggled = self.history_ctrl.toggle_pause()
        self.assertNotEqual(initial_paused, toggled)
        self.assertEqual(len(logging_events), 1)

        # Filter actions
        filter_actions = self.history_ctrl.get_filter_actions()
        self.assertTrue(any(a.id == "history_filter:commands" for a in filter_actions))

        # Clear
        self.history_ctrl.clear_history()
        self.assertEqual(len(self.history_ctrl.get_history()), 0)
        self.assertEqual(len(history_events), 4)
        self.assertEqual(history_events[3]["action"], "clear")
        self.assertIsNone(history_events[3]["entry"])
        self.assertEqual(history_events[3]["history"], [])

    def test_loot_controller_export_loot_uses_report_builder_directly(self):
        """LootController.export_loot must invoke ReportBuilder directly without using deprecated LootManager.export_loot."""
        self.loot_ctrl.add_entry("credentials", "DB User", "db:secret", target_ip="10.10.10.55", category="access")
        out_file = self.temp_path / "controller_loot_export.md"

        with patch.object(self.loot_mgr, "export_loot") as mock_deprecated:
            self.loot_ctrl.export_loot(out_file, target_ip="10.10.10.55")
            mock_deprecated.assert_not_called()

        self.assertTrue(out_file.exists())
        content = out_file.read_text(encoding="utf-8")
        self.assertIn("db:secret", content)
        self.assertIn("DB User", content)

    def test_history_controller_export_report_uses_report_builder_directly(self):
        """HistoryController.export_report_markdown must invoke ReportBuilder directly without using deprecated ClipboardWatcher.export_report_markdown."""
        self.history_ctrl.add_entry("curl -s http://10.10.10.55/admin", target_ip="10.10.10.55")
        out_file = self.temp_path / "controller_history_export.md"

        with patch.object(self.clip_watcher, "export_report_markdown") as mock_deprecated:
            self.history_ctrl.export_report_markdown(out_file, target_ip="10.10.10.55")
            mock_deprecated.assert_not_called()

        self.assertTrue(out_file.exists())
        content = out_file.read_text(encoding="utf-8")
        self.assertIn("curl -s http://10.10.10.55/admin", content)

    def test_loot_controller_notify_persistence_error(self):
        """_notify_persistence_error invokes QMessageBox.critical with parent or activeWindow."""
        from core.storage import PersistenceError

        with patch("ui.controllers.loot_controller.QMessageBox.critical") as mock_crit:
            # 1. With parent_widget
            parent = QWidget()
            err = PersistenceError("disk fail")
            self.loot_ctrl._notify_persistence_error("test_op", err, parent_widget=parent)
            mock_crit.assert_called_once()
            self.assertEqual(mock_crit.call_args[0][0], parent)
            self.assertIn("disk fail", mock_crit.call_args[0][2])

        with patch("ui.controllers.loot_controller.QMessageBox.critical") as mock_crit:
            # 2. Without parent_widget (falls back to activeWindow or None)
            self.loot_ctrl._notify_persistence_error("test_op", err, parent_widget=None)
            mock_crit.assert_called_once()

    def test_loot_controller_error_branches(self):
        """Domain operations handle persistence and validation errors gracefully."""
        from core.storage import StorageError, PersistenceError
        from core.loot_manager import LootValidationError

        # add_entry error
        with patch.object(self.loot_mgr, "add_entry", side_effect=StorageError("cannot add")):
            with patch.object(self.loot_ctrl, "_notify_persistence_error") as mock_notify:
                result = self.loot_ctrl.add_entry("note", "Title", "Content")
                self.assertEqual(result, {})
                mock_notify.assert_called_once()

        # update_entry error
        with patch.object(self.loot_mgr, "update_entry", side_effect=LootValidationError("invalid")):
            with patch.object(self.loot_ctrl, "_notify_persistence_error") as mock_notify:
                result = self.loot_ctrl.update_entry("id1", "Title", "Content")
                self.assertFalse(result)
                mock_notify.assert_called_once()

        # move_entry_to_category error
        with patch.object(self.loot_mgr, "reorder_entry", side_effect=OSError("io error")):
            with patch.object(self.loot_ctrl, "_notify_persistence_error") as mock_notify:
                result = self.loot_ctrl.move_entry_to_category("id1", "recon", 0)
                self.assertFalse(result)
                mock_notify.assert_called_once()

        # delete_entry error
        with patch.object(self.loot_mgr, "delete_entry", side_effect=PersistenceError("io fail")):
            with patch.object(self.loot_ctrl, "_notify_persistence_error") as mock_notify:
                result = self.loot_ctrl.delete_entry("id1")
                self.assertFalse(result)
                mock_notify.assert_called_once()

        # clear_entries error
        with patch.object(self.loot_mgr, "clear_session", side_effect=PersistenceError("cannot clear")):
            with patch.object(self.loot_ctrl, "_notify_persistence_error") as mock_notify:
                self.loot_ctrl.clear_entries()
                mock_notify.assert_called_once()

    def test_loot_controller_clear_loot_dialog(self):
        """clear_loot prompts user when parent_widget provided, or executes immediately."""
        from PyQt6.QtWidgets import QMessageBox

        parent = QWidget()
        self.loot_ctrl.add_entry("note", "Keep me?", "data")

        # 1. User says No
        with patch("ui.controllers.loot_controller.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            result = self.loot_ctrl.clear_loot(parent_widget=parent)
            self.assertFalse(result)
            self.assertEqual(len(self.loot_ctrl.get_entries()), 1)

        # 2. User says Yes
        with patch("ui.controllers.loot_controller.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            result = self.loot_ctrl.clear_loot(parent_widget=parent)
            self.assertTrue(result)
            self.assertEqual(len(self.loot_ctrl.get_entries()), 0)

        # 3. Without parent_widget
        self.loot_ctrl.add_entry("note", "Clear without prompt", "data")
        result = self.loot_ctrl.clear_loot(parent_widget=None)
        self.assertTrue(result)
        self.assertEqual(len(self.loot_ctrl.get_entries()), 0)

    def test_loot_controller_export_entry_to_file_with_feedback(self):
        """export_entry_to_file_with_feedback reports success or warning."""
        parent = QWidget()
        entry = self.loot_ctrl.add_entry("note", "Reported Item", "some content", category="recon")

        # Success case
        with patch("ui.controllers.loot_controller.QMessageBox.information") as mock_info:
            out_path = self.loot_ctrl.export_entry_to_file_with_feedback(entry["id"], parent_widget=parent)
            self.assertIsNotNone(out_path)
            self.assertTrue(out_path.is_file())
            mock_info.assert_called_once()

        # Failure case
        with patch("ui.controllers.loot_controller.QMessageBox.warning") as mock_warn:
            out_path = self.loot_ctrl.export_entry_to_file_with_feedback("non-existent-id", parent_widget=parent)
            self.assertIsNone(out_path)
            mock_warn.assert_called_once()

    def test_loot_controller_filter_pills_and_selection(self):
        """build_filter_pills populates buttons and select_loot_type updates styling and signals."""
        layout = QHBoxLayout()
        selected_types = []
        exports = []
        clears = []
        toggle_views = []
        obsidian_exports = []

        self.loot_ctrl.build_filter_pills(
            pills_layout=layout,
            on_select_type=lambda t: selected_types.append(t),
            on_export=lambda: exports.append(True),
            on_clear=lambda: clears.append(True),
            export_tooltip="Export tooltip",
            on_export_obsidian=lambda: obsidian_exports.append(True),
            on_toggle_view=lambda: toggle_views.append(True),
            view_mode="list",
        )

        # Check buttons were created
        self.assertIn("all", self.loot_ctrl.filter_buttons)
        self.assertIn("credentials", self.loot_ctrl.filter_buttons)

        # Test selecting loot type
        emitted_types = []
        self.loot_ctrl.loot_type_changed.connect(lambda t: emitted_types.append(t))

        self.loot_ctrl.select_loot_type("credentials")
        self.assertEqual(self.loot_ctrl.current_loot_type, "credentials")
        self.assertEqual(emitted_types, ["credentials"])
        self.assertEqual(self.loot_ctrl.filter_buttons["credentials"].property("class"), "FilterPillActive")
        self.assertEqual(self.loot_ctrl.filter_buttons["all"].property("class"), "FilterPill")

        # Test clicking buttons triggers callbacks
        self.loot_ctrl.filter_buttons["all"].click()
        self.assertEqual(selected_types, ["all"])

        btn_view = layout.itemAt(layout.count() - 4).widget()
        btn_view.click()
        self.assertEqual(len(toggle_views), 1)

        btn_exp = layout.itemAt(layout.count() - 3).widget()
        btn_exp.click()
        self.assertEqual(len(exports), 1)

        btn_obs = layout.itemAt(layout.count() - 2).widget()
        btn_obs.click()
        self.assertEqual(len(obsidian_exports), 1)

        btn_clr = layout.itemAt(layout.count() - 1).widget()
        btn_clr.click()
        self.assertEqual(len(clears), 1)

    def test_loot_controller_render_content_and_board(self):
        """render_content handles empty state and cards, render_board_content returns board."""
        layout = QVBoxLayout()
        parent = QWidget()
        proj_dir = self.project_mgr.get_project_dir()
        empty_states = []

        # 1. Empty state
        cards = self.loot_ctrl.render_content(
            content_layout=layout,
            search_query="",
            proj_dir=proj_dir,
            on_delete_loot=lambda _: None,
            on_edit_loot=lambda _: None,
            on_export_loot=lambda _: None,
            parent_widget=parent,
            show_empty_state_fn=lambda msg: empty_states.append(msg),
        )
        self.assertEqual(cards, [])
        self.assertEqual(len(empty_states), 1)

        # 2. Populated list content
        self.loot_ctrl.add_entry("credentials", "Admin Cred", "admin:hunter2", category="access")
        self.loot_ctrl.add_entry("note", "Recon Note", "found port 8080", category="recon")

        cards = self.loot_ctrl.render_content(
            content_layout=layout,
            search_query="",
            proj_dir=proj_dir,
            on_delete_loot=lambda _: None,
            on_edit_loot=lambda _: None,
            on_export_loot=lambda _: None,
            parent_widget=parent,
            show_empty_state_fn=lambda msg: empty_states.append(msg),
        )
        # Should render 2 headers + 2 cards = 4 widgets
        self.assertEqual(len(cards), 4)

        # 3. Populated board content
        board_cards = self.loot_ctrl.render_board_content(
            content_layout=layout,
            search_query="",
            proj_dir=proj_dir,
            on_delete_loot=lambda _: None,
            on_edit_loot=lambda _: None,
            on_export_loot=lambda _: None,
            on_move_loot=lambda e, c, i: True,
            parent_widget=parent,
        )
        self.assertEqual(len(board_cards), 1)

    def test_loot_controller_open_add_dialog_non_modal(self):
        """open_add_dialog non-modal mode creates floating dialog and handles accept/finish."""
        with patch("ui.controllers.loot_controller.AddLootDialog") as MockDialog:
            mock_dlg = MagicMock()
            mock_dlg.isVisible.return_value = False
            mock_dlg.width.return_value = 400
            mock_dlg.height.return_value = 300
            mock_dlg.get_data.return_value = {
                "type": "note",
                "title": "Floating Note",
                "content": "Floating Content",
                "target_ip": "10.10.10.10",
                "category": "recon",
                "severity": "info",
            }
            MockDialog.return_value = mock_dlg

            accepted_callbacks = []
            res = self.loot_ctrl.open_add_dialog(
                modal=False,
                target_ip="10.10.10.10",
                on_accepted=lambda d: accepted_callbacks.append(d),
            )
            self.assertTrue(res)
            self.assertIs(self.loot_ctrl._active_add_dialog, mock_dlg)
            mock_dlg.show.assert_called_once()

            # Second call while visible raises existing dialog
            mock_dlg.isVisible.return_value = True
            res2 = self.loot_ctrl.open_add_dialog(modal=False)
            self.assertTrue(res2)
            mock_dlg.raise_.assert_called()

            # Trigger accepted callback
            connect_accepted = [call[0][0] for call in mock_dlg.accepted.connect.call_args_list]
            self.assertTrue(len(connect_accepted) > 0)
            connect_accepted[0]()
            self.assertEqual(len(accepted_callbacks), 1)
            entries = self.loot_ctrl.get_entries()
            self.assertTrue(any(e["title"] == "Floating Note" for e in entries))

            # Trigger finished callback
            connect_finished = [call[0][0] for call in mock_dlg.finished.connect.call_args_list]
            self.assertTrue(len(connect_finished) > 0)
            connect_finished[0]()
            self.assertIsNone(self.loot_ctrl._active_add_dialog)

    def test_loot_controller_open_edit_dialog(self):
        """open_edit_dialog updates entry on accept and ignores on reject."""
        entry = self.loot_ctrl.add_entry("note", "Original Title", "Original Content")

        with patch("ui.controllers.loot_controller.AddLootDialog") as MockDialog:
            mock_dlg = MagicMock()
            MockDialog.return_value = mock_dlg

            # 1. Accepted
            mock_dlg.exec.return_value = True
            mock_dlg.get_data.return_value = {
                "title": "Edited Title",
                "content": "Edited Content",
                "target_ip": "10.10.10.99",
                "category": "access",
                "type": "credentials",
                "severity": "high",
            }
            res = self.loot_ctrl.open_edit_dialog(QWidget(), entry)
            self.assertTrue(res)
            updated = self.loot_ctrl.get_entries()[0]
            self.assertEqual(updated["title"], "Edited Title")
            self.assertEqual(updated["type"], "credentials")

            # 2. Rejected
            mock_dlg.exec.return_value = False
            res2 = self.loot_ctrl.open_edit_dialog(QWidget(), entry)
            self.assertFalse(res2)


if __name__ == "__main__":
    unittest.main()

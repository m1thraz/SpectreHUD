"""
Unit tests for UI-independent domain controllers and MenuAction DTOs.
Verifies that controllers execute pure business logic without requiring interactive Qt widgets.
"""
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from core.menu_actions import MenuAction
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
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
        self.loot_mgr = LootManager(storage_file=self.temp_path / "loot.json", event_bus=self.event_bus)
        self.clip_watcher = ClipboardWatcher(storage_file=self.temp_path / "clipboard.json", event_bus=self.event_bus)

        self.project_ctrl = ProjectController(self.project_mgr, event_bus=self.event_bus)
        self.cheatsheet_ctrl = CheatsheetController(self.snippet_mgr, event_bus=self.event_bus)
        self.loot_ctrl = LootController(self.loot_mgr, self.project_mgr, event_bus=self.event_bus)
        self.history_ctrl = HistoryController(self.clip_watcher, self.loot_mgr, self.project_mgr, event_bus=self.event_bus)

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
            template="uname -a"
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
            category="access"
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
            category="access"
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
        self.event_bus.subscribe(EventType.LOGGING_STATE_CHANGED, lambda d: logging_events.append(d))

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


if __name__ == "__main__":
    unittest.main()

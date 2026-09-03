"""Tests for core/quick_note_manager.py (Tier 0 pure logic)."""

import unittest
from core.quick_note_manager import QuickNoteManager
from core.storage import InMemoryStorageBackend
from core.event_bus import EventBus, EventType


class TestQuickNoteManager(unittest.TestCase):
    def setUp(self):
        self.storage = InMemoryStorageBackend()
        self.event_bus = EventBus()
        self.manager = QuickNoteManager(storage=self.storage, event_bus=self.event_bus)

    def test_add_entry_creates_valid_note_and_emits_signal(self):
        received_signals = []
        self.manager.entry_added.connect(received_signals.append)

        bus_events = []
        self.event_bus.subscribe(EventType.QUICK_NOTES_UPDATED, bus_events.append)

        entry = self.manager.add_entry("Found open port 8080", category="recon", target_ip="10.10.10.20")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["text"], "Found open port 8080")
        self.assertEqual(entry["category"], "recon")
        self.assertEqual(entry["target_ip"], "10.10.10.20")
        self.assertTrue(entry["id"].startswith("note_"))
        self.assertTrue(bool(entry["timestamp"]))

        # Verify Qt signal emitted
        self.assertEqual(len(received_signals), 1)
        self.assertEqual(received_signals[0]["id"], entry["id"])

        # Verify EventBus event emitted
        self.assertEqual(len(bus_events), 1)
        self.assertEqual(bus_events[0]["action"], "add")
        self.assertEqual(bus_events[0]["entry"]["id"], entry["id"])

    def test_category_normalization_defaults_to_misc(self):
        entry = self.manager.add_entry("Some text", category="invalid_category_name")
        self.assertEqual(entry["category"], "misc")

        # Empty text returns None
        self.assertIsNone(self.manager.add_entry(""))
        self.assertIsNone(self.manager.add_entry("   "))

    def test_get_entries_filtering(self):
        self.manager.add_entry("Note 1", category="recon", target_ip="10.10.10.1")
        self.manager.add_entry("Note 2", category="access", target_ip="10.10.10.2")
        self.manager.add_entry("Note 3 with secret", category="recon", target_ip="10.10.10.2")

        # All
        self.assertEqual(len(self.manager.get_all_entries()), 3)

        # Category filter
        recon_notes = self.manager.get_entries(category="recon")
        self.assertEqual(len(recon_notes), 2)

        # Target IP filter
        target_notes = self.manager.get_entries(target_ip="10.10.10.2")
        self.assertEqual(len(target_notes), 2)

        # Search query filter
        search_notes = self.manager.get_entries(search_query="secret")
        self.assertEqual(len(search_notes), 1)
        self.assertEqual(search_notes[0]["text"], "Note 3 with secret")

    def test_delete_and_clear_entries(self):
        e1 = self.manager.add_entry("Note 1", category="misc")
        e2 = self.manager.add_entry("Note 2", category="misc")
        self.assertEqual(len(self.manager.get_all_entries()), 2)

        # Delete e1
        self.assertTrue(self.manager.delete_entry(e1["id"]))
        self.assertFalse(self.manager.delete_entry(e1["id"]))  # already deleted
        self.assertEqual(len(self.manager.get_all_entries()), 1)

        # Clear all
        self.manager.clear_entries()
        self.assertEqual(len(self.manager.get_all_entries()), 0)

    def test_replace_entries_and_persistence(self):
        raw_list = [
            {"id": "note_1", "text": "First Note", "category": "recon", "target_ip": "10.10.10.5", "timestamp": "2026-09-03 12:00:00"},
            {"id": "note_2", "text": "Second Note", "category": "privesc", "target_ip": "", "timestamp": "2026-09-03 12:01:00"},
        ]
        self.manager.replace_entries(raw_list)
        self.assertEqual(len(self.manager.get_all_entries()), 2)

        # Reload in new manager with same storage
        self.manager.replace_entries_and_persist(raw_list)
        new_manager = QuickNoteManager(storage=self.storage)
        self.assertEqual(len(new_manager.get_all_entries()), 2)
        self.assertEqual(new_manager.get_all_entries()[0]["text"], "First Note")

    def test_allow_multiple_entries_with_identical_text(self):
        e1 = self.manager.add_entry("file:///C:/test.rar", category="recon")
        e2 = self.manager.add_entry("file:///C:/test.rar", category="recon")
        self.assertNotEqual(e1["id"], e2["id"])
        self.assertEqual(len(self.manager.get_all_entries()), 2)


if __name__ == "__main__":
    unittest.main()

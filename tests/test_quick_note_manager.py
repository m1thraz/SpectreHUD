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

    def test_new_fields_and_defaults(self):
        entry = self.manager.add_entry("Test Defaults")
        self.assertEqual(entry["status"], "inbox")
        self.assertFalse(entry["pinned"])
        self.assertIsNone(entry["source"])

        # With explicit values
        src = {"type": "history", "id": "hist_123"}
        custom = self.manager.add_entry(
            "Custom note", status="followup", pinned=True, source=src
        )
        self.assertEqual(custom["status"], "followup")
        self.assertTrue(custom["pinned"])
        self.assertEqual(custom["source"], src)

    def test_legacy_note_compatibility(self):
        legacy = [
            {
                "id": "old_note_1",
                "text": "Old note without new fields",
                "category": "recon",
                "target_ip": "10.10.10.5",
                "timestamp": "2026-09-01 10:00:00",
            }
        ]
        self.manager.replace_entries_and_persist(legacy)
        new_mgr = QuickNoteManager(storage=self.storage)
        notes = new_mgr.get_all_entries()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["status"], "inbox")
        self.assertFalse(notes[0]["pinned"])
        self.assertIsNone(notes[0]["source"])

    def test_update_entry_and_event_bus(self):
        bus_events = []
        self.event_bus.subscribe(EventType.QUICK_NOTES_UPDATED, bus_events.append)

        e = self.manager.add_entry("Original text", category="recon")
        bus_events.clear()

        # Update text and status
        updated = self.manager.update_entry(
            e["id"], text="Updated text", status="followup", pinned=True
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["text"], "Updated text")
        self.assertEqual(updated["status"], "followup")
        self.assertTrue(updated["pinned"])
        self.assertEqual(updated["id"], e["id"])  # ID must remain identical

        # Check persistence
        reloaded = QuickNoteManager(storage=self.storage).get_all_entries()
        self.assertEqual(reloaded[0]["text"], "Updated text")
        self.assertEqual(reloaded[0]["status"], "followup")

        # Check event bus
        self.assertEqual(len(bus_events), 1)
        self.assertEqual(bus_events[0]["action"], "update")
        self.assertEqual(bus_events[0]["entry"]["id"], e["id"])

        # Update non-existent entry returns None
        self.assertIsNone(self.manager.update_entry("non_existent_id", text="ABC"))

        # Empty text update returns None without corrupting note
        self.assertIsNone(self.manager.update_entry(e["id"], text="   "))
        self.assertEqual(self.manager.get_all_entries()[0]["text"], "Updated text")

    def test_sorting_and_status_filtering(self):
        # Add 4 notes
        n1 = self.manager.add_entry("Note 1 - resolved", status="resolved")
        n2 = self.manager.add_entry("Note 2 - inbox", status="inbox")
        n3 = self.manager.add_entry("Note 3 - followup pinned", status="followup", pinned=True)
        n4 = self.manager.add_entry("Note 4 - inbox pinned", status="inbox", pinned=True)

        # get_entries() default sort:
        # Pinned first (n4, n3), unresolved unpinned next (n2), resolved last (n1)
        entries = self.manager.get_entries()
        self.assertEqual([e["id"] for e in entries], [n4["id"], n3["id"], n2["id"], n1["id"]])

        # Filter by status
        followups = self.manager.get_entries(status="followup")
        self.assertEqual(len(followups), 1)
        self.assertEqual(followups[0]["id"], n3["id"])

        resolved = self.manager.get_entries(status="resolved")
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["id"], n1["id"])

        # Filter by pinned
        pinned_notes = self.manager.get_entries(pinned=True)
        self.assertEqual(len(pinned_notes), 2)
        self.assertEqual([e["id"] for e in pinned_notes], [n4["id"], n3["id"]])


if __name__ == "__main__":
    unittest.main()


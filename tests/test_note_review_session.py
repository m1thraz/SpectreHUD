"""
Headless unit tests for QuickNoteReviewSession state machine.
"""

import unittest
from ui.note_review_session import QuickNoteReviewSession


class TestQuickNoteReviewSession(unittest.TestCase):
    """Unit tests for focus review session queue ordering and cycling."""

    def setUp(self) -> None:
        self.session = QuickNoteReviewSession()

    def test_initial_state_and_reset(self) -> None:
        self.assertEqual(self.session.queue_ids, [])
        self.assertEqual(self.session.seen_count, 0)
        self.assertEqual(self.session.completed_count, 0)
        self.assertEqual(self.session.total, 0)
        self.assertFalse(self.session.cycle_notice_pending)

        self.session.seen_count = 5
        self.session.reset()
        self.assertEqual(self.session.seen_count, 0)

    def test_prepare_step_initial_load(self) -> None:
        notes = [
            {"id": "n1", "text": "Note 1"},
            {"id": "n2", "text": "Note 2"},
            {"id": "n3", "text": "Note 3"},
        ]
        entry, show_cycle = self.session.prepare_step(notes)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["id"], "n1")
        self.assertFalse(show_cycle)
        self.assertEqual(self.session.total, 3)
        self.assertEqual(self.session.current_position, 1)

    def test_prepare_step_prunes_missing_entries(self) -> None:
        notes = [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}]
        self.session.prepare_step(notes)

        # External deletion removes n1
        remaining = [{"id": "n2"}, {"id": "n3"}]
        entry, show_cycle = self.session.prepare_step(remaining)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["id"], "n2")
        self.assertEqual(self.session.queue_ids, ["n2", "n3"])

    def test_advance_and_completion_counting(self) -> None:
        notes = [{"id": "n1"}, {"id": "n2"}]
        self.session.prepare_step(notes)

        # Complete n1
        self.session.advance("n1", completed=True)
        self.assertEqual(self.session.completed_count, 1)
        self.assertEqual(self.session.seen_count, 1)
        self.assertEqual(self.session.queue_ids, ["n2"])
        self.assertFalse(self.session.cycle_notice_pending)

        # Advance n2 without completing (e.g. deleted or skipped)
        self.session.advance("n2", completed=False)
        self.assertEqual(self.session.completed_count, 1)
        self.assertEqual(self.session.seen_count, 2)
        self.assertEqual(self.session.queue_ids, [])
        self.assertTrue(self.session.cycle_notice_pending)

    def test_skip_next(self) -> None:
        notes = [{"id": "n1"}, {"id": "n2"}]
        self.session.prepare_step(notes)

        self.session.skip_next()
        self.assertEqual(self.session.queue_ids, ["n2"])
        self.assertEqual(self.session.seen_count, 1)
        self.assertEqual(self.session.completed_count, 0)

    def test_queue_recycling_shows_cycle_notice(self) -> None:
        notes = [{"id": "n1"}]
        self.session.prepare_step(notes)
        self.session.skip_next()
        self.assertTrue(self.session.cycle_notice_pending)

        # Still have n1 eligible
        entry, show_cycle = self.session.prepare_step(notes)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["id"], "n1")
        self.assertTrue(show_cycle)
        self.assertFalse(self.session.cycle_notice_pending)


if __name__ == "__main__":
    unittest.main()

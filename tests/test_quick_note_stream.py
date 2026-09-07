"""Behavioral coverage for the Quick Notes stream and focus review."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from core.event_bus import EventBus
from core.quick_note_manager import QuickNoteManager
from core.storage import InMemoryStorageBackend
from ui.controllers.quick_note_controller import QuickNoteController
from ui.quick_note_card import QuickNoteCard, opacity_for_age
from ui.quick_note_focus_review import QuickNoteFocusReview, QuickNoteReviewSummary


def _entry(entry_id: str, timestamp: str, **changes):
    entry = {
        "id": entry_id,
        "text": f"Note {entry_id}",
        "timestamp": timestamp,
        "category": "recon",
        "target_ip": "10.10.10.10",
        "status": "inbox",
        "pinned": False,
        "source": None,
    }
    entry.update(changes)
    return entry


def _controller(entries):
    event_bus = EventBus()
    manager = QuickNoteManager(storage=InMemoryStorageBackend(), event_bus=event_bus)
    manager.replace_entries(entries)
    return QuickNoteController(
        manager,
        loot_controller=MagicMock(),
        report_controller=MagicMock(),
        event_bus=event_bus,
    )


def _render(controller, parent):
    layout = QVBoxLayout(parent)
    return controller.render_content(layout, "", None, parent, MagicMock())


def test_opacity_thresholds_and_exempt_states(qapp):
    now = datetime(2026, 9, 6, 12, 0, 0)
    assert opacity_for_age(now - timedelta(minutes=10), now) == 1.0
    assert opacity_for_age(now - timedelta(hours=1), now) == 0.85
    assert opacity_for_age(now - timedelta(hours=4), now) == 0.65
    assert opacity_for_age(now - timedelta(hours=12), now) == 0.5

    old = _entry("old", "2026-09-06 04:00:00")
    card = QuickNoteCard(old, now=now)
    assert card.content_container.graphicsEffect().opacity() == 0.5
    assert card.property("overdue") is True
    assert "open for 8 h" in card.lbl_meta.text()

    pinned = QuickNoteCard({**old, "pinned": True}, now=now)
    resolved = QuickNoteCard({**old, "status": "resolved"}, now=now)
    assert pinned.content_container.graphicsEffect().opacity() == 1.0
    assert resolved.content_container.graphicsEffect().opacity() == 1.0
    assert pinned.property("overdue") is False
    assert resolved.property("overdue") is False


def test_stream_row_completion_supports_undo_before_refresh(qapp):
    controller = _controller([_entry("one", "2026-09-06 10:00:00", status="followup")])
    parent = QWidget()
    card = _render(controller, parent)[0]
    updates = []
    controller.notes_updated.connect(lambda: updates.append(True))

    assert controller.begin_completion("one", card) is True
    assert controller.quick_note_manager.get_all_entries()[0]["status"] == "resolved"
    assert card.undo_row.isHidden() is False
    assert card.lbl_content.font().strikeOut() is True
    assert card._completion_timer.isActive()
    assert updates == []

    assert controller.undo_completion("one") is True
    assert controller.quick_note_manager.get_all_entries()[0]["status"] == "followup"
    assert updates == [True]


def test_completion_timer_refreshes_stream_after_undo_window(qapp):
    controller = _controller([_entry("one", "2026-09-06 10:00:00")])
    parent = QWidget()
    card = _render(controller, parent)[0]
    updates = []
    controller.notes_updated.connect(lambda: updates.append(True))

    assert controller.begin_completion("one", card) is True
    assert card._completion_timer.isActive()
    card._completion_timer.timeout.emit()

    assert updates == [True]
    assert controller.quick_note_manager.get_all_entries()[0]["status"] == "resolved"


def test_selection_mode_is_explicit_and_preserves_bulk_selection(qapp):
    controller = _controller([_entry("one", "2026-09-06 10:00:00")])
    parent = QWidget()
    card = _render(controller, parent)[0]
    assert card.chk_select.isHidden()

    controller.selection_mode = True
    parent_two = QWidget()
    selected_card = _render(controller, parent_two)[0]
    assert not selected_card.chk_select.isHidden()
    assert selected_card.btn_complete.isHidden()
    selected_card.chk_select.setChecked(True)
    assert controller.selected_note_ids == {"one"}


def test_toolbar_modes_are_explicit_and_mutually_exclusive(qapp):
    from PyQt6.QtWidgets import QHBoxLayout

    controller = _controller([_entry("one", "2026-09-06 10:00:00")])
    host = QWidget()
    layout = QHBoxLayout(host)
    controller.build_filter_pills(layout, MagicMock(), MagicMock())

    assert controller.btn_select_mode.isCheckable()
    assert controller.btn_review_mode.isCheckable()
    assert not controller.btn_select_mode.icon().isNull()
    assert not controller.btn_review_mode.icon().isNull()

    controller.btn_select_mode.click()
    assert controller.selection_mode is True
    assert controller.review_mode is False

    controller.btn_review_mode.click()
    assert controller.review_mode is True
    assert controller.selection_mode is False


def test_focus_review_is_oldest_first_and_advances_after_actions(qapp):
    controller = _controller(
        [
            _entry("new", "2026-09-06 11:00:00"),
            _entry("old", "2026-09-06 09:00:00"),
        ]
    )
    controller.set_review_mode(True, refresh=False)

    first_parent = QWidget()
    first = _render(controller, first_parent)[0]
    assert isinstance(first, QuickNoteFocusReview)
    assert first.entry["id"] == "old"

    controller._review_complete("old")
    assert controller.quick_note_manager.get_entries(status="resolved")[0]["id"] == "old"
    second_parent = QWidget()
    second = _render(controller, second_parent)[0]
    assert isinstance(second, QuickNoteFocusReview)
    assert second.entry["id"] == "new"

    controller._review_delete("new")
    summary_parent = QWidget()
    assert _render(controller, summary_parent) == []
    assert summary_parent.findChild(QuickNoteReviewSummary) is not None
    assert controller._review_completed_count == 2


def test_focus_review_can_edit_the_current_note(qapp):
    controller = _controller([_entry("one", "2026-09-06 10:00:00")])
    controller.set_review_mode(True, refresh=False)
    parent = QWidget()
    review = _render(controller, parent)[0]
    controller.open_edit_dialog = MagicMock(return_value=True)

    review.btn_edit.click()

    controller.open_edit_dialog.assert_called_once_with(parent, review.entry)


def test_focus_review_saves_note_text_inline(qapp):
    controller = _controller([_entry("one", "2026-09-06 10:00:00")])
    controller.set_review_mode(True, refresh=False)
    parent = QWidget()
    review = _render(controller, parent)[0]

    review.editor.setPlainText("Updated during focused review")
    assert review.btn_save_text.isEnabled()
    review.editor.save_requested.emit()

    saved = controller.quick_note_manager.get_all_entries()[0]
    assert saved["text"] == "Updated during focused review"
    assert not review.btn_save_text.isEnabled()


def test_focus_next_advances_without_counting_completion(qapp):
    controller = _controller([_entry("one", "2026-09-06 10:00:00")])
    controller.set_review_mode(True, refresh=False)
    parent = QWidget()
    _render(controller, parent)

    controller._review_next()
    summary_parent = QWidget()
    assert _render(controller, summary_parent) == []
    assert summary_parent.findChild(QuickNoteReviewSummary) is not None
    assert controller._review_completed_count == 0

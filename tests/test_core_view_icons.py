"""Regression coverage for QtAwesome actions in the frequently used core views."""

from unittest.mock import MagicMock

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ui.history_card import HistoryCard
from ui.loot_card import LootCard
from ui.quick_note_card import QuickNoteCard
from ui.snippet_card import SnippetCard
from ui.controllers.history_controller import HistoryController
from ui.controllers.quick_note_controller import QuickNoteController


def _assert_icon_only(button: QPushButton) -> None:
    assert button.text() == ""
    assert not button.icon().isNull()
    assert button.toolTip()


def test_snippet_card_uses_icons_for_universal_actions(qapp):
    card = SnippetCard(
        {
            "id": "custom-1",
            "title": "Custom",
            "template": "whoami",
            "category": "custom",
            "is_custom": True,
            "is_favorite": False,
        },
        {},
    )

    for button in (card.btn_fav, card.btn_delete, card.btn_tweak, card.btn_copy):
        _assert_icon_only(button)

    inactive_key = card.btn_fav.icon().cacheKey()
    card.btn_fav.click()
    assert card.btn_fav.property("class") == "StarBtnActive"
    assert card.btn_fav.icon().cacheKey() != inactive_key


def test_snippet_copy_feedback_timer_is_owned_by_card(qapp):
    card = SnippetCard(
        {
            "id": "custom-1",
            "title": "Custom",
            "template": "whoami",
            "category": "custom",
            "is_custom": True,
        },
        {},
    )

    card._perform_clipboard_copy("whoami")

    timer = card._copy_reset_timers[card.btn_copy]
    assert timer.parent() is card
    assert timer.isActive()


def test_loot_card_uses_icons_for_card_actions(qapp):
    card = LootCard(
        {"id": "loot-1", "title": "Finding", "content": "secret", "category": "recon"}
    )

    for button in (
        card.btn_edit,
        card.btn_export_file,
        card.btn_export_obsidian,
        card.btn_delete,
        card.btn_copy,
    ):
        _assert_icon_only(button)


def test_quick_note_card_keeps_only_primary_and_copy_actions_visible(qapp):
    card = QuickNoteCard(
        {"id": "note-1", "text": "Follow this up", "status": "inbox", "category": "misc"}
    )

    for button in (card.btn_complete, card.btn_copy):
        _assert_icon_only(button)

    context_actions = [action for action in card._build_context_menu().actions() if not action.isSeparator()]
    assert context_actions
    assert all(not action.icon().isNull() for action in context_actions)


def test_history_card_uses_icons_and_keeps_capture_text(qapp):
    card = HistoryCard(
        {"id": "history-1", "text": "id", "timestamp": "12:00", "char_count": 2}
    )

    _assert_icon_only(card.btn_copy)
    assert card.btn_promote.text()
    assert not card.btn_promote.icon().isNull()
    assert not hasattr(card, "btn_delete")


def test_contextual_core_view_actions_use_icon_plus_text(qapp):
    parent = QWidget()

    notes = QuickNoteController(MagicMock())
    bulk_bar = notes._create_bulk_bar(parent)
    bulk_buttons = bulk_bar.findChildren(QPushButton)
    assert bulk_buttons
    assert all(button.text() and not button.icon().isNull() for button in bulk_buttons)

    watcher = MagicMock()
    watcher.get_history.return_value = []
    history = HistoryController(
        watcher,
        MagicMock(),
        MagicMock(),
        clipboard_monitor=watcher,
    )
    pills_host = QWidget()
    pills_layout = QHBoxLayout(pills_host)
    history.build_filter_pills(pills_layout, lambda _filter: None, lambda: None, lambda: None, "Export")
    contextual = [
        button
        for button in pills_host.findChildren(QPushButton)
        if button.text() in {"Generate Draft (.md)", "Clear"}
    ]
    assert len(contextual) == 2
    assert all(not button.icon().isNull() for button in contextual)

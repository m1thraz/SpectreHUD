"""Regression coverage for layout-derived Cheatsheet scroll ranges."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication, QSizePolicy

from core.clipboard_watcher import ClipboardWatcher
from core.config import ConfigManager
from core.loot_manager import LootManager
from core.project import ProjectManager
from core.snippet_manager import SnippetManager
from ui.main_window import MainWindow
from ui.snippet_card import SnippetCard


pytestmark = pytest.mark.integration


@pytest.fixture
def cheatsheet_window(tmp_path, qapp):
    config_dir = tmp_path / "config"
    window = MainWindow(
        config_manager=ConfigManager(config_dir=config_dir),
        snippet_manager=SnippetManager(
            user_snippets_path=config_dir / "user_snippets.json",
            favorites_path=config_dir / "user_favorites.json",
            language="en",
        ),
        loot_manager=LootManager(storage_file=config_dir / "loot.json"),
        clipboard_watcher=ClipboardWatcher(storage_file=config_dir / "history.json"),
        project_manager=ProjectManager(base_dir=tmp_path / "projects"),
    )
    window.resize(900, 700)
    window.show()
    window.app.refresh_content()
    for _ in range(3):
        qapp.processEvents()

    yield window

    window.hide()
    window.close()
    qapp.processEvents()


def _assert_last_card_matches_content_bottom(window: MainWindow) -> None:
    cards = [card for card in window.cards if isinstance(card, SnippetCard)]
    assert cards

    layout = window.content_panel.content_layout
    container = window.content_panel.content_container
    last_card = cards[-1]
    bottom_margin = layout.contentsMargins().bottom()
    expected_bottom = last_card.geometry().bottom() + 1 + bottom_margin

    normal_layout_slack = 2 * (bottom_margin + layout.spacing())
    assert abs(container.sizeHint().height() - expected_bottom) <= normal_layout_slack

    scroll = window.content_panel.scroll_area
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    QApplication.processEvents()
    last_bottom_in_viewport = last_card.mapTo(
        scroll.viewport(), QPoint(0, last_card.height())
    ).y()
    trailing_space = scroll.viewport().height() - last_bottom_in_viewport
    if scroll.verticalScrollBar().maximum() == 0:
        return

    assert -4 <= trailing_space <= bottom_margin + (2 * layout.spacing()) + 12, (
        f"trailing={trailing_space}, hint={container.sizeHint().height()}, "
        f"minimum_hint={container.minimumSizeHint().height()}, "
        f"layout_minimum={layout.minimumSize().height()}, "
        f"height_for_width={layout.heightForWidth(container.width())}, "
        f"container={container.height()}, last_bottom={last_card.geometry().bottom() + 1}, "
        f"viewport={scroll.viewport().height()}, maximum={scroll.verticalScrollBar().maximum()}, "
        f"value={scroll.verticalScrollBar().value()}"
    )


def test_full_cheatsheet_has_no_large_empty_scroll_area(cheatsheet_window):
    command_policy = cheatsheet_window.cards[0].lbl_command.sizePolicy()
    assert command_policy.horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert cheatsheet_window.content_panel.scroll_area.verticalScrollBar().maximum() > 0
    _assert_last_card_matches_content_bottom(cheatsheet_window)


def test_search_reduces_scroll_range_without_stale_content_height(cheatsheet_window):
    scroll = cheatsheet_window.content_panel.scroll_area
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    assert scroll.verticalScrollBar().value() > 0

    cheatsheet_window.search_panel.search_bar.txt_search.setText("hashcat")
    cheatsheet_window.search_panel.search_bar._emit_search_changed()
    for _ in range(3):
        QApplication.processEvents()

    assert 2 <= len(cheatsheet_window.cards) <= 3
    assert scroll.verticalScrollBar().maximum() == 0
    assert scroll.verticalScrollBar().value() == 0
    _assert_last_card_matches_content_bottom(cheatsheet_window)

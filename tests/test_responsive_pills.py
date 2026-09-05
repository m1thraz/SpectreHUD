"Unit and integration tests for responsive cheatsheet category pills and adaptive overflow."

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QWidget, QHBoxLayout
from PyQt6.QtGui import QFontMetrics, QFont

from core.snippets.manager import SnippetManager
from ui.controllers.cheatsheet_controller import (
    CheatsheetController,
    _order_categories,
)


@pytest.fixture
def snippet_manager(tmp_path):
    sm = SnippetManager(
        user_snippets_path=tmp_path / "user_snippets.json",
        favorites_path=tmp_path / "favorites.json",
        language="en",
    )
    return sm


@pytest.fixture
def controller(snippet_manager):
    return CheatsheetController(snippet_manager=snippet_manager)


def test_order_categories_preserves_priority(controller):
    cats = controller.snippet_manager.get_categories()
    ordered = _order_categories(cats)

    ordered_ids = [c["id"] for c in ordered]
    assert "all" in ordered_ids
    assert "favorites" in ordered_ids

    # Verify that all comes first, then favorites
    assert ordered_ids[0] == "all"
    assert ordered_ids[1] == "favorites"

    # All unique categories preserved
    assert len(ordered_ids) == len(cats)
    assert set(ordered_ids) == {c["id"] for c in cats}


def test_calculate_visible_count_adapts_to_width(controller, qapp):
    cats = controller.snippet_manager.get_categories()
    ordered = _order_categories(cats)
    font_metrics = QFontMetrics(QFont())

    # 1. Extremely narrow width: should show at least 1 button + more
    count_narrow = controller._calculate_visible_count(
        available_width=250,
        ordered_cats=ordered,
        font_metrics=font_metrics,
        spacing=6,
    )
    assert 1 <= count_narrow < len(ordered)

    # 2. Medium width: should show more buttons
    count_med = controller._calculate_visible_count(
        available_width=600,
        ordered_cats=ordered,
        font_metrics=font_metrics,
        spacing=6,
    )
    assert count_narrow < count_med < len(ordered)

    # 3. Very wide width: all categories fit!
    count_wide = controller._calculate_visible_count(
        available_width=3000,
        ordered_cats=ordered,
        font_metrics=font_metrics,
        spacing=6,
    )
    assert count_wide == len(ordered)


def test_build_filter_pills_creates_overflow_button_when_needed(controller, qapp):
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(12, 2, 12, 6)
    layout.setSpacing(6)

    selected = []

    def on_select(cid):
        selected.append(cid)

    # Call with 500px width (requires overflow)
    controller.build_filter_pills(layout, on_select, available_width=500)

    # Check that filter buttons were added
    assert len(controller.filter_buttons) > 0
    # Check that btn_more exists and has overflow categories
    assert controller.btn_more is not None
    assert len(controller._overflow_cat_ids) > 0

    # Total categories accounted for:
    total = len(controller.filter_buttons) + len(controller._overflow_cat_ids)
    all_cats = controller.snippet_manager.get_categories()
    assert total == len(all_cats)

    # The last widget in layout is btn_more
    widgets = [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]
    assert widgets[-1] == controller.btn_more


def test_build_filter_pills_no_overflow_when_super_wide(controller, qapp):
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(12, 2, 12, 6)
    layout.setSpacing(6)

    # Call with 4000px width (all fit!)
    controller.build_filter_pills(layout, lambda cid: None, available_width=4000)

    assert controller.btn_more is None
    assert len(controller._overflow_cat_ids) == 0
    all_cats = controller.snippet_manager.get_categories()
    assert len(controller.filter_buttons) == len(all_cats)


def test_update_pills_width_zero_thrashing(controller, qapp):
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(12, 2, 12, 6)
    layout.setSpacing(6)

    controller.build_filter_pills(layout, lambda cid: None, available_width=600)
    initial_count = controller._last_visible_count

    # Slight width change (e.g. 5px) should NOT rebuild
    rebuilt = controller.update_pills_width(605, lambda cid: None, layout)
    assert rebuilt is False
    assert controller._last_visible_count == initial_count

    # Large width change (e.g. +300px) SHOULD rebuild
    rebuilt_large = controller.update_pills_width(950, lambda cid: None, layout)
    assert rebuilt_large is True
    assert controller._last_visible_count > initial_count


def test_select_category_updates_more_button_label(controller, qapp):
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(12, 2, 12, 6)
    layout.setSpacing(6)

    controller.build_filter_pills(layout, lambda cid: None, available_width=500)
    assert controller.btn_more is not None
    assert len(controller._overflow_cat_ids) > 0

    overflow_target = controller._overflow_cat_ids[0]
    controller.select_category(overflow_target)

    # btn_more should now indicate the active overflow category
    assert controller.btn_more.property("class") == "FilterPillActive"
    assert "\u25be" in controller.btn_more.text()

    # Selecting a primary category should revert btn_more
    controller.select_category("all")
    assert controller.btn_more.property("class") == "FilterPill"
    assert controller.filter_buttons["all"].property("class") == "FilterPillActive"

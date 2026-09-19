"""
Unit tests for QuickFindPopup spotlight search HUD.
"""

from typing import List
from unittest.mock import MagicMock, patch
import pytest
from PyQt6.QtCore import Qt, QEvent, QPointF
from PyQt6.QtGui import QMouseEvent

from ui.quick_find_popup import QuickFindPopup


@pytest.fixture
def mock_cheatsheet_ctrl():
    ctrl = MagicMock()
    snippets = [
        {
            "id": f"snip_{i}",
            "title": f"Snippet {i}",
            "category": "linux_shell",
            "subcategory": "recon",
            "template": f"nmap -sV -p {{{{TARGET_IP}}}} --script snip_{i}",
        }
        for i in range(10)
    ]
    ctrl.get_snippets.return_value = snippets
    return ctrl


@pytest.fixture
def sample_variables():
    return {"target_ip": "10.10.10.123", "attacker_ip": "10.10.14.5"}


def test_quick_find_popup_init(qapp, mock_cheatsheet_ctrl, sample_variables):
    popup = QuickFindPopup(
        cheatsheet_controller=mock_cheatsheet_ctrl,
        variable_provider=lambda: sample_variables,
    )
    assert popup.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert popup.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert popup.layout().count() == 1
    assert popup.layout().itemAt(0).widget() is popup.card
    popup.show()
    qapp.processEvents()
    assert popup.card.width() >= 500
    assert popup.card.height() >= 300
    assert popup.search_input.text() == ""
    assert popup._current_results == []
    popup.close()


def test_quick_find_margin_click_closes(qapp, mock_cheatsheet_ctrl, sample_variables):
    popup = QuickFindPopup(
        cheatsheet_controller=mock_cheatsheet_ctrl,
        variable_provider=lambda: sample_variables,
    )
    popup.show()
    qapp.processEvents()
    assert popup.isVisible()

    margin_event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(1.0, 1.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    popup.mousePressEvent(margin_event)
    assert not popup.isVisible()


def test_quick_find_focus_loss_dismissal(qapp, mock_cheatsheet_ctrl, sample_variables):
    popup = QuickFindPopup(
        cheatsheet_controller=mock_cheatsheet_ctrl,
        variable_provider=lambda: sample_variables,
    )
    popup.show()
    qapp.processEvents()
    popup._has_been_active = True

    event = QEvent(QEvent.Type.ActivationChange)
    with patch.object(popup, "isActiveWindow", return_value=False):
        popup.changeEvent(event)
    assert not popup.isVisible()


def test_quick_find_arm_autoclose(qapp, mock_cheatsheet_ctrl, sample_variables):
    popup = QuickFindPopup(
        cheatsheet_controller=mock_cheatsheet_ctrl,
        variable_provider=lambda: sample_variables,
    )
    popup.show()
    qapp.processEvents()
    popup._has_been_active = False
    popup._arm_autoclose()
    assert popup._has_been_active
    popup.close()


def test_quick_find_empty_input_no_results(qapp, mock_cheatsheet_ctrl, sample_variables):
    popup = QuickFindPopup(
        cheatsheet_controller=mock_cheatsheet_ctrl,
        variable_provider=lambda: sample_variables,
    )
    popup._on_search_changed("")
    assert popup._current_results == []
    assert not popup.lbl_status.isHidden()
    mock_cheatsheet_ctrl.get_snippets.assert_not_called()
    popup.close()


def test_quick_find_search_enforces_max_5_results(qapp, mock_cheatsheet_ctrl, sample_variables):
    popup = QuickFindPopup(
        cheatsheet_controller=mock_cheatsheet_ctrl,
        variable_provider=lambda: sample_variables,
    )
    popup._on_search_changed("nmap")
    mock_cheatsheet_ctrl.get_snippets.assert_called_once_with(
        category_id="all", search_query="nmap"
    )
    assert len(popup._current_results) == 5
    assert len(popup._result_widgets) == 5
    assert popup._selected_index == 0
    assert popup._result_widgets[0]._is_selected
    popup.close()


def test_quick_find_no_matching_results(qapp, mock_cheatsheet_ctrl, sample_variables):
    mock_cheatsheet_ctrl.get_snippets.return_value = []
    popup = QuickFindPopup(
        cheatsheet_controller=mock_cheatsheet_ctrl,
        variable_provider=lambda: sample_variables,
    )
    popup._on_search_changed("nonexistent_command_xyz")
    assert popup._current_results == []
    assert len(popup._result_widgets) == 0
    assert not popup.lbl_status.isHidden()
    popup.close()


def test_quick_find_arrow_navigation(qapp, mock_cheatsheet_ctrl, sample_variables):
    popup = QuickFindPopup(
        cheatsheet_controller=mock_cheatsheet_ctrl,
        variable_provider=lambda: sample_variables,
    )
    popup._on_search_changed("nmap")

    assert popup._selected_index == 0

    # Down arrow -> index 1
    popup._select_next()
    assert popup._selected_index == 1
    assert popup._result_widgets[1]._is_selected
    assert not popup._result_widgets[0]._is_selected

    # Up arrow -> index 0
    popup._select_prev()
    assert popup._selected_index == 0

    # Up arrow from 0 wraps to 4
    popup._select_prev()
    assert popup._selected_index == 4
    popup.close()


def test_quick_find_copy_interpolates_variables(qapp, mock_cheatsheet_ctrl, sample_variables):
    popup = QuickFindPopup(
        cheatsheet_controller=mock_cheatsheet_ctrl,
        variable_provider=lambda: sample_variables,
    )
    popup._on_search_changed("nmap")

    copied_signals: List[str] = []
    popup.snippet_copied.connect(copied_signals.append)

    popup._copy_selected()

    assert len(copied_signals) == 1
    # Template was "nmap -sV -p {{TARGET_IP}} --script snip_0"
    # Interpolated should have replaced TARGET_IP with 10.10.10.123
    assert "10.10.10.123" in copied_signals[0]
    assert "snip_0" in copied_signals[0]
    popup.close()


def test_quick_find_row_click_copies(qapp, mock_cheatsheet_ctrl, sample_variables):
    popup = QuickFindPopup(
        cheatsheet_controller=mock_cheatsheet_ctrl,
        variable_provider=lambda: sample_variables,
    )
    popup._on_search_changed("nmap")

    copied_signals: List[str] = []
    popup.snippet_copied.connect(copied_signals.append)

    # Click row 2
    row2 = popup._result_widgets[2]
    row2.clicked.emit(row2.snippet)

    assert len(copied_signals) == 1
    assert "snip_2" in copied_signals[0]
    popup.close()


def test_quick_find_shortcuts_resolution():
    from core.shortcuts import get_shortcuts
    from core.config import ConfigManager

    # Fallback / None config
    shortcuts = get_shortcuts(config_manager=None)
    find_sc = [s for s in shortcuts if s.id == "global_quick_find"]
    assert len(find_sc) == 1
    assert find_sc[0].sequence == "Ctrl+Alt+F"

    # With ConfigManager custom hotkey
    cfg = ConfigManager()
    cfg.set("quick_find_hotkey", "<ctrl>+<shift>+f")
    custom_shortcuts = get_shortcuts(config_manager=cfg)
    custom_find_sc = [s for s in custom_shortcuts if s.id == "global_quick_find"]
    assert len(custom_find_sc) == 1
    assert custom_find_sc[0].sequence == "Ctrl+Shift+F"

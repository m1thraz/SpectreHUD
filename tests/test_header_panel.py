"""Tests for the HUD header panel controls."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.panels.header_panel import HeaderPanel
from ui.styles import build_app_theme
from ui.styles.palette import CYBER_DARK_PALETTE


def test_close_button_emits_close_requested(qapp):
    header = HeaderPanel()
    assert header.btn_close.property("class") == "CloseBtn"
    assert header.btn_close.toolTip()

    emitted = []
    header.close_requested.connect(lambda: emitted.append(True))
    header.btn_close.click()
    assert emitted == [True]
    header.deleteLater()


def test_minimize_button_emits_minimize_requested(qapp):
    header = HeaderPanel()
    emitted = []
    header.minimize_requested.connect(lambda: emitted.append(True))
    header.btn_minimize.click()
    assert emitted == [True]
    header.deleteLater()


def test_close_button_is_styled_by_central_theme():
    qss = build_app_theme(CYBER_DARK_PALETTE)
    assert "QPushButton.CloseBtn" in qss
    assert "QPushButton.CloseBtn:hover" in qss


def test_notes_mode_button_and_badge(qapp):
    header = HeaderPanel()
    assert hasattr(header, "btn_mode_notes")
    assert "Notes" in header.btn_mode_notes.text()
    assert header.btn_mode_notes.property("class") == "ModeSwitchBtn"

    emitted_modes = []
    header.mode_changed.connect(emitted_modes.append)
    header.btn_mode_notes.click()
    assert emitted_modes == ["notes"]

    # Test active styling
    header.set_active_mode("notes")
    assert header.btn_mode_notes.property("class") == "ModeSwitchBtnActive"
    assert header.btn_mode_history.property("class") == "ModeSwitchBtn"

    # Header notes pill must remain clean without count badge
    header.update_notes_badge(5)
    assert header.btn_mode_notes.text() == "Notes"
    assert "[5]" not in header.btn_mode_notes.text()

    header.update_notes_badge(0)
    assert header.btn_mode_notes.text() == "Notes"

    header.deleteLater()


def test_project_button_class_and_theme(qapp):
    header = HeaderPanel()
    assert header.btn_project.property("class") in ("ProjectSelectBtn", "ProjectDropdownBtn")
    qss = build_app_theme(CYBER_DARK_PALETTE)
    assert f"QPushButton.{header.btn_project.property('class')}" in qss
    header.deleteLater()


def test_header_icons_and_divider(qapp):
    header = HeaderPanel()
    # Check icons on action buttons
    assert not header.btn_quick_note.icon().isNull()
    assert not header.btn_screenshot.icon().isNull()
    assert not header.btn_settings.icon().isNull()
    assert not header.btn_rec_indicator.icon().isNull()

    # Check separator exists and is styled
    assert hasattr(header, "nav_separator")
    assert header.nav_separator.property("class") == "HeaderDivider"
    qss = build_app_theme(CYBER_DARK_PALETTE)
    assert "HeaderDivider" in qss

    header.deleteLater()


def test_rec_indicator_icon_toggle(qapp):
    header = HeaderPanel()
    assert "REC: Off" in header.btn_rec_indicator.text()
    assert not header.btn_rec_indicator.icon().isNull()

    header.update_rec_indicator(True)
    assert "REC: ON" in header.btn_rec_indicator.text()
    assert not header.btn_rec_indicator.icon().isNull()

    header.update_rec_indicator(False)
    assert "REC: Off" in header.btn_rec_indicator.text()
    assert not header.btn_rec_indicator.icon().isNull()

    header.deleteLater()


def test_header_action_overflow_progressive(qapp):
    header = HeaderPanel()
    assert hasattr(header, "btn_overflow")
    assert header.btn_overflow.property("class") == "ScreenshotBtn"
    assert not header.btn_overflow.icon().isNull()

    # 1. Very wide width: all 3 action buttons fit (visible_count == 3)
    assert header._calculate_visible_action_count(1600) == 3
    header.update_overflow_state(1600)
    assert not header.btn_quick_note.isHidden()
    assert not header.btn_screenshot.isHidden()
    assert not header.btn_rec_indicator.isHidden()
    assert header.btn_overflow.isHidden()

    # 2. Narrow width: 0 fit, all collapsed into overflow (visible_count == 0)
    assert header._calculate_visible_action_count(600) == 0
    header.update_overflow_state(600)
    assert header.btn_quick_note.isHidden()
    assert header.btn_screenshot.isHidden()
    assert header.btn_rec_indicator.isHidden()
    assert not header.btn_overflow.isHidden()

    # 3. Dynamic resizeEvent handler tests
    from PyQt6.QtGui import QResizeEvent
    from PyQt6.QtCore import QSize

    header.resizeEvent(QResizeEvent(QSize(1600, 40), QSize(600, 40)))
    assert not header.btn_quick_note.isHidden()
    assert not header.btn_screenshot.isHidden()
    assert not header.btn_rec_indicator.isHidden()
    assert header.btn_overflow.isHidden()

    header.resizeEvent(QResizeEvent(QSize(500, 40), QSize(1600, 40)))
    assert header.btn_quick_note.isHidden()
    assert not header.btn_overflow.isHidden()

    header.deleteLater()


def test_overflow_menu_actions_and_signals(qapp):
    header = HeaderPanel()
    # Force 0 visible so all 3 actions are in overflow
    header.update_overflow_state(500)
    menu = header._build_overflow_menu()
    actions = menu.actions()

    # Must contain Note, Snip, Separator, and REC
    assert len(actions) >= 4
    note_act = actions[0]
    snip_act = actions[1]
    rec_act = actions[3]

    assert "Note" in note_act.text()
    assert "Snip" in snip_act.text()
    assert "REC" in rec_act.text()

    emitted = []
    header.quick_note_requested.connect(lambda: emitted.append("note"))
    header.screenshot_requested.connect(lambda: emitted.append("snip"))
    header.toggle_rec_requested.connect(lambda: emitted.append("rec"))

    note_act.trigger()
    snip_act.trigger()
    rec_act.trigger()

    assert emitted == ["note", "snip", "rec"]
    header.deleteLater()


def test_overflow_menu_contains_only_hidden_actions(qapp):
    header = HeaderPanel()
    # Manually simulate k=2: Note & Snip visible, REC hidden
    header.btn_quick_note.setVisible(True)
    header.btn_screenshot.setVisible(True)
    header.btn_rec_indicator.setVisible(False)

    menu = header._build_overflow_menu()
    action_texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert len(action_texts) == 1
    assert "REC" in action_texts[0]

    # Simulate k=1: Note visible, Snip & REC hidden
    header.btn_quick_note.setVisible(True)
    header.btn_screenshot.setVisible(False)
    header.btn_rec_indicator.setVisible(False)

    menu = header._build_overflow_menu()
    action_texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert len(action_texts) == 2
    assert "Snip" in action_texts[0]
    assert "REC" in action_texts[1]

    header.deleteLater()


def test_overflow_rec_state_reflection(qapp):
    header = HeaderPanel()
    # When REC is in overflow and active:
    header.btn_rec_indicator.setVisible(False)
    header.update_rec_indicator(True)
    assert "REC" in header.btn_overflow.toolTip()

    menu = header._build_overflow_menu()
    rec_acts = [a for a in menu.actions() if "REC" in a.text()]
    assert len(rec_acts) == 1
    assert "Pause" in rec_acts[0].text() or "ON" in rec_acts[0].text()

    header.update_rec_indicator(False)
    menu = header._build_overflow_menu()
    rec_acts = [a for a in menu.actions() if "REC" in a.text()]
    assert len(rec_acts) == 1
    assert "Off" in rec_acts[0].text() or "Start" in rec_acts[0].text()

    header.deleteLater()



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

    # Test badge update
    header.update_notes_badge(5)
    assert "[5]" in header.btn_mode_notes.text()

    header.update_notes_badge(0)
    assert "[0]" not in header.btn_mode_notes.text()
    assert "Notes" in header.btn_mode_notes.text()

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


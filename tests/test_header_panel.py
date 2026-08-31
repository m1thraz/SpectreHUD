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

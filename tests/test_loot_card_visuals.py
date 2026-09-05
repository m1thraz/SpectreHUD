"""Tests for LootCard visual tactile design, cursor transitions, and board spacing."""

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QLabel

from core.loot.manager import CATEGORIES
from ui.loot_card import LootCard
from ui.loot_board import LootBoardDropArea


def test_loot_card_has_card_styling_and_open_hand_cursor(qapp):
    entry = {
        "id": "card-visual-1",
        "type": "credentials",
        "category": "access",
        "title": "Database Admin Creds",
        "content": "postgres:secret",
    }
    card = LootCard(entry)
    card.resize(260, 120)
    card.show()
    qapp.processEvents()

    assert card.objectName() == "lootCard"
    assert card.frameShape() == QFrame.Shape.StyledPanel
    assert card.cursor().shape() == Qt.CursorShape.OpenHandCursor

    # Verify drag handle grip icon exists
    assert hasattr(card, "lbl_grip")
    assert isinstance(card.lbl_grip, QLabel)
    assert not card.lbl_grip.pixmap().isNull()
    assert len(card.lbl_grip.toolTip()) > 0

    card.hide()
    card.deleteLater()


def test_loot_card_cursor_transitions_on_press_and_release(qapp):
    entry = {
        "id": "card-visual-2",
        "type": "note",
        "category": "recon",
        "title": "Target Recon Note",
        "content": "Notes here",
    }
    card = LootCard(entry)
    card.resize(260, 120)
    card.show()
    qapp.processEvents()

    assert card.cursor().shape() == Qt.CursorShape.OpenHandCursor

    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(20.0, 20.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    card.mousePressEvent(press_event)
    assert card.cursor().shape() == Qt.CursorShape.ClosedHandCursor

    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(20.0, 20.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    card.mouseReleaseEvent(release_event)
    assert card.cursor().shape() == Qt.CursorShape.OpenHandCursor

    card.hide()
    card.deleteLater()


def test_loot_board_drop_area_spacing_and_margins(qapp):
    area = LootBoardDropArea(CATEGORIES[0], lambda _id, _cat, _idx: True)
    margins = area.cards_layout.contentsMargins()

    assert margins.left() == 4
    assert margins.top() == 4
    assert margins.right() == 4
    assert margins.bottom() == 4
    assert area.cards_layout.spacing() == 8

    area.deleteLater()

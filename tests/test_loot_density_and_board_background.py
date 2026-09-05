"""Tests for LootBoard background styling, LootCard density modes, and action hover states."""

import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, QPointF
from PyQt6.QtGui import QCursor, QEnterEvent
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from ui.loot_board import LootBoard
from ui.loot_card import LootCard
from ui.controllers.loot_controller import LootController
from ui.styles.cards import CARDS_QSS_TEMPLATE


def test_loot_board_autofill_background_and_qss_rule(qapp):
    entries = [
        {
            "id": "loot_1",
            "type": "note",
            "category": "recon",
            "title": "Subdomains",
            "content": "api.domain.com",
        }
    ]
    with tempfile.TemporaryDirectory() as tmp_dir:
        board = LootBoard(
            entries=entries,
            project_dir=Path(tmp_dir),
            on_delete=lambda _: None,
            on_edit=lambda _: None,
            on_export=lambda _: None,
            on_move=lambda *_: True,
        )
        assert board.property("class") == "LootBoard"
        assert board.viewport().autoFillBackground() is True
        assert 'QScrollArea[class="LootBoard"]' in CARDS_QSS_TEMPLATE
        assert "{LOOT_COLUMN_SURFACE}" in CARDS_QSS_TEMPLATE
        board.deleteLater()


def test_loot_card_comfortable_mode_hover_actions_and_delete_icon(qapp):
    entry = {
        "id": "loot_c1",
        "type": "note",
        "category": "recon",
        "title": "Port Scan",
        "content": "22, 80, 443 open",
        "target_ip": "10.10.10.1",
        "timestamp": "2026-09-05 12:00:00",
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Move cursor away so resting state doesn't trigger synthetic enter
        QCursor.setPos(QPoint(2000, 2000))

        card = LootCard(
            entry,
            project_dir=Path(tmp_dir),
            board_mode=True,
            density="comfortable",
        )
        card.move(100, 100)
        card.resize(260, 160)
        card.show()
        qapp.processEvents()

        assert card.density == "comfortable"
        assert card.property("cardDensity") == "comfortable"
        assert card._action_bar_widget is not None
        assert not card._action_bar_widget.isVisible()
        assert card.lbl_content.isVisible()

        # Simulate hover enter on card
        enter_event = QEnterEvent(
            QPointF(10.0, 10.0),
            QPointF(10.0, 10.0),
            QPointF(10.0, 10.0),
        )
        card.enterEvent(enter_event)
        assert card._action_bar_widget.isVisible()

        # Test delete button hover color swap
        event_enter = QEvent(QEvent.Type.Enter)
        event_leave = QEvent(QEvent.Type.Leave)
        card.eventFilter(card.btn_delete, event_enter)
        card.eventFilter(card.btn_delete, event_leave)

        # Simulate leave event on card
        leave_event = QEvent(QEvent.Type.Leave)
        card.leaveEvent(leave_event)
        assert not card._action_bar_widget.isVisible()

        card.hide()
        card.deleteLater()


def test_loot_card_compact_mode_resting_and_hover_states(qapp):
    entry = {
        "id": "loot_compact",
        "type": "credentials",
        "category": "access",
        "title": "SSH Root Password For Testing",
        "content": "root:SuperSecret123!",
        "target_ip": "192.168.1.15",
        "timestamp": "14:30:00",
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Move cursor away so resting state doesn't trigger synthetic enter
        QCursor.setPos(QPoint(2000, 2000))

        card = LootCard(
            entry,
            project_dir=Path(tmp_dir),
            board_mode=True,
            density="compact",
        )
        card.move(100, 100)
        card.resize(260, 40)
        card.show()
        qapp.processEvents()

        assert card.density == "compact"
        assert card.property("cardDensity") == "compact"
        assert hasattr(card, "lbl_title")
        assert card.lbl_title.text() == entry["title"]
        assert hasattr(card, "lbl_grip")
        assert hasattr(card, "lbl_cat")
        assert hasattr(card, "btn_copy")
        assert card.btn_copy.isVisible()

        # In compact resting state: content is hidden, action bar is hidden
        assert not card.lbl_content.isVisible()
        assert not card.lbl_badge.isVisible()
        assert not card._action_bar_widget.isVisible()

        # Tooltip contains metadata
        assert "CREDENTIALS" in card.toolTip()
        assert "192.168.1.15" in card.toolTip()
        assert "root:SuperSecret123!" in card.toolTip()

        # On hover: action bar appears
        enter_event = QEnterEvent(
            QPointF(10.0, 10.0),
            QPointF(10.0, 10.0),
            QPointF(10.0, 10.0),
        )
        card.enterEvent(enter_event)
        assert card._action_bar_widget.isVisible()

        # Copy functionality works in compact mode
        card._copy_content()
        assert qapp.clipboard().text() == "root:SuperSecret123!"

        card.hide()
        card.deleteLater()


def test_loot_controller_density_toggle_and_board_propagation(qapp):
    from core.loot.manager import LootManager
    from core.project import ProjectManager
    from core.storage import FileStorageBackend

    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = FileStorageBackend(base_dir=Path(tmp_dir))
        loot_mgr = LootManager(storage=storage)
        proj_mgr = ProjectManager(base_dir=Path(tmp_dir), config_dir=Path(tmp_dir))
        ctrl = LootController(loot_mgr, proj_mgr)

        # Test build_filter_pills density toggle button
        container = QWidget()
        layout = QHBoxLayout(container)
        toggled = []

        ctrl.build_filter_pills(
            layout,
            on_select_type=lambda _: None,
            on_export=lambda: None,
            on_clear=lambda: None,
            export_tooltip="tip",
            on_toggle_view=lambda: None,
            view_mode="board",
            on_toggle_density=lambda: toggled.append(True),
            density="comfortable",
        )

        btn_density = container.findChild(QWidget, "LootDensityToggleButton")
        assert btn_density is not None
        assert btn_density.text() in ("Compact", "Kompakt")
        btn_density.click()
        assert len(toggled) == 1

        container.deleteLater()

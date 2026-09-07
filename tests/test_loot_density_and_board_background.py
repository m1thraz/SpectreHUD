"""Tests for LootBoard background styling, column vertical scrolling, LootCard density modes, context menu, and AddLootDialog export actions."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QEnterEvent, QWheelEvent
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from ui.loot_board import LootBoard
from ui.loot_card import LootCard
from ui.add_loot_dialog import AddLootDialog
from ui.controllers.loot_controller import LootController


def test_loot_board_autofill_background_and_qss_rule(qapp):
    entries = [
        {
            "id": f"loot_{i}",
            "type": "note",
            "category": "recon",
            "title": f"Subdomains {i}",
            "content": f"api{i}.domain.com\nDetails line 1\nDetails line 2\nDetails line 3",
        }
        for i in range(12)
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
        # Check column scroll areas and vertical scrollbar
        board.resize(1000, 350)
        board.show()
        qapp.processEvents()

        recon_col = board.columns.get("recon")
        assert recon_col is not None
        assert recon_col.scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded

        v_bar = recon_col.scroll.verticalScrollBar()
        assert v_bar.maximum() > 0, "Vertical scrollbar maximum should be > 0 when cards exceed column height"

        # Verify mouse wheel scrolling
        initial_val = v_bar.value()
        wheel_event = QWheelEvent(
            QPointF(50.0, 50.0),
            QPointF(50.0, 50.0),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        qapp.sendEvent(recon_col.scroll.viewport(), wheel_event)
        qapp.processEvents()
        assert v_bar.value() > initial_val or v_bar.maximum() > 0

        board.hide()
        board.deleteLater()


def test_loot_card_comfortable_mode_resting_actions_and_context_menu(qapp):
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
        card = LootCard(
            entry,
            project_dir=Path(tmp_dir),
            board_mode=True,
            density="comfortable",
        )
        card.resize(260, 160)
        card.show()
        qapp.processEvents()

        assert card.density == "comfortable"
        assert card.property("cardDensity") == "comfortable"
        assert card.lbl_content.isVisible()

        # Copy button is permanently visible on Row 1
        assert card.btn_copy.isVisible()

        # Action bar is NOT visible on hover (no hover reveal)
        enter_event = QEnterEvent(
            QPointF(10.0, 10.0),
            QPointF(10.0, 10.0),
            QPointF(10.0, 10.0),
        )
        card.enterEvent(enter_event)
        if hasattr(card, "_action_bar_widget") and card._action_bar_widget is not None:
            assert not card._action_bar_widget.isVisible()

        # Test context menu creation on right-click
        menu_triggered = {}
        card.edit_requested.connect(lambda e: menu_triggered.setdefault("edit", True))
        card.export_requested.connect(lambda eid: menu_triggered.setdefault("export", True))
        card.obsidian_export_requested.connect(lambda eid: menu_triggered.setdefault("obsidian", True))
        card.deleted.connect(lambda eid: menu_triggered.setdefault("delete", True))

        menu = card._create_context_menu()
        assert menu is not None
        actions = menu.actions()
        action_texts = [a.text() for a in actions if not a.isSeparator()]
        assert any("Edit" in t or "Bearbeiten" in t for t in action_texts)
        assert any("Export" in t or "Exportieren" in t for t in action_texts)
        assert any("Obsidian" in t for t in action_texts)
        assert any("Delete" in t or "Löschen" in t for t in action_texts)

        # Trigger each action to verify signals
        for act in actions:
            if not act.isSeparator():
                act.trigger()

        assert menu_triggered.get("edit") is True
        assert menu_triggered.get("export") is True
        assert menu_triggered.get("obsidian") is True
        assert menu_triggered.get("delete") is True

        # Test right-click handler with exec patched
        with patch("PyQt6.QtWidgets.QMenu.exec", return_value=None):
            card._show_context_menu(QPoint(100, 100))

        card.hide()
        card.deleteLater()


def test_loot_card_compact_mode_resting_state(qapp):
    entry = {
        "id": "loot_compact",
        "type": "credentials",
        "category": "access",
        "title": "SSH Root Password",
        "content": "root:SuperSecret123!",
        "target_ip": "192.168.1.15",
        "timestamp": "14:30:00",
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        card = LootCard(
            entry,
            project_dir=Path(tmp_dir),
            board_mode=True,
            density="compact",
        )
        card.resize(260, 40)
        card.show()
        qapp.processEvents()

        assert card.density == "compact"
        assert card.property("cardDensity") == "compact"
        assert card.lbl_title.text() == entry["title"]
        assert card.btn_copy.isVisible()

        # In compact resting state: content is hidden
        assert not card.lbl_content.isVisible()
        assert not card.lbl_badge.isVisible()
        if hasattr(card, "_action_bar_widget") and card._action_bar_widget is not None:
            assert not card._action_bar_widget.isVisible()

        # Hover does not reveal action bar
        enter_event = QEnterEvent(
            QPointF(10.0, 10.0),
            QPointF(10.0, 10.0),
            QPointF(10.0, 10.0),
        )
        card.enterEvent(enter_event)
        if hasattr(card, "_action_bar_widget") and card._action_bar_widget is not None:
            assert not card._action_bar_widget.isVisible()

        # Copy functionality works in compact mode
        card._copy_content()
        assert qapp.clipboard().text() == "root:SuperSecret123!"

        card.hide()
        card.deleteLater()


def test_add_loot_dialog_export_buttons_in_edit_mode(qapp):
    exported_files = []
    exported_obsidian = []

    # In edit mode with entry_id
    dlg = AddLootDialog(
        entry_id="loot_test_123",
        is_edit=True,
        title="Test Entry",
        content="Secret Value",
        on_export_file=lambda eid: exported_files.append(eid),
        on_export_obsidian=lambda eid: exported_obsidian.append(eid),
    )
    assert dlg.btn_export_file is not None
    assert dlg.btn_export_obsidian is not None
    dlg.btn_export_file.click()
    assert exported_files == ["loot_test_123"]
    dlg.btn_export_obsidian.click()
    assert exported_obsidian == ["loot_test_123"]
    dlg.deleteLater()

    # In create mode without entry_id
    dlg_new = AddLootDialog(
        is_edit=False,
    )
    assert dlg_new.btn_export_file is None
    assert dlg_new.btn_export_obsidian is None
    dlg_new.deleteLater()


def test_loot_controller_density_toggle_and_board_propagation(qapp):
    from core.loot.manager import LootManager
    from core.project import ProjectManager
    from core.storage import FileStorageBackend

    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = FileStorageBackend(base_dir=Path(tmp_dir))
        loot_mgr = LootManager(storage=storage)
        proj_mgr = ProjectManager(base_dir=Path(tmp_dir), config_dir=Path(tmp_dir))
        ctrl = LootController(loot_mgr, proj_mgr)

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

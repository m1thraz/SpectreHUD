"""Smoke tests for the Kanban loot board presentation."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QMimeData
from PyQt6.QtWidgets import QApplication, QAbstractScrollArea

from core.loot_manager import CATEGORIES
from ui.loot_board import LOOT_ENTRY_MIME_TYPE, LootBoard, LootBoardDropArea


app = QApplication.instance() or QApplication(sys.argv)


class _FakeDragEvent:
    def __init__(self, mime_data):
        self._mime_data = mime_data
        self.accepted = False

    def mimeData(self):
        return self._mime_data

    def acceptProposedAction(self):
        self.accepted = True

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.accepted = False


def test_board_creates_one_column_per_category_and_reuses_loot_cards():
    moves = []
    exported = []
    entries = [
        {"id": "loot_recon", "type": "note", "category": "recon", "title": "Nmap", "content": "nmap -sV"},
        {"id": "loot_scripts", "type": "note", "category": "scripts", "title": "PoC", "content": "python poc.py"},
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        board = LootBoard(
            entries=entries,
            project_dir=Path(tmp_dir),
            on_delete=lambda _entry_id: None,
            on_edit=lambda _entry: None,
            on_export=exported.append,
            on_move=lambda entry_id, category, target_index: moves.append(
                (entry_id, category, target_index)
            ) or True,
        )

        assert list(board.columns) == [category["id"] for category in CATEGORIES]
        assert board.columns["recon"].entry_ids == ["loot_recon"]
        assert board.columns["scripts"].entry_ids == ["loot_scripts"]
        assert board.columns["access"].entry_ids == []

        card = board.columns["scripts"].cards_layout.itemAt(0).widget()
        card.btn_export_file.click()
        assert exported == ["loot_scripts"]

        assert board.columns["access"].on_entry_dropped("loot_recon", "access", 0)
        assert moves == [("loot_recon", "access", 0)]
        board.deleteLater()


def test_board_renders_entries_by_persistent_position():
    entries = [
        {"id": "third", "category": "recon", "position": 2, "title": "Third", "content": "3"},
        {"id": "first", "category": "recon", "position": 0, "title": "First", "content": "1"},
        {"id": "second", "category": "recon", "position": 1, "title": "Second", "content": "2"},
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        board = LootBoard(
            entries=entries,
            project_dir=Path(tmp_dir),
            on_delete=lambda _entry_id: None,
            on_edit=lambda _entry: None,
            on_export=lambda _entry_id: None,
            on_move=lambda _entry_id, _category, _target_index: True,
        )

        assert board.columns["recon"].entry_ids == ["first", "second", "third"]
        board.deleteLater()


def test_drop_area_resets_drag_highlight_after_leave_and_drop():
    dropped = []
    area = LootBoardDropArea(
        CATEGORIES[0],
        lambda entry_id, category, target_index: dropped.append(
            (entry_id, category, target_index)
        ) or True,
    )
    mime_data = QMimeData()
    mime_data.setData(LOOT_ENTRY_MIME_TYPE, b"loot_recon")
    event = _FakeDragEvent(mime_data)

    area.dragEnterEvent(event)
    assert event.accepted
    assert area.property("dragActive") is True

    area.dragLeaveEvent(event)
    assert area.property("dragActive") is False

    area.dragEnterEvent(event)
    area._handle_drop(event, 0)
    assert event.accepted
    assert dropped == [("loot_recon", "recon", 0)]
    assert area.property("dragActive") is False
    area.deleteLater()


def test_kanban_cards_use_bounded_elided_previews_without_inner_scrollbars():
    edited = []
    contents = [
        "\n".join(f"multiline finding {index}" for index in range(30)),
        "A" * 1200,
        ("large loot entry with several words " * 500).strip(),
    ]
    entries = [
        {
            "id": f"long-{index}",
            "type": "note",
            "category": "recon",
            "title": f"Long entry {index}",
            "content": content,
        }
        for index, content in enumerate(contents)
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        board = LootBoard(
            entries=entries,
            project_dir=Path(tmp_dir),
            on_delete=lambda _entry_id: None,
            on_edit=edited.append,
            on_export=lambda _entry_id: None,
            on_move=lambda _entry_id, _category, _target_index: True,
        )
        board.resize(1400, 650)
        board.show()
        for _ in range(3):
            app.processEvents()

        recon_column = board.columns["recon"]
        cards = [
            recon_column.cards_layout.itemAt(index).widget()
            for index in range(recon_column.cards_layout.count())
        ]
        assert len(cards) == 3

        for card, full_content in zip(cards, contents):
            assert card.findChildren(QAbstractScrollArea) == []
            assert card.lbl_content.text() != full_content
            assert card.lbl_content.text().endswith("…")
            expected_maximum = card.lbl_content.fontMetrics().lineSpacing() * 5
            margins = card.lbl_content.contentsMargins()
            expected_maximum += margins.top() + margins.bottom()
            assert card.lbl_content.maximumHeight() == expected_maximum
            assert card.height() < 500

        cards[0].btn_edit.click()
        assert edited == [entries[0]]
        assert edited[0]["content"] == contents[0]
        board.hide()
        board.deleteLater()

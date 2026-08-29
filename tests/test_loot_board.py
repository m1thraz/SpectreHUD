"""Smoke tests for the Kanban loot board presentation."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from core.loot_manager import CATEGORIES
from ui.loot_board import LootBoard


app = QApplication.instance() or QApplication(sys.argv)


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
            on_move=lambda entry_id, category: moves.append((entry_id, category)) or True,
        )

        assert list(board.columns) == [category["id"] for category in CATEGORIES]
        assert board.columns["recon"].entry_ids == ["loot_recon"]
        assert board.columns["scripts"].entry_ids == ["loot_scripts"]
        assert board.columns["access"].entry_ids == []

        card = board.columns["scripts"].cards_layout.itemAt(0).widget()
        card.btn_export_file.click()
        assert exported == ["loot_scripts"]

        assert board.columns["access"].on_entry_dropped("loot_recon", "access")
        assert moves == [("loot_recon", "access")]
        board.deleteLater()

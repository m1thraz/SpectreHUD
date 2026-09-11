"""Verify real card geometry and rendered contrast under the nested scroll styles."""

import pytest
from PyQt6.QtGui import QColor

from core.theme_loader import ThemeLoader
from ui.loot_board import LootBoard
from ui.panels.content_panel import ContentPanel
from ui.styles import build_app_theme


@pytest.mark.parametrize("theme", [p.stem for p in ThemeLoader.BUILTIN_THEMES_DIR.glob("*.json")])
def test_kanban_cards_keep_badges_values_and_surface_contrast(qapp, tmp_path, theme):
    values = ["/home/test/Desktop/SpectreHUD-main.rar", "ab12" * 64 + "\nuser:secret"]
    entries = [
        {
            "id": str(i),
            "type": kind,
            "category": "recon",
            "title": "Evidence",
            "content": value,
            "target_ip": "192.168.56.1",
            "timestamp": "2026-09-05 12:00",
        }
        for i, (kind, value) in enumerate(zip(("directory", "note"), values))
    ]
    panel = ContentPanel()
    panel.setStyleSheet(build_app_theme(ThemeLoader().load_theme(theme)))
    board = LootBoard(
        entries, tmp_path, lambda _: None, lambda _: None, lambda _: None, lambda *_: True
    )
    panel.content_layout.addWidget(board)
    panel.resize(740, 700)
    panel.show()
    try:
        for width in (740, 1200, 740):
            panel.resize(width, 700)
            for _ in range(5):
                qapp.processEvents()
            column = board.columns["recon"]
            for index, value in enumerate(values):
                card = column.cards_layout.itemAt(index).widget()
                badge = card.lbl_badge
                assert badge.text() == ("DIRECTORIES", "NOTES")[index]
                assert badge.width() >= badge.fontMetrics().horizontalAdvance(badge.text()) + 14
                assert badge.geometry().right() < card.width()
                assert card.width() <= column.width()
                assert card.lbl_content.text() == value
                assert card.lbl_content.verticalScrollBar().maximum() == 0
                assert card.lbl_content.horizontalScrollBar().maximum() == 0
                block = card.lbl_content.document().begin()
                while block.isValid():
                    text_layout = block.layout()
                    # Every character belongs to a rendered line inside the viewport.
                    assert sum(
                        text_layout.lineAt(n).textLength() for n in range(text_layout.lineCount())
                    ) == len(block.text())
                    assert all(
                        text_layout.lineAt(n).naturalTextWidth()
                        <= card.lbl_content.viewport().width()
                        for n in range(text_layout.lineCount())
                    )
                    block = block.next()
                assert card.lbl_content.height() >= card.lbl_content.heightForWidth(
                    card.lbl_content.width()
                )
                image = card.grab().toImage()
                card_color = image.pixelColor(image.width() // 2, 5)
                column_color = QColor(ThemeLoader().load_theme(theme)["BG_DARK"])
                assert abs(card_color.lightnessF() - column_color.lightnessF()) >= 0.13
            assert (
                column.cards_layout.itemAt(1).widget().height()
                > column.cards_layout.itemAt(0).widget().height()
            )
    finally:
        panel.close()
        panel.deleteLater()

"""Regression tests ensuring badges ('TARGET', etc.) never truncate while titles elide gracefully."""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from ui.loot_card import LootCard
from ui.quick_note_card import QuickNoteCard
from ui.history_card import HistoryCard
from ui.elided_label import ElidedLabel


def test_loot_card_reserves_badge_width_and_elides_title(qapp, tmp_path):
    entry = {
        "id": "loot-truncation-test",
        "type": "credentials",
        "category": "access",
        "title": "A Very Long Exploit Payload With Custom Arguments For Squeezed Row",
        "target_ip": "TARGET",
        "timestamp": "2026-09-05 14:00:00",
        "content": "admin:SuperSecret123",
    }

    container = QWidget()
    layout = QVBoxLayout(container)
    card = LootCard(entry, project_dir=tmp_path, parent=container)
    layout.addWidget(card)

    container.resize(240, 200)
    container.show()
    for _ in range(3):
        qapp.processEvents()

    labels = card.findChildren(QLabel)
    target_label = next((lbl for lbl in labels if lbl.text() == "TARGET"), None)
    assert target_label is not None, "Target badge label 'TARGET' must exist"

    advance = target_label.fontMetrics().horizontalAdvance("TARGET")
    assert target_label.minimumWidth() >= advance + 8
    assert target_label.width() >= advance + 8

    assert isinstance(card.lbl_title, ElidedLabel)
    assert "…" in card.lbl_title.elided_text()
    assert card.lbl_title.text() == entry["title"]

    container.hide()
    container.deleteLater()


def test_quick_note_card_reserves_target_badge_width(qapp):
    entry = {
        "id": "note-truncation-test",
        "content": "Check internal staging credentials",
        "category": "access",
        "target_ip": "TARGET",
        "timestamp": "14:05:00",
    }

    container = QWidget()
    layout = QVBoxLayout(container)
    card = QuickNoteCard(entry, parent=container)
    layout.addWidget(card)

    container.resize(250, 150)
    container.show()
    for _ in range(3):
        qapp.processEvents()

    labels = card.findChildren(QLabel)
    target_label = next((lbl for lbl in labels if lbl.text() == "TARGET"), None)
    assert target_label is not None
    advance = target_label.fontMetrics().horizontalAdvance("TARGET")
    assert target_label.minimumWidth() >= advance + 14
    assert target_label.width() >= advance

    container.hide()
    container.deleteLater()


def test_history_card_reserves_target_badge_width(qapp):
    entry = {
        "id": "hist-truncation-test",
        "text": "curl -s http://TARGET/api/keys",
        "target_ip": "TARGET",
        "timestamp": "14:10:00",
        "lines_count": 1,
        "char_count": 30,
    }

    container = QWidget()
    layout = QVBoxLayout(container)
    card = HistoryCard(entry, parent=container)
    layout.addWidget(card)

    container.resize(250, 150)
    container.show()
    for _ in range(3):
        qapp.processEvents()

    labels = card.findChildren(QLabel)
    target_label = next((lbl for lbl in labels if lbl.text() == "TARGET"), None)
    assert target_label is not None
    advance = target_label.fontMetrics().horizontalAdvance("TARGET")
    assert target_label.minimumWidth() >= advance + 14
    assert target_label.width() >= advance

    container.hide()
    container.deleteLater()


def test_cards_render_standardized_phase_badges(qapp, tmp_path):
    loot_entry = {
        "id": "loot-phase-test",
        "type": "credentials",
        "category": "initial",  # alias for access
        "title": "Shell access",
        "timestamp": "2026-09-05 14:00:00",
        "content": "test",
    }
    loot_card = LootCard(loot_entry, project_dir=tmp_path)
    labels = loot_card.findChildren(QLabel)
    cat_lbl = next((lbl for lbl in labels if lbl.property("class") == "CategoryBadge"), None)
    assert cat_lbl is not None
    assert cat_lbl.text() == "ACCESS"
    assert "Initial Access & Exploitation" in cat_lbl.toolTip()

    note_entry = {
        "id": "note-phase-test",
        "text": "Note text",
        "category": "lateral",  # alias for postex
        "timestamp": "14:05:00",
    }
    note_card = QuickNoteCard(note_entry)
    note_labels = note_card.findChildren(QLabel)
    note_cat_lbl = next((lbl for lbl in note_labels if lbl.text() == "POSTEX"), None)
    assert note_cat_lbl is not None
    assert note_cat_lbl.toolTip() == "Post-Exploitation & Lateral Movement"


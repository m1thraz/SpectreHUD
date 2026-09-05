"""Kanban board presentation for categorized loot entries."""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, QMimeData, QEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.loot.manager import CATEGORIES
from ui.loot_card import LootCard


LOOT_ENTRY_MIME_TYPE = "application/x-spectrehud-loot-entry"


class LootBoardDropArea(QFrame):
    """One category column that accepts a dragged LootCard entry ID."""

    def __init__(
        self,
        category: Dict[str, Any],
        on_entry_dropped: Callable[[str, str, int], bool],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.category = category
        self.on_entry_dropped = on_entry_dropped
        self.entry_ids: List[str] = []
        self.setAcceptDrops(True)
        self.setProperty("class", "LootBoardColumn")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel(f"{category.get('icon', '')} {category['name']}")
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(True)
        title.setProperty("class", "LootBoardColumnTitle")
        layout.addWidget(title)

        self.cards_container = QWidget(self)
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(6)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cards_container.setAcceptDrops(True)
        self.cards_container.installEventFilter(self)

        scroll = QScrollArea(self)
        scroll.setObjectName("LootColumnScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.viewport().setStyleSheet("background: transparent; border: none;")
        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll, stretch=1)

    def add_card(self, card: LootCard) -> None:
        self.entry_ids.append(str(card.entry.get("id", "")))
        self.cards_layout.addWidget(card)

    def _set_drag_active(self, active: bool) -> None:
        if self.property("dragActive") == active:
            return
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _target_index_for_y(self, position_y: int, entry_id: str = "") -> int:
        target_index = self.cards_layout.count()
        for index in range(self.cards_layout.count()):
            card = self.cards_layout.itemAt(index).widget()
            if card is not None and position_y < card.geometry().center().y():
                target_index = index
                break

        if entry_id in self.entry_ids:
            source_index = self.entry_ids.index(entry_id)
            if source_index < target_index:
                target_index -= 1
        return max(0, target_index)

    def _handle_drop(self, event, position_y: int) -> None:
        try:
            mime_data: QMimeData = event.mimeData()
            if not mime_data.hasFormat(LOOT_ENTRY_MIME_TYPE):
                event.ignore()
                return
            try:
                entry_id = bytes(mime_data.data(LOOT_ENTRY_MIME_TYPE)).decode(
                    "utf-8", errors="strict"
                )
            except UnicodeDecodeError:
                event.ignore()
                return
            target_index = self._target_index_for_y(position_y, entry_id)
            if entry_id and self.on_entry_dropped(entry_id, self.category["id"], target_index):
                event.acceptProposedAction()
            else:
                event.ignore()
        finally:
            self._set_drag_active(False)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(LOOT_ENTRY_MIME_TYPE):
            self._set_drag_active(True)
            event.acceptProposedAction()
        else:
            self._set_drag_active(False)
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        self.dragEnterEvent(event)

    def dragLeaveEvent(self, event) -> None:
        self._set_drag_active(False)
        event.accept()

    def dropEvent(self, event) -> None:
        cards_position = self.cards_container.mapFrom(self, event.position().toPoint())
        self._handle_drop(event, cards_position.y())

    def eventFilter(self, watched, event) -> bool:
        if watched is self.cards_container and event.type() in (
            QEvent.Type.DragEnter,
            QEvent.Type.DragMove,
            QEvent.Type.DragLeave,
            QEvent.Type.Drop,
        ):
            # The visible empty area belongs to the cards container, so forward
            # drops to the column's canonical handler.
            if event.type() == QEvent.Type.Drop:
                self._handle_drop(event, event.position().toPoint().y())
            elif event.type() == QEvent.Type.DragLeave:
                self.dragLeaveEvent(event)
            else:
                self.dragEnterEvent(event)
            return event.isAccepted()
        return super().eventFilter(watched, event)


class LootBoard(QScrollArea):
    """Horizontally scrollable board composed of one column per loot category."""

    def __init__(
        self,
        entries: List[Dict[str, Any]],
        project_dir: Path,
        on_delete: Callable[[str], None],
        on_edit: Callable[[Dict[str, Any]], None],
        on_export: Callable[[str], None],
        on_move: Callable[[str, str, int], bool],
        on_export_obsidian: Optional[Callable[[str], None]] = None,
        on_copied: Optional[Callable[[str], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.columns: Dict[str, LootBoardDropArea] = {}
        self.setWidgetResizable(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(430)
        self.setProperty("class", "LootBoard")

        board_content = QWidget(self)
        layout = QHBoxLayout(board_content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        entries_by_category = {
            category["id"]: sorted(
                (entry for entry in entries if entry.get("category") == category["id"]),
                key=lambda entry: entry.get("position", 0),
            )
            for category in CATEGORIES
        }
        for category in CATEGORIES:
            column = LootBoardDropArea(category, on_move, board_content)
            column.setFixedWidth(270)
            for entry in entries_by_category[category["id"]]:
                card = LootCard(
                    entry,
                    project_dir,
                    parent=column.cards_container,
                    preview_line_limit=5,
                )
                card.loot_deleted.connect(on_delete)
                card.edit_requested.connect(on_edit)
                card.export_requested.connect(on_export)
                if on_export_obsidian is not None:
                    card.obsidian_export_requested.connect(on_export_obsidian)
                if on_copied is not None:
                    card.copied.connect(on_copied)
                column.add_card(card)
            self.columns[category["id"]] = column
            layout.addWidget(column)

        layout.addStretch()
        board_content.setMinimumWidth(len(CATEGORIES) * 280)
        self.setWidget(board_content)

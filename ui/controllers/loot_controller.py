from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox

from core.loot_manager import LootManager, LOOT_TYPES, CATEGORIES
from core.project_manager import ProjectManager
from ui.loot_card import LootCard
from ui.add_loot_dialog import AddLootDialog
from ui.styles import CYBER_DARK_QSS


class LootController(QObject):
    """Controller managing loot entries, category grouping, filter pills, and add/edit/delete dialogs."""

    loot_type_changed = pyqtSignal(str)
    loot_updated = pyqtSignal()

    def __init__(
        self, 
        loot_manager: LootManager, 
        project_manager: ProjectManager, 
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.loot_manager = loot_manager
        self.project_manager = project_manager
        self.current_loot_type: str = "all"
        self.filter_buttons: Dict[str, QPushButton] = {}

    def select_loot_type(self, type_id: str) -> None:
        self.current_loot_type = type_id
        for tid, btn in self.filter_buttons.items():
            btn.setProperty("class", "FilterPillActive" if tid == type_id else "FilterPill")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.loot_type_changed.emit(type_id)

    def build_filter_pills(
        self,
        pills_layout: QHBoxLayout,
        on_select_type: Callable[[str], None],
        on_export: Callable[[], None],
        on_clear: Callable[[], None],
        export_tooltip: str
    ) -> None:
        self.filter_buttons.clear()
        counts = self.loot_manager.get_type_counts(target_ip=None)
        all_btn = QPushButton(f"All ({counts.get('all', 0)})")
        all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        all_btn.setProperty("class", "FilterPillActive" if self.current_loot_type == "all" else "FilterPill")
        all_btn.clicked.connect(lambda: on_select_type("all"))
        self.filter_buttons["all"] = all_btn
        pills_layout.addWidget(all_btn)

        for t in LOOT_TYPES:
            tid = t["id"]
            count = counts.get(tid, 0)
            btn = QPushButton(f"{t['name']} ({count})")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("class", "FilterPillActive" if self.current_loot_type == tid else "FilterPill")
            btn.clicked.connect(lambda checked=False, type_id=tid: on_select_type(type_id))
            self.filter_buttons[tid] = btn
            pills_layout.addWidget(btn)

        pills_layout.addStretch()

        # Contextual Loot Action Buttons
        btn_export = QPushButton("Export (.md)")
        btn_export.setProperty("class", "MiniActionBtn")
        btn_export.setToolTip(export_tooltip)
        btn_export.clicked.connect(on_export)
        pills_layout.addWidget(btn_export)

        btn_clear = QPushButton("Clear")
        btn_clear.setProperty("class", "MiniDangerBtn")
        btn_clear.setToolTip("Session-Loot dieses Projekts leeren")
        btn_clear.clicked.connect(on_clear)
        pills_layout.addWidget(btn_clear)

    def render_content(
        self,
        content_layout: QVBoxLayout,
        search_query: str,
        proj_dir: Path,
        on_delete_loot: Callable[[str], None],
        on_edit_loot: Callable[[Dict[str, Any]], None],
        parent_widget: QWidget,
        show_empty_state_fn: Callable[[str], None]
    ) -> List[QWidget]:
        loot_entries = self.loot_manager.get_entries(
            target_ip=None,
            entry_type=self.current_loot_type,
            search_query=search_query
        )

        if not loot_entries:
            show_empty_state_fn("Kein Session-Loot vorhanden. Drücke Ctrl+N um Notizen/Creds anzulegen oder Snip für Screenshots.")
            return []

        rendered_cards: List[QWidget] = []

        # Group entries by category preserving sort order within category
        entries_by_cat: Dict[str, List[Dict[str, Any]]] = {}
        for entry in loot_entries:
            cat_id = entry.get("category") or "misc"
            entries_by_cat.setdefault(cat_id, []).append(entry)

        # Render in CATEGORIES order (skipping empty categories)
        for cat_def in sorted(CATEGORIES, key=lambda c: c.get("order", 99)):
            cat_id = cat_def["id"]
            cat_entries = entries_by_cat.pop(cat_id, None)
            if not cat_entries:
                continue

            header = QLabel(f"{cat_def.get('icon', '')} {cat_def.get('name', '')}".strip())
            header.setProperty("class", "LootSectionHeader")
            content_layout.addWidget(header)

            for entry in cat_entries:
                card = LootCard(entry, project_dir=proj_dir, parent=parent_widget)
                card.loot_deleted.connect(on_delete_loot)
                card.edit_requested.connect(on_edit_loot)
                content_layout.addWidget(card)
                rendered_cards.append(card)

        # Any remaining entries with unknown categories
        for cat_id, cat_entries in entries_by_cat.items():
            if not cat_entries:
                continue
            header = QLabel(f"{cat_id.capitalize()}")
            header.setProperty("class", "LootSectionHeader")
            content_layout.addWidget(header)

            for entry in cat_entries:
                card = LootCard(entry, project_dir=proj_dir, parent=parent_widget)
                card.loot_deleted.connect(on_delete_loot)
                card.edit_requested.connect(on_edit_loot)
                content_layout.addWidget(card)
                rendered_cards.append(card)

        return rendered_cards

    def open_add_dialog(
        self,
        parent_widget: QWidget,
        target_ip: str = "",
        default_type: str = "credentials",
        default_category: str = "misc",
        default_title: str = "",
        default_content: str = ""
    ) -> bool:
        dlg = AddLootDialog(
            target_ip=target_ip,
            default_type=default_type,
            default_category=default_category,
            default_title=default_title,
            default_content=default_content,
            parent=parent_widget
        )
        if dlg.exec():
            data = dlg.get_data()
            self.loot_manager.add_entry(
                entry_type=data["type"],
                category=data.get("category", "misc"),
                title=data["title"],
                content=data["content"],
                target_ip=data["target_ip"]
            )
            self.loot_updated.emit()
            return True
        return False

    def open_edit_dialog(self, parent_widget: QWidget, entry: Dict[str, Any]) -> bool:
        dlg = AddLootDialog(
            parent=parent_widget,
            entry_id=entry.get("id"),
            is_edit=True,
            initial_type=entry.get("type", "note"),
            initial_category=entry.get("category", "misc"),
            initial_title=entry.get("title", ""),
            initial_content=entry.get("content", ""),
            current_target_ip=entry.get("target_ip", "")
        )
        if dlg.exec():
            data = dlg.get_data()
            self.loot_manager.update_entry(
                entry_id=data.get("id") or entry.get("id", ""),
                type=data.get("type"),
                category=data.get("category"),
                title=data.get("title"),
                content=data.get("content"),
                target_ip=data.get("target_ip")
            )
            self.loot_updated.emit()
            return True
        return False

    def delete_loot(self, loot_id: str) -> None:
        self.loot_manager.delete_entry(loot_id)
        self.loot_updated.emit()

    def clear_loot(self, parent_widget: QWidget) -> bool:
        msg = QMessageBox(parent_widget)
        msg.setWindowTitle("Session leeren")
        msg.setText("Möchtest du wirklich alle Loot-Einträge dieses Projekts löschen?")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.setStyleSheet(CYBER_DARK_QSS)

        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.loot_manager.clear_session()
            self.loot_updated.emit()
            return True
        return False

from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox

from core.loot_manager import LootManager, LOOT_TYPES, CATEGORIES
from core.project_manager import ProjectManager
from core.storage import PersistenceError, StorageError
from core.logger import get_logger
from core.menu_actions import MenuAction
from core.event_bus import EventBus
from core.i18n import t
from ui.loot_card import LootCard
from ui.add_loot_dialog import AddLootDialog
from ui.styles import CYBER_DARK_QSS

logger = get_logger("loot_controller")


class LootController(QObject):
    """UI-independent controller managing loot entries, category grouping, filter pills, and domain actions."""

    loot_type_changed = pyqtSignal(str)
    loot_updated = pyqtSignal()

    def __init__(
        self, 
        loot_manager: LootManager, 
        project_manager: ProjectManager, 
        event_bus: Optional[EventBus] = None,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.loot_manager = loot_manager
        self.project_manager = project_manager
        self.event_bus = event_bus if event_bus is not None else EventBus()
        self.current_loot_type: str = "all"
        self.filter_buttons: Dict[str, QPushButton] = {}

    def _notify_persistence_error(self, operation: str, error: Exception, parent_widget: Optional[QWidget] = None) -> None:
        logger.error(f"Persistence error during {operation}: {error}")
        target_widget = parent_widget
        if target_widget is None:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                target_widget = app.activeWindow()
        QMessageBox.critical(
            target_widget,
            "Speicherfehler",
            f"Loot-Änderung konnte nicht auf die Festplatte geschrieben werden:\n{error}\n\nDie laufenden Sitzungsdaten im Speicher bleiben geschützt."
        )

    # ------------------------------------------------------------------ #
    # Pure Domain Methods (UI-Independent)
    # ------------------------------------------------------------------ #

    def get_entries(
        self,
        target_ip: Optional[str] = None,
        entry_type: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        target_type = entry_type if entry_type is not None else self.current_loot_type
        return self.loot_manager.get_entries(
            target_ip=target_ip,
            entry_type=target_type,
            search_query=search_query
        )

    def get_type_counts(self, target_ip: Optional[str] = None) -> Dict[str, int]:
        return self.loot_manager.get_type_counts(target_ip=target_ip)

    def add_entry(
        self,
        entry_type: str,
        title: str,
        content: str,
        target_ip: str = "",
        category: str = "misc",
        severity: str = "info",
    ) -> Dict[str, Any]:
        try:
            entry = self.loot_manager.add_entry(
                entry_type=entry_type,
                title=title,
                content=content,
                target_ip=target_ip,
                category=category,
                severity=severity,
            )
            self.loot_updated.emit()
            return entry
        except (PersistenceError, StorageError, OSError) as e:
            self._notify_persistence_error("add_entry", e)
            return {}

    def update_entry(
        self,
        entry_id: str,
        title: str,
        content: str,
        target_ip: str = "",
        category: str = "misc",
        entry_type: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> bool:
        try:
            fields: Dict[str, Any] = {
                "entry_id": entry_id,
                "title": title,
                "content": content,
                "target_ip": target_ip,
                "category": category,
            }
            if entry_type is not None:
                fields["type"] = entry_type
            if severity is not None:
                fields["severity"] = severity
            success = self.loot_manager.update_entry(**fields)
            if success:
                self.loot_updated.emit()
            return success
        except (PersistenceError, StorageError, OSError) as e:
            self._notify_persistence_error("update_entry", e)
            return False

    def delete_entry(self, entry_id: str) -> bool:
        try:
            success = self.loot_manager.delete_entry(entry_id)
            if success:
                self.loot_updated.emit()
            return success
        except (PersistenceError, StorageError, OSError) as e:
            self._notify_persistence_error("delete_entry", e)
            return False

    delete_loot = delete_entry

    def clear_entries(self, target_ip: Optional[str] = None) -> None:
        try:
            self.loot_manager.clear_session(target_ip=target_ip)
            self.loot_updated.emit()
        except (PersistenceError, StorageError, OSError) as e:
            self._notify_persistence_error("clear_entries", e)

    def clear_loot(self, parent_widget: Optional[QWidget] = None) -> bool:
        if parent_widget:
            reply = QMessageBox.question(
                parent_widget,
                t("loot.clear_title", "Clear Loot"),
                t("loot.clear_confirm", "Are you sure you want to delete all session loot for this project?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
        self.clear_entries()
        return True

    def export_loot(self, output_path: Path, target_ip: Optional[str] = None) -> str:
        return self.loot_manager.export_loot(output_path, target_ip=target_ip)

    def get_type_filter_actions(
        self,
        on_select_type: Optional[Callable[[str], None]] = None
    ) -> List[MenuAction]:
        """Returns a list of MenuAction DTOs for filtering loot by type."""
        counts = self.get_type_counts(target_ip=None)
        actions: List[MenuAction] = [
            MenuAction(
                id="type:all",
                text=f"All ({counts.get('all', 0)})",
                checked=(self.current_loot_type == "all"),
                callback=lambda: on_select_type("all") if on_select_type else self.select_loot_type("all"),
                data={"type": "all"}
            )
        ]
        for t in LOOT_TYPES:
            tid = t["id"]
            count = counts.get(tid, 0)
            actions.append(MenuAction(
                id=f"type:{tid}",
                text=f"{t['name']} ({count})",
                checked=(self.current_loot_type == tid),
                callback=lambda target_id=tid: on_select_type(target_id) if on_select_type else self.select_loot_type(target_id),
                data={"type": tid}
            ))
        return actions

    # ------------------------------------------------------------------ #
    # UI Adapters (Pills & Rendering)
    # ------------------------------------------------------------------ #

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
        loot_entries = self.get_entries(
            target_ip=None,
            entry_type=self.current_loot_type,
            search_query=search_query
        )

        if not loot_entries:
            show_empty_state_fn(
                t(
                    "loot.empty_state",
                    "No session loot captured yet. Press Ctrl+N to add notes/credentials or Snip for screenshots."
                )
            )
            return []

        rendered_cards: List[QWidget] = []
        for category in sorted(CATEGORIES, key=lambda c: c["order"]):
            cat_entries = [e for e in loot_entries if e.get("category") == category["id"]]
            if not cat_entries:
                continue

            sec_header = QLabel(f"{category['icon']} {category['name']} ({len(cat_entries)})")
            sec_header.setProperty("class", "LootSectionHeader")
            content_layout.addWidget(sec_header)
            rendered_cards.append(sec_header)

            for entry in cat_entries:
                card = LootCard(entry, proj_dir, parent=parent_widget)
                card.loot_deleted.connect(on_delete_loot)
                card.edit_requested.connect(on_edit_loot)
                content_layout.addWidget(card)
                rendered_cards.append(card)

        return rendered_cards

    def open_add_dialog(
        self,
        parent_widget: QWidget,
        target_ip: str = "",
        default_target: str = "",
        default_type: str = "note",
        default_category: str = "misc",
        default_title: str = "",
        default_content: str = "",
        default_severity: str = "info",
    ) -> bool:
        """Open the loot dialog with optional values prefilled by its caller."""
        dlg = AddLootDialog(
            parent=parent_widget,
            target_ip=target_ip or default_target,
            default_type=default_type,
            default_category=default_category,
            default_title=default_title,
            default_content=default_content,
            default_severity=default_severity,
        )
        if dlg.exec():
            data = dlg.get_data()
            self.add_entry(
                entry_type=data["type"],
                title=data["title"],
                content=data["content"],
                target_ip=data["target_ip"],
                category=data.get("category", "misc"),
                severity=data.get("severity", "info"),
            )
            return True
        return False

    def open_edit_dialog(self, parent_widget: QWidget, entry: Dict[str, Any]) -> bool:
        dlg = AddLootDialog(
            parent=parent_widget,
            entry_id=entry.get("id"),
            is_edit=True,
            target_ip=entry.get("target_ip", ""),
            default_type=entry.get("type", "note"),
            default_category=entry.get("category", "misc"),
            default_title=entry.get("title", ""),
            default_content=entry.get("content", ""),
            default_severity=entry.get("severity", "info"),
        )
        if dlg.exec():
            data = dlg.get_data()
            self.update_entry(
                entry_id=entry["id"],
                title=data["title"],
                content=data["content"],
                target_ip=data["target_ip"],
                category=data.get("category", "misc"),
                entry_type=data.get("type"),
                severity=data.get("severity"),
            )
            return True
        return False

import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from PyQt6.QtCore import QObject, Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QCursor, QGuiApplication
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox

from core.loot_manager import LootManager, LootValidationError, LOOT_TYPES, CATEGORIES
from core.project import ProjectManager
from core.storage import PersistenceError, StorageError
from core.atomic_write import atomic_write_text
from core.project.validator import sanitize_filename_component, validate_workspace_boundary
from core.logger import get_logger
from core.menu_actions import MenuAction
from core.event_bus import EventBus
from core.i18n import t
from ui.loot_card import LootCard
from ui.loot_board import LootBoard
from ui.add_loot_dialog import AddLootDialog

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
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.loot_manager = loot_manager
        self.project_manager = project_manager
        self.event_bus = event_bus if event_bus is not None else EventBus()
        self.current_loot_type: str = "all"
        self.filter_buttons: Dict[str, QPushButton] = {}
        self._active_add_dialog: Optional[AddLootDialog] = None

    def _notify_persistence_error(
        self, operation: str, error: Exception, parent_widget: Optional[QWidget] = None
    ) -> None:
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
            f"Loot-Änderung konnte nicht auf die Festplatte geschrieben werden:\n{error}\n\nDie laufenden Sitzungsdaten im Speicher bleiben geschützt.",
        )

    # ------------------------------------------------------------------ #
    # Pure Domain Methods (UI-Independent)
    # ------------------------------------------------------------------ #

    def get_entries(
        self,
        target_ip: Optional[str] = None,
        entry_type: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        target_type = entry_type if entry_type is not None else self.current_loot_type
        return self.loot_manager.get_entries(
            target_ip=target_ip, entry_type=target_type, search_query=search_query
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
        except (PersistenceError, StorageError, LootValidationError, OSError) as e:
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
        except (PersistenceError, StorageError, LootValidationError, OSError) as e:
            self._notify_persistence_error("update_entry", e)
            return False

    def move_entry_to_category(
        self,
        entry_id: str,
        category: str,
        target_index: int = 0,
        parent_widget: Optional[QWidget] = None,
    ) -> bool:
        """Moves one entry to a Kanban column/index and persists the new order."""
        if category not in {item["id"] for item in CATEGORIES}:
            return False
        try:
            updated = self.loot_manager.reorder_entry(entry_id, category, target_index)
            if updated is None:
                return False
            self.loot_updated.emit()
            return True
        except (PersistenceError, StorageError, LootValidationError, OSError) as exc:
            self._notify_persistence_error("move_entry_to_category", exc, parent_widget)
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
                t(
                    "loot.clear_confirm",
                    "Are you sure you want to delete all session loot for this project?",
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
        self.clear_entries()
        return True

    def export_loot(self, output_path: Path, target_ip: Optional[str] = None) -> str:
        from core.report_builder import ReportBuilder

        builder = ReportBuilder(loot_manager=self.loot_manager)
        return builder.export(output_path, target_ip=target_ip)

    def export_entry_to_file(self, entry_id: str) -> Path:
        """Writes one loot entry as a human-readable, project-local text file."""
        entry = next(
            (item for item in self.loot_manager.get_all_entries() if item.get("id") == entry_id),
            None,
        )
        if entry is None:
            raise ValueError(f"Loot entry '{entry_id}' does not exist.")

        category = entry.get("category", "misc")
        if category not in {item["id"] for item in CATEGORIES}:
            category = "misc"

        project_dir = self.project_manager.get_project_dir(
            self.project_manager.get_active_project()
        )
        category_dir = validate_workspace_boundary(project_dir / category, project_dir)
        if category_dir.exists() and category_dir.is_symlink():
            raise PersistenceError(
                f"Refusing to export through symlinked category directory: {category}"
            )
        category_dir.mkdir(parents=True, exist_ok=True)
        category_dir = validate_workspace_boundary(category_dir, project_dir)
        if category_dir.is_symlink() or not category_dir.is_dir():
            raise PersistenceError(f"Invalid project category directory: {category}")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        clean_title = sanitize_filename_component(str(entry.get("title", "loot")), fallback="loot")
        target = category_dir / f"{timestamp}_{clean_title}.txt"
        suffix = 1
        while target.exists():
            target = category_dir / f"{timestamp}_{clean_title}_{suffix:02d}.txt"
            suffix += 1
        target = validate_workspace_boundary(target, project_dir)

        contents = "\n".join(
            [
                f"Title: {entry.get('title', '')}",
                f"Type: {entry.get('type', 'note')}",
                f"Category: {category}",
                f"Target: {entry.get('target_ip', '')}",
                f"Captured: {entry.get('timestamp', '')}",
                "",
                str(entry.get("content", "")),
                "",
            ]
        )
        try:
            if not atomic_write_text(target, contents):
                raise PersistenceError(f"Could not write loot export to {target}")
        except OSError as exc:
            raise PersistenceError(f"Could not write loot export to {target}: {exc}") from exc
        return target

    def export_entry_to_file_with_feedback(
        self, entry_id: str, parent_widget: Optional[QWidget] = None
    ) -> Optional[Path]:
        """Exports one entry and reports the outcome to the user."""
        try:
            output_path = self.export_entry_to_file(entry_id)
        except (PersistenceError, OSError, ValueError) as exc:
            logger.error("Loot file export failed for %s: %s", entry_id, exc, exc_info=True)
            QMessageBox.warning(
                parent_widget,
                "Export fehlgeschlagen",
                f"Loot-Datei konnte nicht exportiert werden:\n{exc}",
            )
            return None

        QMessageBox.information(
            parent_widget, "Loot-Datei exportiert", f"Gespeichert unter:\n{output_path}"
        )
        return output_path

    def get_type_filter_actions(
        self, on_select_type: Optional[Callable[[str], None]] = None
    ) -> List[MenuAction]:
        """Returns a list of MenuAction DTOs for filtering loot by type."""
        counts = self.get_type_counts(target_ip=None)
        actions: List[MenuAction] = [
            MenuAction(
                id="type:all",
                text=f"All ({counts.get('all', 0)})",
                checked=(self.current_loot_type == "all"),
                callback=lambda: (
                    on_select_type("all") if on_select_type else self.select_loot_type("all")
                ),
                data={"type": "all"},
            )
        ]
        for loot_type in LOOT_TYPES:
            tid = loot_type["id"]
            count = counts.get(tid, 0)
            actions.append(
                MenuAction(
                    id=f"type:{tid}",
                    text=f"{loot_type['name']} ({count})",
                    checked=(self.current_loot_type == tid),
                    callback=lambda target_id=tid: (
                        on_select_type(target_id)
                        if on_select_type
                        else self.select_loot_type(target_id)
                    ),
                    data={"type": tid},
                )
            )
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
        export_tooltip: str,
        on_export_obsidian: Optional[Callable[[], None]] = None,
        on_toggle_view: Optional[Callable[[], None]] = None,
        view_mode: str = "list",
    ) -> None:
        self.filter_buttons.clear()
        counts = self.loot_manager.get_type_counts(target_ip=None)
        all_btn = QPushButton(f"All ({counts.get('all', 0)})")
        all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        all_btn.setProperty(
            "class", "FilterPillActive" if self.current_loot_type == "all" else "FilterPill"
        )
        all_btn.clicked.connect(lambda: on_select_type("all"))
        self.filter_buttons["all"] = all_btn
        pills_layout.addWidget(all_btn)

        for loot_type in LOOT_TYPES:
            tid = loot_type["id"]
            count = counts.get(tid, 0)
            btn = QPushButton(f"{loot_type['name']} ({count})")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty(
                "class", "FilterPillActive" if self.current_loot_type == tid else "FilterPill"
            )
            btn.clicked.connect(lambda checked=False, type_id=tid: on_select_type(type_id))
            self.filter_buttons[tid] = btn
            pills_layout.addWidget(btn)

        pills_layout.addStretch()

        # Contextual Loot Action Buttons
        if on_toggle_view is not None:
            showing_board = view_mode == "board"
            btn_view = QPushButton(
                t("loot.view_classic", "Classic")
                if showing_board
                else t("loot.view_kanban", "Kanban")
            )
            btn_view.setObjectName("LootViewToggleButton")
            btn_view.setProperty("class", "MiniActionBtn")
            btn_view.setToolTip(
                t(
                    "loot.toggle_view_tip",
                    "Switch between classic list and Kanban board",
                )
            )
            btn_view.clicked.connect(on_toggle_view)
            pills_layout.addWidget(btn_view)

        btn_export = QPushButton("Export (.md)")
        btn_export.setObjectName("LootExportButton")
        btn_export.setProperty("class", "MiniActionBtn")
        btn_export.setToolTip(export_tooltip)
        btn_export.clicked.connect(on_export)
        pills_layout.addWidget(btn_export)

        if on_export_obsidian is not None:
            btn_obsidian = QPushButton("Obsidian")
            btn_obsidian.setProperty("class", "MiniActionBtn")
            btn_obsidian.setToolTip(
                t(
                    "loot.export_obsidian_tip",
                    "Append the current loot to the exported Obsidian project note",
                )
            )
            btn_obsidian.clicked.connect(on_export_obsidian)
            pills_layout.addWidget(btn_obsidian)

        btn_clear = QPushButton("Clear")
        btn_clear.setProperty("class", "MiniDangerBtn")
        btn_clear.setToolTip(t("loot.clear_tip", "Clear this project's session loot"))
        btn_clear.clicked.connect(on_clear)
        pills_layout.addWidget(btn_clear)

    def render_content(
        self,
        content_layout: QVBoxLayout,
        search_query: str,
        proj_dir: Path,
        on_delete_loot: Callable[[str], None],
        on_edit_loot: Callable[[Dict[str, Any]], None],
        on_export_loot: Callable[[str], None],
        parent_widget: QWidget,
        show_empty_state_fn: Callable[[str], None],
        on_export_obsidian: Optional[Callable[[str], None]] = None,
        on_copied: Optional[Callable[[str], None]] = None,
    ) -> List[QWidget]:
        loot_entries = self.get_entries(
            target_ip=None, entry_type=self.current_loot_type, search_query=search_query
        )

        if not loot_entries:
            show_empty_state_fn(
                t(
                    "loot.empty_state",
                    "No session loot captured yet. Press Ctrl+N to add notes/credentials or Snip for screenshots.",
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
                card.export_requested.connect(on_export_loot)
                if on_export_obsidian is not None:
                    card.obsidian_export_requested.connect(on_export_obsidian)
                if on_copied is not None:
                    card.copied.connect(on_copied)
                content_layout.addWidget(card)
                rendered_cards.append(card)

        return rendered_cards

    def render_board_content(
        self,
        content_layout: QVBoxLayout,
        search_query: str,
        proj_dir: Path,
        on_delete_loot: Callable[[str], None],
        on_edit_loot: Callable[[Dict[str, Any]], None],
        on_export_loot: Callable[[str], None],
        on_move_loot: Callable[[str, str, int], bool],
        parent_widget: QWidget,
        on_export_obsidian: Optional[Callable[[str], None]] = None,
        on_copied: Optional[Callable[[str], None]] = None,
    ) -> List[QWidget]:
        """Renders the alternate Kanban presentation using the same LootCards."""
        loot_entries = self.get_entries(
            target_ip=None,
            entry_type=self.current_loot_type,
            search_query=search_query,
        )
        board = LootBoard(
            entries=loot_entries,
            project_dir=proj_dir,
            on_delete=on_delete_loot,
            on_edit=on_edit_loot,
            on_export=on_export_loot,
            on_move=on_move_loot,
            on_export_obsidian=on_export_obsidian,
            on_copied=on_copied,
            parent=parent_widget,
        )
        content_layout.addWidget(board)
        return [board]

    def open_add_dialog(
        self,
        parent_widget: Optional[QWidget] = None,
        target_ip: str = "",
        default_target: str = "",
        default_type: str = "note",
        default_category: str = "misc",
        default_title: str = "",
        default_content: str = "",
        default_severity: str = "info",
        modal: bool = True,
        on_accepted: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> bool:
        """Open the loot dialog with optional values prefilled by its caller.

        If modal=True (default), runs synchronously as a blocking modal dialog.
        If modal=False, opens non-modally as a floating remote control window.
        """
        if not modal:
            if self._active_add_dialog is not None and self._active_add_dialog.isVisible():
                self._active_add_dialog.raise_()
                self._active_add_dialog.activateWindow()
                if hasattr(self._active_add_dialog, "txt_title"):
                    self._active_add_dialog.txt_title.setFocus()
                return True

            dlg = AddLootDialog(
                parent=None,
                target_ip=target_ip or default_target,
                default_type=default_type,
                default_category=default_category,
                default_title=default_title,
                default_content=default_content,
                default_severity=default_severity,
            )
            dlg.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )

            cursor_pos = QCursor.pos()
            screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
            dlg_width = dlg.width()
            dlg_height = dlg.height()
            target_x = cursor_pos.x() - (dlg_width // 2)
            target_y = cursor_pos.y() - (dlg_height // 2)
            if screen:
                geom = screen.availableGeometry()
                target_x = max(geom.left() + 10, min(target_x, geom.right() - dlg_width - 10))
                target_y = max(geom.top() + 10, min(target_y, geom.bottom() - dlg_height - 10))
            dlg.move(QPoint(target_x, target_y))

            def _handle_accepted() -> None:
                data = dlg.get_data()
                self.add_entry(
                    entry_type=data["type"],
                    title=data["title"],
                    content=data["content"],
                    target_ip=data["target_ip"],
                    category=data.get("category", "misc"),
                    severity=data.get("severity", "info"),
                )
                if on_accepted:
                    on_accepted(data)

            def _handle_finished() -> None:
                if self._active_add_dialog is dlg:
                    self._active_add_dialog = None

            dlg.accepted.connect(_handle_accepted)
            dlg.finished.connect(_handle_finished)
            self._active_add_dialog = dlg

            dlg.show()
            if os.name == "nt":
                try:
                    import ctypes

                    user32 = ctypes.windll.user32
                    kernel32 = ctypes.windll.kernel32
                    hwnd = int(dlg.winId())
                    fg = user32.GetForegroundWindow()
                    if fg != hwnd:
                        fore_thread = user32.GetWindowThreadProcessId(fg, None)
                        app_thread = kernel32.GetCurrentThreadId()
                        if fore_thread != app_thread and fore_thread != 0:
                            user32.AttachThreadInput(fore_thread, app_thread, True)
                            user32.BringWindowToTop(hwnd)
                            user32.SetForegroundWindow(hwnd)
                            user32.AttachThreadInput(fore_thread, app_thread, False)
                        else:
                            user32.BringWindowToTop(hwnd)
                            user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass

            dlg.raise_()
            dlg.activateWindow()
            if hasattr(dlg, "txt_title"):
                dlg.txt_title.setFocus()
            return True

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
            if on_accepted:
                on_accepted(data)
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

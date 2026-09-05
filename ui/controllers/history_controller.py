from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from PyQt6.QtCore import QObject, Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QFileDialog,
)

from core.clipboard_history import ClipboardHistory
from core.loot.manager import LootManager
from core.project import ProjectManager
from core.storage import PersistenceError, StorageError
from core.logger import get_logger
from core.menu_actions import MenuAction
from core.event_bus import EventBus, EventType
from core.i18n import t
from ui.history_card import HistoryCard
from ui.clipboard_monitor import ClipboardMonitor
from ui.styles.icons import icon

logger = get_logger("history_controller")


class HistoryController(QObject):
    """UI-independent controller managing clipboard history, filtering, recording status, and domain actions."""

    history_filter_changed = pyqtSignal(str)
    history_updated = pyqtSignal()

    def __init__(
        self,
        clipboard_history: ClipboardHistory,
        loot_manager: LootManager,
        project_manager: ProjectManager,
        clipboard_monitor: Optional[ClipboardMonitor] = None,
        event_bus: Optional[EventBus] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.clipboard_history = clipboard_history
        self.clipboard_monitor = clipboard_monitor
        self.loot_manager = loot_manager
        self.project_manager = project_manager
        self.event_bus = event_bus if event_bus is not None else EventBus()
        self.current_history_filter: str = "all"
        self.filter_buttons: Dict[str, QPushButton] = {}

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
            t("dialog.storage_error", "Speicherfehler"),
            t(
                "history.storage_error_msg",
                "Clipboard-Verlauf konnte nicht auf die Festplatte geschrieben werden:\n{error}\n\nDie laufenden Sitzungsdaten im Speicher bleiben geschützt.",
                error=str(error),
            ),
        )

    # ------------------------------------------------------------------ #
    # Pure Domain Methods (UI-Independent)
    # ------------------------------------------------------------------ #

    def get_history(
        self,
        target_ip: Optional[str] = None,
        filter_type: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        active_filter = filter_type if filter_type is not None else self.current_history_filter
        actual_target = target_ip if active_filter == "target_only" else None
        actual_filter_type = active_filter if active_filter in ["commands", "outputs"] else "all"
        return self.clipboard_history.get_history(
            target_ip=actual_target, filter_type=actual_filter_type, search_query=search_query
        )

    def add_entry(self, text: str, target_ip: Optional[str] = None) -> None:
        try:
            entry = self.clipboard_history.add_entry(text=text, target_ip=target_ip)
            if entry is not None:
                self.history_updated.emit()
        except (PersistenceError, StorageError, OSError) as e:
            self._notify_persistence_error("add_entry", e)

    def clear_history(self, parent_widget: Optional[QWidget] = None) -> bool:
        if parent_widget:
            reply = QMessageBox.question(
                parent_widget,
                t("history.clear_title", "Clear History"),
                t(
                    "history.clear_confirm",
                    "Are you sure you want to delete all recorded clipboard history for this project?",
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
        try:
            self.clipboard_history.clear_history()
            self.history_updated.emit()
            return True
        except (PersistenceError, StorageError, OSError) as e:
            self._notify_persistence_error("clear_history", e, parent_widget)
            return False

    def delete_entry(self, item_id: str) -> None:
        try:
            if self.clipboard_history.delete_entry(item_id):
                self.history_updated.emit()
        except (PersistenceError, StorageError, OSError) as e:
            self._notify_persistence_error("delete_entry", e)

    def update_entry(self, entry_id: str, text: str, target_ip: str = "") -> bool:
        """Updates text and target IP of a clipboard history entry."""
        try:
            res = self.clipboard_history.update_entry(
                entry_id=entry_id, text=text, target_ip=target_ip
            )
            if res is not None:
                self.history_updated.emit()
                return True
            return False
        except (PersistenceError, StorageError, OSError) as e:
            self._notify_persistence_error("update_entry", e)
            return False

    def open_edit_dialog(self, parent_widget: QWidget, entry: Dict[str, Any]) -> bool:
        """Opens modal dialog to edit a clipboard history entry."""
        from ui.history_edit_dialog import EditHistoryDialog

        dlg = EditHistoryDialog(entry, parent=parent_widget)
        if dlg.exec():
            data = dlg.get_data()
            return self.update_entry(
                entry_id=entry.get("id", ""),
                text=data["text"],
                target_ip=data.get("target_ip", ""),
            )
        return False

    def toggle_pause(self) -> bool:
        if self.clipboard_monitor is None:
            return True
        is_paused = self.clipboard_monitor.toggle_pause()
        self.history_updated.emit()
        self.event_bus.publish(EventType.LOGGING_STATE_CHANGED, {"is_active": not is_paused})
        return is_paused

    def is_paused(self) -> bool:
        return self.clipboard_monitor is None or self.clipboard_monitor.is_paused

    def export_report_markdown(self, output_path: Path, target_ip: Optional[str] = None) -> str:
        from core.reporting.builder import ReportBuilder

        builder = ReportBuilder(
            loot_manager=self.loot_manager, clipboard_watcher=self.clipboard_history
        )
        return builder.export(output_path, target_ip=target_ip)

    def get_filter_actions(
        self, on_select_filter: Optional[Callable[[str], None]] = None
    ) -> List[MenuAction]:
        """Returns a list of MenuAction DTOs for filtering history."""
        history_all = self.clipboard_history.get_history()
        pills = [
            ("all", f"All ({len(history_all)})"),
            ("target_only", "Target IP Only"),
            ("commands", "Commands"),
            ("outputs", "Outputs"),
        ]
        actions: List[MenuAction] = []
        for pid, ptext in pills:
            actions.append(
                MenuAction(
                    id=f"history_filter:{pid}",
                    text=ptext,
                    checked=(self.current_history_filter == pid),
                    callback=lambda target_pid=pid: (
                        on_select_filter(target_pid)
                        if on_select_filter
                        else self.select_history_filter(target_pid)
                    ),
                    data={"filter": pid},
                )
            )
        return actions

    # ------------------------------------------------------------------ #
    # UI Adapters (Pills & Rendering)
    # ------------------------------------------------------------------ #

    def select_history_filter(self, filter_id: str) -> None:
        self.current_history_filter = filter_id
        for fid, btn in self.filter_buttons.items():
            btn.setProperty("class", "FilterPillActive" if fid == filter_id else "FilterPill")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.history_filter_changed.emit(filter_id)

    def build_filter_pills(
        self,
        pills_layout: QHBoxLayout,
        on_select_filter: Callable[[str], None],
        on_export: Callable[[], None],
        on_clear: Callable[[], None],
        export_tooltip: str,
    ) -> None:
        self.filter_buttons.clear()
        history_all = self.clipboard_history.get_history()
        pills = [
            ("all", f"All ({len(history_all)})"),
            ("target_only", "Target IP Only"),
            ("commands", "Commands"),
            ("outputs", "Outputs"),
        ]
        for pid, ptext in pills:
            btn = QPushButton(ptext)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty(
                "class", "FilterPillActive" if self.current_history_filter == pid else "FilterPill"
            )
            btn.clicked.connect(lambda checked=False, fid=pid: on_select_filter(fid))
            self.filter_buttons[pid] = btn
            pills_layout.addWidget(btn)

        pills_layout.addStretch()

        # Contextual History Action Buttons
        btn_export = QPushButton("Report (.md)")
        btn_export.setIcon(icon("fa5s.file-export"))
        btn_export.setIconSize(QSize(12, 12))
        btn_export.setProperty("class", "MiniActionBtn")
        btn_export.setToolTip(export_tooltip)
        btn_export.clicked.connect(on_export)
        pills_layout.addWidget(btn_export)

        btn_clear = QPushButton("Clear")
        btn_clear.setIcon(icon("fa5s.trash"))
        btn_clear.setIconSize(QSize(12, 12))
        btn_clear.setProperty("class", "MiniDangerBtn")
        btn_clear.setToolTip(t("history.clear_tip", "Clear this project's clipboard history"))
        btn_clear.clicked.connect(on_clear)
        pills_layout.addWidget(btn_clear)

    def render_content(
        self,
        content_layout: QVBoxLayout,
        search_query: str,
        target_ip: Optional[str],
        on_add_to_loot: Callable[[Dict[str, Any]], None],
        on_delete_entry: Callable[[str], None],
        parent_widget: QWidget,
        show_empty_state_fn: Callable[[str], None],
        on_copied: Optional[Callable[[str], None]] = None,
        on_add_to_note: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_edit_history: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[QWidget]:
        history_items = self.get_history(target_ip=target_ip, search_query=search_query)

        if not history_items:
            show_empty_state_fn(
                t(
                    "history.empty_state",
                    "No clipboard history recorded yet. Enable REC (Ctrl+P) and copy commands in your terminal.",
                )
            )
            return []

        rendered_cards: List[QWidget] = []
        for item in history_items:
            card = HistoryCard(item, parent=parent_widget)
            card.transfer_to_loot.connect(on_add_to_loot)
            if on_add_to_note is not None:
                card.transfer_to_note.connect(on_add_to_note)
            card.entry_deleted.connect(on_delete_entry)
            if on_copied is not None:
                card.copied.connect(on_copied)
            if on_edit_history is not None:
                card.edit_requested.connect(on_edit_history)
            else:
                card.edit_requested.connect(
                    lambda entry, p=parent_widget: self.open_edit_dialog(p, entry)
                )
            content_layout.addWidget(card)
            rendered_cards.append(card)

        return rendered_cards

    def export_report_dialog(
        self, parent_widget: QWidget, target_ip: Optional[str] = None
    ) -> Optional[str]:
        active_proj = self.project_manager.get_active_project()
        proj_dir = self.project_manager.get_project_dir(active_proj)
        default_file = proj_dir / "report.md"

        file_path, _ = QFileDialog.getSaveFileName(
            parent_widget,
            t("history.export_report_title", "Pentest Report exportieren"),
            str(default_file),
            "Markdown Files (*.md);;All Files (*)",
        )
        if file_path:
            out_path = Path(file_path)
            res = self.export_report_markdown(out_path, target_ip=target_ip)
            QMessageBox.information(
                parent_widget, t("history.export_result_title", "Report Export"), res
            )
            return res
        return None

    export_report = export_report_dialog

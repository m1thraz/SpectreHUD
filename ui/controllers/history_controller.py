from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QFileDialog

from core.clipboard_watcher import ClipboardWatcher
from core.loot_manager import LootManager
from core.project_manager import ProjectManager
from core.report_builder import ReportBuilder
from ui.history_card import HistoryCard
from ui.styles import CYBER_DARK_QSS


class HistoryController(QObject):
    """Controller managing clipboard history, filtering, recording status, and report export."""

    history_filter_changed = pyqtSignal(str)
    history_updated = pyqtSignal()

    def __init__(
        self,
        clipboard_watcher: ClipboardWatcher,
        loot_manager: LootManager,
        project_manager: ProjectManager,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.clipboard_watcher = clipboard_watcher
        self.loot_manager = loot_manager
        self.project_manager = project_manager
        self.current_history_filter: str = "all"
        self.filter_buttons: Dict[str, QPushButton] = {}

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
        export_tooltip: str
    ) -> None:
        self.filter_buttons.clear()
        history_all = self.clipboard_watcher.get_history()
        pills = [
            ("all", f"All ({len(history_all)})"),
            ("target_only", "Target IP Only"),
            ("commands", "Commands"),
            ("outputs", "Outputs")
        ]
        for pid, ptext in pills:
            btn = QPushButton(ptext)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("class", "FilterPillActive" if self.current_history_filter == pid else "FilterPill")
            btn.clicked.connect(lambda checked=False, fid=pid: on_select_filter(fid))
            self.filter_buttons[pid] = btn
            pills_layout.addWidget(btn)

        pills_layout.addStretch()

        # Contextual History Action Buttons
        btn_export = QPushButton("Report (.md)")
        btn_export.setProperty("class", "MiniActionBtn")
        btn_export.setToolTip(export_tooltip)
        btn_export.clicked.connect(on_export)
        pills_layout.addWidget(btn_export)

        btn_clear = QPushButton("Clear")
        btn_clear.setProperty("class", "MiniDangerBtn")
        btn_clear.setToolTip("Clipboard-Historie dieses Projekts leeren")
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
        show_empty_state_fn: Callable[[str], None]
    ) -> List[QWidget]:
        history_items = self.clipboard_watcher.get_history(
            target_ip=target_ip if self.current_history_filter == "target_only" else None,
            filter_type=self.current_history_filter if self.current_history_filter in ["commands", "outputs"] else "all",
            search_query=search_query
        )

        if not history_items:
            show_empty_state_fn("Keine Clipboard-Historie vorhanden. Aktiviere REC (Ctrl+P) und kopiere Befehle im Terminal.")
            return []

        rendered_cards: List[QWidget] = []
        for item in history_items:
            card = HistoryCard(item, parent=parent_widget)
            card.add_to_loot_requested.connect(on_add_to_loot)
            card.entry_deleted.connect(on_delete_entry)
            content_layout.addWidget(card)
            rendered_cards.append(card)

        return rendered_cards

    def toggle_pause(self) -> None:
        self.clipboard_watcher.toggle_pause()

    def update_rec_indicator(self, btn_indicator: QPushButton, is_active: bool) -> None:
        if is_active:
            btn_indicator.setText("REC: ON")
            btn_indicator.setProperty("paused", "false")
            btn_indicator.setToolTip("Clipboard-Logger ist AKTIV (schneidet alle Kopien mit).\nKlicken oder Ctrl+P zum Pausieren.")
        else:
            btn_indicator.setText("REC: Off")
            btn_indicator.setProperty("paused", "true")
            btn_indicator.setToolTip("Clipboard-Logger ist PAUSIERT (keine Aufzeichnung).\nKlicken oder Ctrl+P zum Fortsetzen.")

        btn_indicator.style().unpolish(btn_indicator)
        btn_indicator.style().polish(btn_indicator)

    def delete_entry(self, entry_id: str) -> None:
        self.clipboard_watcher.delete_entry(entry_id)
        self.history_updated.emit()

    def clear_history(self, parent_widget: QWidget) -> bool:
        msg = QMessageBox(parent_widget)
        msg.setWindowTitle("Historie leeren")
        msg.setText("Möchtest du wirklich die gesamte Clipboard-Historie dieses Projekts löschen?")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.setStyleSheet(CYBER_DARK_QSS)

        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.clipboard_watcher.clear_history()
            self.history_updated.emit()
            return True
        return False

    def export_report(self, parent_widget: QWidget, target_ip: str, active_proj: str) -> None:
        proj_dir = self.project_manager.get_project_dir(active_proj)
        default_path = proj_dir / "report.md"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            parent_widget, "CTF Write-Up Report exportieren", str(default_path), "Markdown (*.md);;HTML (*.html);;All Files (*)"
        )
        if file_path:
            target = Path(file_path)
            builder = ReportBuilder(
                loot_manager=self.loot_manager,
                clipboard_watcher=self.clipboard_watcher,
                project_manager=self.project_manager
            )
            md_content = builder.build(
                target_ip=target_ip if target_ip else None,
                project_name=active_proj
            )
            if target.suffix.lower() == ".html" or ("html" in selected_filter.lower() and target.suffix.lower() != ".md"):
                if target.suffix.lower() != ".html":
                    target = target.with_suffix(".html")
                from core.html_report_exporter import HtmlReportExporter
                success = HtmlReportExporter.export_to_file(
                    markdown_content=md_content,
                    output_path=target,
                    project_dir=proj_dir,
                    project_name=active_proj,
                    target_ip=target_ip
                )
                report_msg = f"HTML-Report erfolgreich generiert: {target.name}" if success else f"Fehler beim Exportieren: {target.name}"
            else:
                report_msg = builder.export(
                    target,
                    target_ip=target_ip if target_ip else None,
                    project_name=active_proj
                )

            is_error = report_msg.startswith("Fehler")
            msg = QMessageBox(parent_widget)
            msg.setWindowTitle("Fehler beim Export" if is_error else "Report generiert")
            msg.setText(report_msg)
            msg.setIcon(QMessageBox.Icon.Warning if is_error else QMessageBox.Icon.Information)
            msg.setStyleSheet(CYBER_DARK_QSS)
            msg.exec()

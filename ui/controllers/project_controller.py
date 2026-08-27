from typing import Optional, Callable
from pathlib import Path
from PyQt6.QtCore import QObject, QPoint, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QWidget, QPushButton, QMenu, QFileDialog

from core.project_manager import ProjectManager
from ui.project_dialog import NewProjectDialog
from core.i18n import t


class ProjectController(QObject):
    """UI Controller managing project/box dropdown menus, selection, import, and creation dialogs."""

    project_selected = pyqtSignal(str)
    project_created = pyqtSignal(str)

    def __init__(self, project_manager: ProjectManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.project_manager = project_manager

    def show_project_menu(
        self,
        btn_project: QPushButton,
        on_switch_project: Callable[[str], None],
        on_open_new_project: Callable[[], None],
        parent_widget: QWidget
    ) -> None:
        menu = QMenu(parent_widget)
        active_proj = self.project_manager.get_active_project()
        all_projects = self.project_manager.list_projects()

        # Project list
        for p in all_projects:
            prefix = "✓ " if p == active_proj else "   "
            act = QAction(f"{prefix}{p}", menu)
            act.triggered.connect(lambda checked=False, pname=p: on_switch_project(pname))
            menu.addAction(act)

        menu.addSeparator()

        # Action: New Project
        act_new = QAction(t("project.new_project", "+ Neues Projekt / Box erstellen..."), menu)
        act_new.triggered.connect(on_open_new_project)
        menu.addAction(act_new)

        # Action: Import Existing Project Folder
        act_import = QAction(t("project.import_folder", "Projekt-Ordner importieren / öffnen..."), menu)
        act_import.triggered.connect(lambda: self._on_import_project(parent_widget, on_switch_project))
        menu.addAction(act_import)

        # Action: Archive Box (.zip)
        act_archive = QAction(t("project.archive", "📦 Box archivieren (.zip)..."), menu)
        act_archive.triggered.connect(lambda: self._on_archive_project(parent_widget))
        menu.addAction(act_archive)

        # Action: Open in Explorer
        act_open_folder = QAction(t("project.open_folder", "Projektordner im Explorer öffnen"), menu)
        act_open_folder.triggered.connect(lambda: self.project_manager.open_project_folder())
        menu.addAction(act_open_folder)

        # Show menu under project button
        menu.exec(btn_project.mapToGlobal(QPoint(0, btn_project.height() + 4)))

    def _on_archive_project(self, parent_widget: QWidget) -> None:
        """Prompts user to select output zip path and creates a compressed project archive."""
        from PyQt6.QtWidgets import QMessageBox
        from ui.styles import CYBER_DARK_QSS
        from datetime import datetime
        import sys, subprocess, os

        active_proj = self.project_manager.get_active_project()
        proj_dir = self.project_manager.get_project_dir(active_proj)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_zip = proj_dir.parent / f"{active_proj}_archive_{ts}.zip"

        file_path, _ = QFileDialog.getSaveFileName(
            parent_widget,
            t("project.archive_title", "Box als ZIP archivieren"),
            str(default_zip),
            "ZIP Archives (*.zip);;All Files (*)"
        )
        if not file_path:
            return

        out_zip = Path(file_path)
        result = self.project_manager.archive_project(active_proj, out_zip)
        if result.get("success"):
            zip_path = result.get("zip_path")
            file_count = result.get("file_count", 0)
            comp_bytes = result.get("compressed_bytes", 0)
            size_mb = comp_bytes / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB" if size_mb >= 0.1 else f"{comp_bytes / 1024:.1f} KB"

            msg = QMessageBox(parent_widget)
            msg.setWindowTitle(t("project.archive_success_title", "Archiv erstellt"))
            msg.setText(
                f"Die Box '{active_proj}' wurde erfolgreich archiviert:\n\n"
                f"📁 ZIP-Datei: {zip_path.name}\n"
                f"📄 Enthaltene Dateien: {file_count}\n"
                f"📦 Komprimierte Größe: {size_str}\n\n"
                f"Ordner im Explorer öffnen?"
            )
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.Yes)
            msg.setStyleSheet(CYBER_DARK_QSS)
            if msg.exec() == QMessageBox.StandardButton.Yes:
                folder_to_open = zip_path.parent
                try:
                    if sys.platform == "win32":
                        os.startfile(str(folder_to_open))
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", str(folder_to_open)])
                    else:
                        subprocess.Popen(["xdg-open", str(folder_to_open)])
                except Exception:
                    pass
        else:
            err = result.get("error", "Unbekannter Fehler")
            msg = QMessageBox(parent_widget)
            msg.setWindowTitle(t("project.archive_error_title", "Archivierung fehlgeschlagen"))
            msg.setText(f"Fehler beim Erstellen des ZIP-Archivs:\n{err}")
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setStyleSheet(CYBER_DARK_QSS)
            msg.exec()

    def _on_import_project(self, parent_widget: QWidget, on_switch_project: Callable[[str], None]) -> None:
        """Opens folder browser to register and activate an existing project directory."""
        folder = QFileDialog.getExistingDirectory(
            parent_widget,
            t("project.import_title", "Projekt-Ordner auswählen"),
            str(self.project_manager.base_dir)
        )
        if folder:
            pname = self.project_manager.import_project_folder(folder)
            if pname:
                on_switch_project(pname)
                self.project_selected.emit(pname)

    def open_new_project_dialog(
        self,
        parent_widget: QWidget,
        default_target: str,
        default_attacker: str,
        default_port: str,
        on_project_created: Callable[[str], None]
    ) -> bool:
        from core.project_manager import ProjectExistsError
        dlg = NewProjectDialog(
            parent_widget,
            default_target=default_target,
            default_attacker=default_attacker,
            default_port=default_port,
            default_base_dir=self.project_manager.base_dir,
            project_manager=self.project_manager
        )
        if dlg.exec():
            data = dlg.get_data()
            pname = data.get("name")
            if pname:
                custom_base = data.get("base_dir")
                try:
                    self.project_manager.create_project(
                        name=pname,
                        target_ip=data.get("target_ip", ""),
                        attacker_ip=data.get("attacker_ip", ""),
                        port=data.get("port", "4444"),
                        base_dir=Path(custom_base) if custom_base else None
                    )
                    clean_name = self.project_manager._sanitize_name(pname)
                    on_project_created(clean_name)
                    self.project_created.emit(clean_name)
                    return True
                except ProjectExistsError as e:
                    QMessageBox.warning(parent_widget, "Projekt existiert bereits", str(e))
                    return False
        return False

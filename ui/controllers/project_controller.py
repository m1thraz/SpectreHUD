"""
Project Controller managing project state, workspace actions, and MenuAction DTOs.
"""
from typing import Optional, Callable, List, Dict, Any
from pathlib import Path
from PyQt6.QtCore import QObject, QPoint, pyqtSignal
from PyQt6.QtWidgets import QWidget, QPushButton, QFileDialog, QMessageBox

from core.project_manager import ProjectManager, ProjectExistsError
from core.project.validator import ProjectError
from core.storage import PersistenceError, StorageError
from core.logger import get_logger
from core.menu_actions import MenuAction
from core.event_bus import EventBus, EventType
from core.i18n import t
from ui.menu_builder import build_qmenu
from ui.project_dialog import NewProjectDialog

logger = get_logger("project_controller")


class ProjectController(QObject):
    """UI-independent controller managing project lifecycle, metadata, and MenuAction DTOs."""

    project_selected = pyqtSignal(str)
    project_created = pyqtSignal(str)

    def __init__(
        self,
        project_manager: ProjectManager,
        event_bus: Optional[EventBus] = None,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.project_manager = project_manager
        self.event_bus = event_bus if event_bus is not None else EventBus()

    # ------------------------------------------------------------------ #
    # Pure Domain & DTO Methods (UI-Independent)
    # ------------------------------------------------------------------ #

    def get_active_project(self) -> str:
        return self.project_manager.get_active_project()

    def list_projects(self) -> List[str]:
        return self.project_manager.list_projects()

    def create_project(
        self,
        name: str,
        target_ip: str = "",
        attacker_ip: str = "",
        port: str = "4444",
        base_dir: Optional[Path] = None
    ) -> str:
        self.project_manager.create_project(
            name=name,
            target_ip=target_ip,
            attacker_ip=attacker_ip,
            port=port,
            base_dir=base_dir
        )
        clean_name = self.project_manager._sanitize_name(name)
        self.project_created.emit(clean_name)
        return clean_name

    def import_project_folder(self, folder_path: str) -> Optional[str]:
        pname = self.project_manager.import_project_folder(folder_path)
        if pname:
            self.project_selected.emit(pname)
        return pname

    def archive_project(self, project_name: str, target_zip_path: Path) -> Dict[str, Any]:
        return self.project_manager.archive_project(project_name, target_zip_path)

    def open_project_folder(self) -> None:
        self.project_manager.open_project_folder()

    def get_project_menu_actions(
        self,
        on_switch_project: Optional[Callable[[str], None]] = None,
        on_open_new_project: Optional[Callable[[], None]] = None,
        on_import_project: Optional[Callable[[], None]] = None,
        on_archive_project: Optional[Callable[[], None]] = None,
        on_open_folder: Optional[Callable[[], None]] = None
    ) -> List[MenuAction]:
        """Generates a list of UI-independent MenuAction DTOs for the project selector menu."""
        actions: List[MenuAction] = []
        active_proj = self.get_active_project()
        all_projects = self.list_projects()

        # Project list items
        for p in all_projects:
            is_active = (p == active_proj)
            prefix = "✓ " if is_active else "   "
            actions.append(MenuAction(
                id=f"switch_project:{p}",
                text=f"{prefix}{p}",
                checked=is_active,
                callback=lambda pname=p: on_switch_project(pname) if on_switch_project else self.project_selected.emit(pname),
                data={"project_name": p}
            ))

        actions.append(MenuAction.separator("sep_projects"))

        # Action: New Project
        actions.append(MenuAction(
            id="new_project",
            text=t("project.new_project", "+ Neues Projekt / Box erstellen..."),
            callback=on_open_new_project
        ))

        # Action: Import Existing Project Folder
        actions.append(MenuAction(
            id="import_folder",
            text=t("project.import_folder", "Projekt-Ordner importieren / öffnen..."),
            callback=on_import_project
        ))

        # Action: Archive Box (.zip)
        actions.append(MenuAction(
            id="archive_box",
            text=t("project.archive", "📦 Box archivieren (.zip)..."),
            callback=on_archive_project
        ))

        # Action: Open in Explorer
        actions.append(MenuAction(
            id="open_folder",
            text=t("project.open_folder", "Projektordner im Explorer öffnen"),
            callback=on_open_folder if on_open_folder else self.open_project_folder
        ))

        return actions

    # ------------------------------------------------------------------ #
    # UI Adapters (Backward-Compatibility & Dialog Triggers)
    # ------------------------------------------------------------------ #

    def show_project_menu(
        self,
        btn_project: QPushButton,
        on_switch_project: Callable[[str], None],
        on_open_new_project: Callable[[], None],
        parent_widget: QWidget
    ) -> None:
        """Constructs and displays the project selection popup menu under the given button."""
        actions = self.get_project_menu_actions(
            on_switch_project=on_switch_project,
            on_open_new_project=on_open_new_project,
            on_import_project=lambda: self._on_import_project(parent_widget, on_switch_project),
            on_archive_project=lambda: self._on_archive_project(parent_widget),
            on_open_folder=self.open_project_folder
        )

        menu = build_qmenu(actions, parent_widget=parent_widget)
        menu.exec(btn_project.mapToGlobal(QPoint(0, btn_project.height() + 4)))

    def _on_archive_project(self, parent_widget: QWidget) -> None:
        """Prompts user to select output zip path and creates a compressed project archive."""
        from ui.styles import CYBER_DARK_QSS
        from datetime import datetime
        import sys, subprocess, os

        active_proj = self.get_active_project()
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
        result = self.archive_project(active_proj, out_zip)
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
            try:
                pname = self.import_project_folder(folder)
                if pname:
                    on_switch_project(pname)
            except (ProjectError, PersistenceError, StorageError, OSError) as e:
                logger.error(f"Failed to import project folder '{folder}': {e}")
                QMessageBox.critical(
                    parent_widget,
                    "Import fehlgeschlagen",
                    f"Der Projektordner konnte nicht importiert werden:\n{e}"
                )

    def open_new_project_dialog(
        self,
        parent_widget: QWidget,
        default_target: str,
        default_attacker: str,
        default_port: str,
        on_project_created: Callable[[str], None]
    ) -> bool:
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
                    clean_name = self.create_project(
                        name=pname,
                        target_ip=data.get("target_ip", ""),
                        attacker_ip=data.get("attacker_ip", ""),
                        port=data.get("port", "4444"),
                        base_dir=Path(custom_base) if custom_base else None
                    )
                    on_project_created(clean_name)
                    return True
                except ProjectExistsError as e:
                    QMessageBox.warning(parent_widget, "Projekt existiert bereits", str(e))
                    return False
                except (ProjectError, PersistenceError, StorageError, OSError) as e:
                    logger.error(f"Failed to create project '{pname}': {e}")
                    QMessageBox.critical(
                        parent_widget,
                        "Projekt-Erstellung fehlgeschlagen",
                        f"Das Projekt konnte nicht erstellt werden:\n{e}"
                    )
                    return False
        return False

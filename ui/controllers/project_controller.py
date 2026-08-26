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

        # Action: Open in Explorer
        act_open_folder = QAction(t("project.open_folder", "Projektordner im Explorer öffnen"), menu)
        act_open_folder.triggered.connect(lambda: self.project_manager.open_project_folder())
        menu.addAction(act_open_folder)

        # Show menu under project button
        menu.exec(btn_project.mapToGlobal(QPoint(0, btn_project.height() + 4)))

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
        dlg = NewProjectDialog(
            parent_widget,
            default_target=default_target,
            default_attacker=default_attacker,
            default_port=default_port,
            default_base_dir=self.project_manager.base_dir
        )
        if dlg.exec():
            data = dlg.get_data()
            pname = data.get("name")
            if pname:
                custom_base = data.get("base_dir")
                self.project_manager.create_project(
                    name=pname,
                    target_ip=data.get("target_ip", ""),
                    attacker_ip=data.get("attacker_ip", ""),
                    port=data.get("port", "4444"),
                    base_dir=Path(custom_base) if custom_base else None
                )
                on_project_created(pname)
                self.project_created.emit(pname)
                return True
        return False

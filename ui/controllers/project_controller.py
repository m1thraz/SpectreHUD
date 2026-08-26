from typing import Optional, Callable
from PyQt6.QtCore import QObject, QPoint, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QWidget, QPushButton, QMenu

from core.project_manager import ProjectManager
from ui.project_dialog import NewProjectDialog


class ProjectController(QObject):
    """UI Controller managing project/box dropdown menus, selection, and creation dialogs."""

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
        act_new = QAction("+ Neues Projekt / Box erstellen...", menu)
        act_new.triggered.connect(on_open_new_project)
        menu.addAction(act_new)

        # Action: Open in Explorer
        act_open_folder = QAction("Projektordner im Explorer öffnen", menu)
        act_open_folder.triggered.connect(lambda: self.project_manager.open_project_folder())
        menu.addAction(act_open_folder)

        # Show menu under project button
        menu.exec(btn_project.mapToGlobal(QPoint(0, btn_project.height() + 4)))

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
                if custom_base and custom_base != self.project_manager.base_dir:
                    self.project_manager.base_dir = custom_base
                self.project_manager.create_project(
                    name=pname,
                    target_ip=data.get("target_ip", ""),
                    attacker_ip=data.get("attacker_ip", ""),
                    port=data.get("port", "4444")
                )
                on_project_created(pname)
                self.project_created.emit(pname)
                return True
        return False

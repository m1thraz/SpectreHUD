from typing import Dict, Any, Optional, Callable
from PyQt6.QtCore import QObject, QPoint, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QWidget, QPushButton, QMenu

from core.project_manager import ProjectManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from ui.project_dialog import NewProjectDialog
from ui.variable_bar import VariableBar


class ProjectController(QObject):
    """Controller managing project/box workspaces, switching, and state persistence."""

    project_switched = pyqtSignal(str)

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
        act_new = QAction("➕ Neues Projekt / Box erstellen...", menu)
        act_new.triggered.connect(on_open_new_project)
        menu.addAction(act_new)

        # Action: Open in Explorer
        act_open_folder = QAction("📂 Projektordner im Explorer öffnen", menu)
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
            default_port=default_port
        )
        if dlg.exec():
            data = dlg.get_data()
            pname = data.get("name")
            if pname:
                self.project_manager.create_project(
                    name=pname,
                    target_ip=data.get("target_ip", ""),
                    attacker_ip=data.get("attacker_ip", ""),
                    port=data.get("port", "4444")
                )
                on_project_created(pname)
                return True
        return False

    def load_active_project_state(
        self,
        btn_project: QPushButton,
        var_bar: Optional[VariableBar],
        loot_manager: LootManager,
        clipboard_watcher: ClipboardWatcher
    ) -> None:
        active_proj = self.project_manager.get_active_project()
        btn_project.setText(f"📁 Box: {active_proj} ▾")

        state = self.project_manager.load_project_state()
        if not state:
            return

        # Restore Variables in VariableBar
        if var_bar:
            var_bar.txt_target.blockSignals(True)
            var_bar.txt_attacker.blockSignals(True)
            var_bar.txt_port.blockSignals(True)

            var_bar.txt_target.setText(state.get("target_ip", "10.10.10.10"))
            var_bar.txt_attacker.setText(state.get("attacker_ip", "10.10.14.5"))
            var_bar.txt_port.setText(state.get("port", "4444"))

            var_bar.txt_target.blockSignals(False)
            var_bar.txt_attacker.blockSignals(False)
            var_bar.txt_port.blockSignals(False)

        # Restore Loot
        loot_manager.set_entries(state.get("loot", []))

        # Restore Clipboard History
        clipboard_watcher.set_history(state.get("clipboard_history", []))

    def save_current_project_state(
        self,
        var_bar: Optional[VariableBar],
        loot_manager: LootManager,
        clipboard_watcher: ClipboardWatcher
    ) -> None:
        target_ip = var_bar.txt_target.text().strip() if var_bar else "10.10.10.10"
        attacker_ip = var_bar.txt_attacker.text().strip() if var_bar else "10.10.14.5"
        port = var_bar.txt_port.text().strip() if var_bar else "4444"

        state = {
            "target_ip": target_ip,
            "attacker_ip": attacker_ip,
            "port": port,
            "loot": loot_manager.get_all_entries(),
            "clipboard_history": clipboard_watcher.get_all_history()
        }
        self.project_manager.save_project_state(state=state)

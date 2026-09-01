"""
Helper utility to construct styled Qt QMenu widgets from UI-independent MenuAction DTO lists.
"""

from typing import List, Optional, Callable
from PyQt6.QtWidgets import QMenu, QWidget
from PyQt6.QtGui import QAction
from core.menu_actions import MenuAction


def build_qmenu(
    actions: List[MenuAction],
    parent_widget: Optional[QWidget] = None,
    action_handler: Optional[Callable[[MenuAction], None]] = None,
) -> QMenu:
    """Builds a styled QMenu from a list of MenuAction DTOs."""
    menu = QMenu(parent_widget)
    for act in actions:
        if act.is_separator:
            menu.addSeparator()
            continue

        qact = QAction(act.text, menu)
        qact.setEnabled(act.enabled)
        if act.checked:
            qact.setCheckable(True)
            qact.setChecked(True)
        if act.tooltip:
            qact.setToolTip(act.tooltip)
            qact.setStatusTip(act.tooltip)
        if act.shortcut:
            qact.setShortcut(act.shortcut)

        def _make_slot(action_dto: MenuAction = act):
            def _slot(checked: bool = False):
                if action_dto.callback:
                    action_dto.callback()
                if action_handler:
                    action_handler(action_dto)

            return _slot

        qact.triggered.connect(_make_slot(act))
        menu.addAction(qact)

    return menu

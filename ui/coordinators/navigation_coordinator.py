"""
Navigation Coordinator for SpectreHUD.

Coordinates HUD mode navigation (Cheatsheet, Loot, History, Report) and panel visibilities.
"""

from typing import Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal

from core.event_bus import EventBus, EventType
from core.navigation_state import NavigationStateMachine
from core.logger import get_logger
from ui.panels.header_panel import HeaderPanel
from ui.panels.search_panel import SearchPanel
from ui.panels.content_panel import ContentPanel
from ui.variable_bar import VariableBar
from ui.controllers.report_controller import ReportController

logger = get_logger(__name__)


class NavigationCoordinator(QObject):
    """Coordinates mode transitions, panel visibility, and tab guards."""

    mode_changed = pyqtSignal(str)

    def __init__(
        self,
        header: HeaderPanel,
        search: SearchPanel,
        var_bar: VariableBar,
        content: ContentPanel,
        report_ctrl: ReportController,
        event_bus: EventBus,
        on_mode_switched: Optional[Callable[[str], None]] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.header = header
        self.search = search
        self.var_bar = var_bar
        self.content = content
        self.report_ctrl = report_ctrl
        self.event_bus = event_bus
        self.on_mode_switched = on_mode_switched

        self._state_machine = NavigationStateMachine(initial_mode="cheatsheet")

    @property
    def active_mode(self) -> str:
        return self._state_machine.active_mode

    def switch_mode(self, mode: str) -> bool:
        """Switches between 'cheatsheet', 'loot', 'history', and 'report' modes."""
        if self._state_machine.active_mode == "report" and mode != "report":
            if not self.report_ctrl.confirm_discard_if_dirty():
                return False

        if not self._state_machine.switch_mode(mode):
            return False

        self.header.set_active_mode(mode)

        self.content.set_privacy_banner_visible(mode == "history")
        self.search.setVisible(mode != "report")
        self.var_bar.setVisible(mode != "report")
        self.search.update_placeholder(mode)

        if mode != "report":
            self.search.set_focus()

        if self.on_mode_switched:
            self.on_mode_switched(mode)

        self.mode_changed.emit(mode)
        self.event_bus.publish(EventType.MODE_CHANGED, {"mode": mode})
        return True

    def toggle_mode(self) -> None:
        """Cycles through modes via Tab shortcut (Report mode excluded from Tab cycle)."""
        next_mode = self._state_machine.get_next_tab_mode()
        self.switch_mode(next_mode)

from typing import Optional
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QWidget
from PyQt6.QtCore import pyqtSignal, QEvent
from ui.search_bar import SearchBar
from core.i18n import t


class SearchPanel(QFrame):
    """
    Search and Filter bar panel.
    Encapsulates the spotlight SearchBar with live debouncing and the horizontal FilterPills bar.
    """

    search_changed = pyqtSignal(str)
    pills_width_changed = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("SearchPanel")
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Search Bar
        self.search_bar = SearchBar()
        self.search_bar.search_changed.connect(self.search_changed.emit)
        layout.addWidget(self.search_bar)

        # 2. Filter Pills Frame
        self.pills_frame = QFrame()
        self.pills_frame.setObjectName("FilterPillsFrame")
        self.pills_layout = QHBoxLayout(self.pills_frame)
        self.pills_layout.setContentsMargins(12, 2, 12, 6)
        self.pills_layout.setSpacing(6)
        self.pills_frame.installEventFilter(self)
        layout.addWidget(self.pills_frame)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.pills_frame and event.type() == QEvent.Type.Resize:
            width = self.get_pills_available_width()
            if width > 0:
                self.pills_width_changed.emit(width)
        return super().eventFilter(watched, event)

    def get_pills_available_width(self) -> int:
        margins = self.pills_layout.contentsMargins()
        w = self.pills_frame.width() - margins.left() - margins.right()
        return w if w >= 300 else 680

    def get_query(self) -> str:
        return self.search_bar.get_text()

    def clear_search(self) -> None:
        self.search_bar.clear()

    def set_focus(self) -> None:
        self.search_bar.set_focus()

    def get_pills_layout(self) -> QHBoxLayout:
        return self.pills_layout

    def clear_pills(self) -> None:
        while self.pills_layout.count():
            child = self.pills_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def update_placeholder(self, mode: str) -> None:
        """Updates the search input placeholder text according to current mode."""
        if mode == "cheatsheet":
            self.search_bar.txt_search.setPlaceholderText(
                t(
                    "search.cheatsheet_placeholder",
                    "Befehl, Tool oder Syntax suchen (z. B. 'curl', 'nmap', 'sql')...",
                )
            )
        elif mode == "loot":
            self.search_bar.txt_search.setPlaceholderText(
                t(
                    "search.loot_placeholder",
                    "Session Loot, Credentials, Hashes & Notizen durchsuchen...",
                )
            )
        elif mode == "history":
            self.search_bar.txt_search.setPlaceholderText(
                t(
                    "search.history_placeholder",
                    "Clipboard-Historie, kopierte Befehle & Ausgaben durchsuchen...",
                )
            )
        elif mode == "notes":
            self.search_bar.txt_search.setPlaceholderText(
                t(
                    "search.notes_placeholder",
                    "Quick-Notes & Notizen-Inbox durchsuchen...",
                )
            )

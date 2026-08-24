from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QWidget
from PyQt6.QtCore import pyqtSignal, Qt

class SearchBar(QFrame):
    """Minimalist Spotlight-style search bar for instant full-text filtering."""
    
    search_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("SearchSection")
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.txt_search = QLineEdit()
        self.txt_search.setObjectName("SpotlightSearch")
        self.txt_search.setPlaceholderText("⚡ Befehl, Tool oder Syntax suchen (z. B. 'curl', 'nmap', 'sql', 'suid', 'lfi')...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self.search_changed.emit)
        
        layout.addWidget(self.txt_search)

    def set_focus(self) -> None:
        self.txt_search.setFocus()
        self.txt_search.selectAll()

    def clear(self) -> None:
        self.txt_search.clear()

    def text(self) -> str:
        return self.txt_search.text().strip()

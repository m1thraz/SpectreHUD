from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QWidget
from PyQt6.QtCore import pyqtSignal, QTimer


class SearchBar(QFrame):
    """Minimalist Spotlight-style search bar with debounced live filtering."""

    search_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget = None, debounce_ms: int = 60):
        super().__init__(parent)
        self.debounce_ms = debounce_ms
        self.setObjectName("SearchSection")

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(self.debounce_ms)
        self._debounce_timer.timeout.connect(self._emit_search_changed)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.txt_search = QLineEdit()
        self.txt_search.setObjectName("SpotlightSearch")
        self.txt_search.setPlaceholderText(
            "Search commands, tools or syntax (e.g. 'curl', 'nmap', 'sql', 'suid', 'lfi')..."
        )
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self._on_text_changed)

        layout.addWidget(self.txt_search)

    def _on_text_changed(self, text: str) -> None:
        if self.debounce_ms <= 0:
            self._emit_search_changed()
        else:
            self._debounce_timer.start(self.debounce_ms)

    def _emit_search_changed(self) -> None:
        self.search_changed.emit(self.txt_search.text().strip())

    def set_focus(self) -> None:
        self.txt_search.setFocus()
        self.txt_search.selectAll()

    def clear(self) -> None:
        self._debounce_timer.stop()
        self.txt_search.clear()

    def text(self) -> str:
        return self.txt_search.text().strip()

    def get_text(self) -> str:
        return self.txt_search.text().strip()

from typing import Optional, List
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QLabel
from PyQt6.QtCore import Qt


class ContentPanel(QWidget):
    """
    Scrollable content panel hosting dynamic command cards, loot entries, history items,
    or empty state messages, along with the optional privacy warning banner.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ContentPanel")
        self._init_ui()

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # 1. Privacy Warning Banner for History Mode
        self.privacy_banner = QFrame()
        self.privacy_banner.setObjectName("PrivacyWarningBanner")
        banner_layout = QHBoxLayout(self.privacy_banner)
        banner_layout.setContentsMargins(10, 4, 10, 4)
        lbl_warn = QLabel(
            "Datenschutz-Hinweis: Kopierte Passwörter oder persönliche Daten werden protokolliert, "
            "solange REC aktiv ist (Pausieren mit Ctrl+P oder Klick auf REC: ON)."
        )
        lbl_warn.setTextFormat(Qt.TextFormat.PlainText)
        lbl_warn.setObjectName("PrivacyWarningText")
        lbl_warn.setWordWrap(True)
        banner_layout.addWidget(lbl_warn)
        self.privacy_banner.setVisible(False)
        outer_layout.addWidget(self.privacy_banner)

        # 2. Scrollable Content Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setObjectName("MainScrollArea")
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(12, 8, 12, 8)
        self.content_layout.setSpacing(6)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.content_container)
        outer_layout.addWidget(self.scroll_area, stretch=1)

    def get_layout(self) -> QVBoxLayout:
        return self.content_layout

    def clear_cards(self) -> None:
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def show_empty_state(self, message: str) -> None:
        empty_lbl = QLabel(message)
        empty_lbl.setTextFormat(Qt.TextFormat.PlainText)
        empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_lbl.setStyleSheet("color: #6e7681; font-size: 13px; font-style: italic; padding: 40px 20px;")
        empty_lbl.setWordWrap(True)
        self.content_layout.addWidget(empty_lbl)

    def set_privacy_banner_visible(self, visible: bool) -> None:
        self.privacy_banner.setVisible(visible)

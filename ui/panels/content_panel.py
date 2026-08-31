from typing import Optional, List
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QLabel
from PyQt6.QtCore import Qt
from core.i18n import t


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
        self.lbl_warn = QLabel(
            t(
                "privacy.warning",
                "Privacy Notice: Copied passwords or personal data are logged while REC is active "
                "(Pause with Ctrl+P or click REC: ON)."
            )
        )
        self.lbl_warn.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_warn.setObjectName("PrivacyWarningText")
        self.lbl_warn.setWordWrap(True)
        banner_layout.addWidget(self.lbl_warn)
        self.privacy_banner.setVisible(False)
        outer_layout.addWidget(self.privacy_banner)

        # 2. Scrollable Content Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setObjectName("MainScrollArea")

        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(12, 8, 12, 8)
        self.content_layout.setSpacing(6)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.content_container)
        # QScrollArea enables auto-fill on its viewport and hosted widget.
        # Disable both paint surfaces so the frameless window glass remains
        # visible without introducing a widget-local stylesheet.
        self.scroll_area.setAutoFillBackground(False)
        self.scroll_area.viewport().setAutoFillBackground(False)
        self.content_container.setAutoFillBackground(False)
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

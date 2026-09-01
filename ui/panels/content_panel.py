from typing import Optional, List
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QLabel
from PyQt6.QtCore import Qt, QTimer, QSize
from core.i18n import t


class ViewportBoundContent(QWidget):
    """Keep horizontal child hints from widening a resizable scroll widget."""

    def hasHeightForWidth(self) -> bool:
        # The nested card layouts already contribute their wrapped size hints.
        # Re-running the aggregate layout's heightForWidth calculation here
        # substantially double-counts wrapped command heights in QScrollArea.
        return False

    def heightForWidth(self, _width: int) -> int:
        return -1

    def _constrain_width(self, hint: QSize) -> QSize:
        ancestor = self.parentWidget()
        while ancestor is not None and not isinstance(ancestor, QScrollArea):
            ancestor = ancestor.parentWidget()
        if ancestor is not None:
            viewport_width = ancestor.viewport().width()
            if viewport_width > 0:
                hint.setWidth(min(hint.width(), viewport_width))
        return hint

    def sizeHint(self) -> QSize:
        return self._constrain_width(super().sizeHint())

    def minimumSizeHint(self) -> QSize:
        return self._constrain_width(super().minimumSizeHint())


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
        # Preserve the original render hierarchy used by the HUD glass effect.
        # The local transparent scroll-area surface allows the themed background
        # below the content zone to remain visible.
        self.scroll_area.setStyleSheet(
            "background: transparent; border: none;"
        )

        self.content_container = ViewportBoundContent()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(12, 8, 12, 8)
        self.content_layout.setSpacing(6)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.content_container)
        # QScrollArea enables auto-fill on its viewport and hosted widget.
        # Keep these paint surfaces disabled in addition to the historical
        # local scroll-area style so none of them obscures the glass layer.
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

    def refresh_content_geometry(self) -> None:
        """Recompute layout-derived scroll geometry after replacing view content."""
        self.content_layout.invalidate()
        self.content_container.updateGeometry()
        self.content_layout.activate()
        # Re-apply the layout-derived size so QScrollArea cannot retain a
        # previously larger hosted-widget height after wrapping/filter changes.
        self.content_container.adjustSize()

    def schedule_content_geometry_refresh(self) -> None:
        """Recalculate once more after wrapped labels receive their final width."""
        QTimer.singleShot(0, self.refresh_content_geometry)

    def show_empty_state(self, message: str) -> None:
        empty_lbl = QLabel(message)
        empty_lbl.setTextFormat(Qt.TextFormat.PlainText)
        empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_lbl.setStyleSheet("color: #6e7681; font-size: 13px; font-style: italic; padding: 40px 20px;")
        empty_lbl.setWordWrap(True)
        self.content_layout.addWidget(empty_lbl)

    def set_privacy_banner_visible(self, visible: bool) -> None:
        self.privacy_banner.setVisible(visible)

"""Presentation-only bulk action bar for Quick Note selection."""

from typing import Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from core.i18n import t
from ui.styles.icons import icon
from ui.styles.palette import CYBER_CYAN, TEXT_MUTED


class QuickNoteBulkBar(QFrame):
    """Render Quick Note bulk controls without owning selection state."""

    status_requested = pyqtSignal(str)
    delete_requested = pyqtSignal()
    deselect_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("QuickNoteBulkBar")
        self.setStyleSheet(
            "QFrame#QuickNoteBulkBar { background-color: rgba(0, 229, 255, 0.08); "
            "border: 1px solid rgba(0, 229, 255, 0.35); border-radius: 6px; } "
            "QPushButton { font-size: 11px; padding: 2px 8px; border-radius: 4px; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(6)

        self.lbl_selected = QLabel()
        self.lbl_selected.setStyleSheet(
            f"color: {CYBER_CYAN}; font-weight: bold; font-size: 11px;"
        )
        layout.addWidget(self.lbl_selected)

        lbl_mark = QLabel(t("quick_note.bulk_mark_as", "Mark:"))
        lbl_mark.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(lbl_mark)

        layout.addWidget(
            self._status_button("inbox", "fa5s.inbox", "quick_note.status_inbox_short", "Inbox ▾")
        )
        layout.addWidget(
            self._status_button(
                "followup",
                "fa5s.clock",
                "quick_note.status_followup_short",
                "Follow-up ▾",
            )
        )
        layout.addWidget(
            self._status_button(
                "resolved",
                "fa5s.check-circle",
                "quick_note.status_resolved_short",
                "Resolved ▾",
            )
        )
        layout.addStretch()

        btn_delete = self._button(
            t("quick_note.bulk_delete", "Delete Selected"),
            "fa5s.trash",
            "DangerBtn",
        )
        btn_delete.clicked.connect(self.delete_requested.emit)
        layout.addWidget(btn_delete)

        btn_deselect = self._button(
            t("quick_note.bulk_deselect", "Deselect"),
            "fa5s.times",
            "SecondaryBtn",
        )
        btn_deselect.clicked.connect(self.deselect_requested.emit)
        layout.addWidget(btn_deselect)

        self.set_selected_count(0)

    def _status_button(
        self,
        status: str,
        icon_name: str,
        translation_key: str,
        fallback: str,
    ) -> QPushButton:
        button = self._button(
            t(translation_key, fallback).removesuffix(" ▾"),
            icon_name,
            "SecondaryBtn",
        )
        button.clicked.connect(lambda: self.status_requested.emit(status))
        return button

    @staticmethod
    def _button(text: str, icon_name: str, style_class: str) -> QPushButton:
        button = QPushButton(text)
        button.setIcon(icon(icon_name))
        button.setIconSize(QSize(12, 12))
        button.setProperty("class", style_class)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def set_selected_count(self, count: int) -> None:
        self.lbl_selected.setText(
            t("quick_note.bulk_selected_count", "{count} selected").replace(
                "{count}", str(count)
            )
        )
        self.setVisible(count > 0)

"""Focused one-at-a-time review surface for Quick Notes."""

from typing import Any, Dict, Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.i18n import t
from core.phases import get_phase
from ui.styles.icons import icon


class QuickNoteFocusReview(QFrame):
    """Present a single review decision without surrounding stream noise."""

    promote_requested = pyqtSignal(dict)
    complete_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    next_requested = pyqtSignal()

    def __init__(
        self,
        entry: Dict[str, Any],
        position: int,
        total: int,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.entry = dict(entry)
        self.setObjectName("QuickNoteFocusReview")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        progress = QLabel(
            t("quick_note.review_progress", "{current} of {total}")
            .replace("{current}", str(position))
            .replace("{total}", str(total))
        )
        progress.setProperty("class", "QuickNoteReviewProgress")
        progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(progress)

        text = QLabel(self.entry.get("text", ""))
        text.setObjectName("QuickNoteReviewText")
        text.setTextFormat(Qt.TextFormat.MarkdownText)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(text, stretch=1)

        phase = get_phase(self.entry.get("category", "misc"))
        metadata = QLabel(
            "  ·  ".join(
                part
                for part in (str(self.entry.get("timestamp", "")).strip(), phase.short)
                if part
            )
        )
        metadata.setObjectName("QuickNoteMeta")
        metadata.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(metadata)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        loot = self._button(t("quick_note.send_loot", "Send to Loot"), "fa5s.archive")
        loot.clicked.connect(lambda: self.promote_requested.emit(self.entry))
        actions.addWidget(loot)
        complete = self._button(t("quick_note.review_complete", "Done"), "fa5s.check-circle")
        complete.setProperty("class", "PrimaryBtn")
        complete.clicked.connect(
            lambda: self.complete_requested.emit(self.entry.get("id", ""))
        )
        actions.addWidget(complete)
        delete = self._button(t("quick_note.review_delete", "Delete"), "fa5s.trash")
        delete.setProperty("class", "DangerBtn")
        delete.clicked.connect(lambda: self.delete_requested.emit(self.entry.get("id", "")))
        actions.addWidget(delete)
        next_button = self._button(t("quick_note.review_next", "Next"), "fa5s.arrow-right")
        next_button.clicked.connect(self.next_requested.emit)
        actions.addWidget(next_button)
        layout.addLayout(actions)

    @staticmethod
    def _button(text: str, icon_name: str) -> QPushButton:
        button = QPushButton(text)
        button.setIcon(icon(icon_name))
        button.setIconSize(QSize(14, 14))
        button.setProperty("class", "SecondaryBtn")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(36)
        return button


class QuickNoteReviewSummary(QFrame):
    """Keep the session outcome visible without gamified motion or decoration."""

    def __init__(self, completed: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("QuickNoteReviewSummary")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        label = QLabel(
            t("quick_note.review_summary", "{count} processed today").replace(
                "{count}", str(completed)
            )
        )
        label.setObjectName("QuickNoteReviewSummaryText")
        layout.addWidget(label)
        layout.addStretch()

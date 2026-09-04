"""
Dialog to edit a clipboard history entry (content text and target IP).
"""

from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
)
from PyQt6.QtGui import QKeySequence, QShortcut

from ui.base_dialog import BaseHudDialog
from core.i18n import t


class EditHistoryDialog(BaseHudDialog):
    """Lets the user edit a recorded clipboard history entry."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(
            title=t("history.edit_title", "SPECTRE // EDIT CLIPBOARD ENTRY"),
            parent=parent,
        )
        self.entry = dict(entry)
        self.setMinimumWidth(560)
        self.resize(600, 380)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = self.body_layout
        layout.setSpacing(10)

        # 1. Target IP Row (optional)
        lbl_target = QLabel(t("history.lbl_target", "Target IP (optional):"))
        lbl_target.setProperty("class", "FormLabel")
        layout.addWidget(lbl_target)

        self.txt_target = QLineEdit(self.entry.get("target_ip", ""))
        self.txt_target.setProperty("class", "FormInput")
        self.txt_target.setPlaceholderText("10.10.10.x")
        layout.addWidget(self.txt_target)

        # 2. Content Row
        lbl_content = QLabel(t("history.lbl_content", "Content:"))
        lbl_content.setProperty("class", "FormLabel")
        layout.addWidget(lbl_content)

        self.txt_content = QPlainTextEdit(self.entry.get("text", ""))
        self.txt_content.setProperty("class", "FormTextEdit")
        self.txt_content.setMinimumHeight(180)
        layout.addWidget(self.txt_content)

        # 3. Footer Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 8, 0, 0)

        lbl_hint = QLabel(t("history.edit_hint", "Ctrl+Enter: Save | Esc: Cancel"))
        lbl_hint.setStyleSheet("color: #8b949e; font-size: 11px;")
        btn_layout.addWidget(lbl_hint)

        btn_layout.addStretch()

        btn_cancel = QPushButton(t("dialog.cancel", "Cancel"))
        btn_cancel.setProperty("class", "SecondaryBtn")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        self.btn_save = QPushButton(t("dialog.save", "Save"))
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._on_save)
        self.txt_content.setFocus()

    def _on_save(self) -> None:
        text = self.txt_content.toPlainText().strip()
        if text:
            self.accept()

    def get_data(self) -> Dict[str, str]:
        """Returns the edited entry payload."""
        return {
            "text": self.txt_content.toPlainText().strip(),
            "target_ip": self.txt_target.text().strip(),
        }

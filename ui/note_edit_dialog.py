"""
Dialog to edit a quick note entry (text, pentest phase, target IP, and status).
"""

from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QComboBox,
)
from PyQt6.QtGui import QKeySequence, QShortcut

from ui.base_dialog import BaseHudDialog
from core.loot.manager import VALID_CATEGORY_IDS
from core.i18n import t

NOTE_PHASES = [
    ("recon", "1. Recon"),
    ("access", "2. Access"),
    ("privesc", "3. PrivEsc"),
    ("postex", "4. PostEx"),
    ("scripts", "5. Scripts"),
    ("misc", "6. Misc"),
]

STATUS_OPTIONS = [
    ("inbox", "📥 Inbox"),
    ("followup", "⏳ Follow-up"),
    ("resolved", "✓ Resolved"),
]


class EditNoteDialog(BaseHudDialog):
    """Dialog to view and adjust all fields of a quick note."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(
            title=t("note_dialog.title_edit", "SPECTRE // EDIT NOTE"),
            parent=parent,
        )
        self.entry = dict(entry)
        self.setMinimumWidth(560)
        self.resize(600, 440)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = self.body_layout
        layout.setSpacing(10)

        # 1. Category & Status Row (Side-by-side)
        row_top = QHBoxLayout()
        row_top.setSpacing(10)

        # Category
        col_cat = QVBoxLayout()
        col_cat.setSpacing(4)
        lbl_cat = QLabel(t("note_dialog.lbl_phase", "Pentest Phase:"))
        lbl_cat.setProperty("class", "FormLabel")
        col_cat.addWidget(lbl_cat)

        self.combo_cat = QComboBox()
        self.combo_cat.setProperty("class", "FormInput")
        current_cat = str(self.entry.get("category", "misc")).lower()
        active_cat_idx = 0
        for i, (cat_id, label) in enumerate(NOTE_PHASES):
            self.combo_cat.addItem(label, cat_id)
            if cat_id == current_cat:
                active_cat_idx = i
        self.combo_cat.setCurrentIndex(active_cat_idx)
        col_cat.addWidget(self.combo_cat)
        row_top.addLayout(col_cat, stretch=1)

        # Status
        col_status = QVBoxLayout()
        col_status.setSpacing(4)
        lbl_status = QLabel(t("note_dialog.lbl_status", "Status:"))
        lbl_status.setProperty("class", "FormLabel")
        col_status.addWidget(lbl_status)

        self.combo_status = QComboBox()
        self.combo_status.setProperty("class", "FormInput")
        current_status = str(self.entry.get("status", "inbox")).lower()
        active_status_idx = 0
        for i, (st_id, label) in enumerate(STATUS_OPTIONS):
            self.combo_status.addItem(label, st_id)
            if st_id == current_status:
                active_status_idx = i
        self.combo_status.setCurrentIndex(active_status_idx)
        col_status.addWidget(self.combo_status)
        row_top.addLayout(col_status, stretch=1)

        layout.addLayout(row_top)

        # 2. Target IP Row (optional)
        lbl_target = QLabel(t("note_dialog.lbl_target", "Target IP (optional):"))
        lbl_target.setProperty("class", "FormLabel")
        layout.addWidget(lbl_target)

        self.txt_target = QLineEdit(str(self.entry.get("target_ip", "")))
        self.txt_target.setProperty("class", "FormInput")
        self.txt_target.setPlaceholderText("10.10.10.x")
        layout.addWidget(self.txt_target)

        # 3. Note Text
        lbl_text = QLabel(t("note_dialog.lbl_text", "Note Text:"))
        lbl_text.setProperty("class", "FormLabel")
        layout.addWidget(lbl_text)

        self.txt_text = QPlainTextEdit(str(self.entry.get("text", "")))
        self.txt_text.setProperty("class", "FormTextEdit")
        self.txt_text.setMinimumHeight(180)
        layout.addWidget(self.txt_text)

        # 4. Footer Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 8, 0, 0)

        lbl_hint = QLabel(t("note_dialog.edit_hint", "Ctrl+Enter: Save | Esc: Cancel"))
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
        self.txt_text.setFocus()

    def _on_save(self) -> None:
        text = self.txt_text.toPlainText().strip()
        if text:
            self.accept()

    def get_data(self) -> Dict[str, Any]:
        """Returns edited quick note data."""
        cat_data = self.combo_cat.currentData()
        status_data = self.combo_status.currentData()
        return {
            "text": self.txt_text.toPlainText().strip(),
            "category": cat_data if cat_data in VALID_CATEGORY_IDS else "misc",
            "status": status_data or "inbox",
            "target_ip": self.txt_target.text().strip(),
        }

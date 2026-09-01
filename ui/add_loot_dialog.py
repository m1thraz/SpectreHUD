from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QComboBox,
    QWidget,
    QMessageBox,
)
from typing import Dict, Any, Optional
from core.loot_manager import LOOT_TYPES, CATEGORIES
from core.i18n import t
from ui.base_dialog import BaseHudDialog


class AddLootDialog(BaseHudDialog):
    """Dialog to capture new or edit existing session loot (credentials, hashes, flags, notes, PoCs)."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        target_ip: str = "",
        current_target_ip: str = "",
        default_type: str = "note",
        initial_type: str = "note",
        entry_type: str = "note",
        default_category: str = "misc",
        initial_category: str = "misc",
        category: str = "misc",
        default_title: str = "",
        initial_title: str = "",
        title: str = "",
        default_content: str = "",
        initial_content: str = "",
        content: str = "",
        entry_id: Optional[str] = None,
        is_edit: bool = False,
        **kwargs,
    ):
        self.entry_id = entry_id or kwargs.get("id")
        self.is_edit = is_edit or bool(self.entry_id)
        dialog_title = t(
            "loot_dialog.title_edit" if self.is_edit else "loot_dialog.title_new",
            "SPECTRE // EDIT SESSION LOOT" if self.is_edit else "SPECTRE // CAPTURE SESSION LOOT",
        )

        super().__init__(title=dialog_title, parent=parent)
        self.setMinimumWidth(540)
        self.resize(560, 460)

        self.current_target_ip = target_ip or current_target_ip or kwargs.get("target", "")
        self.initial_type = default_type or initial_type or entry_type or kwargs.get("type", "note")
        self.initial_category = (
            default_category or initial_category or category or kwargs.get("cat", "misc")
        )
        self.initial_severity = (
            kwargs.get("default_severity")
            or kwargs.get("initial_severity")
            or kwargs.get("severity")
            or "info"
        )
        self.initial_title = default_title or initial_title or title or kwargs.get("name", "")
        self.initial_content = (
            default_content or initial_content or content or kwargs.get("text", "")
        )

        self._init_form()

    def _init_form(self) -> None:
        layout = self.body_layout

        # 1. Type, Severity, and Category Selection (Side by Side)
        select_row = QHBoxLayout()
        select_row.setSpacing(10)

        # 1a. Type
        type_col = QVBoxLayout()
        type_col.setSpacing(4)
        lbl_type = QLabel(t("loot_dialog.lbl_type", "Entry Type:"))
        lbl_type.setProperty("class", "FormLabel")
        type_col.addWidget(lbl_type)

        self.combo_type = QComboBox()
        for i, loot_type in enumerate(LOOT_TYPES):
            self.combo_type.addItem(loot_type["name"], loot_type["id"])
            if loot_type["id"] == self.initial_type:
                self.combo_type.setCurrentIndex(i)
        type_col.addWidget(self.combo_type)
        select_row.addLayout(type_col, stretch=1)

        # 1b. Severity / Schweregrad
        sev_col = QVBoxLayout()
        sev_col.setSpacing(4)
        lbl_sev = QLabel(t("loot_dialog.lbl_severity", "Severity:"))
        lbl_sev.setProperty("class", "FormLabel")
        sev_col.addWidget(lbl_sev)

        self.combo_severity = QComboBox()
        severities = [
            ("🔵 Info", "info"),
            ("🟢 Low", "low"),
            ("🟡 Medium", "medium"),
            ("🟠 High", "high"),
            ("🔴 Critical", "critical"),
        ]
        for i, (s_label, s_id) in enumerate(severities):
            self.combo_severity.addItem(s_label, s_id)
            if s_id == self.initial_severity.lower():
                self.combo_severity.setCurrentIndex(i)
        sev_col.addWidget(self.combo_severity)
        select_row.addLayout(sev_col, stretch=1)

        # 1c. Pentest Category
        cat_col = QVBoxLayout()
        cat_col.setSpacing(4)
        lbl_cat = QLabel(t("loot_dialog.lbl_category", "Pentest Phase / Category:"))
        lbl_cat.setProperty("class", "FormLabel")
        cat_col.addWidget(lbl_cat)

        self.combo_category = QComboBox()
        for i, c in enumerate(sorted(CATEGORIES, key=lambda x: x["order"])):
            self.combo_category.addItem(c["name"], c["id"])
            if c["id"] == self.initial_category:
                self.combo_category.setCurrentIndex(i)
        cat_col.addWidget(self.combo_category)
        select_row.addLayout(cat_col, stretch=2)

        layout.addLayout(select_row)

        # 2. Title
        lbl_title = QLabel(t("loot_dialog.lbl_name", "Title / Identifier:"))
        lbl_title.setProperty("class", "FormLabel")
        layout.addWidget(lbl_title)

        self.txt_title = QLineEdit(self.initial_title)
        self.txt_title.setPlaceholderText(
            t("loot_dialog.ph_name", "e.g. SSH Key user 'alice', MySQL Root Password, user.txt")
        )
        layout.addWidget(self.txt_title)

        # 3. Content / Value
        lbl_content = QLabel(
            t("loot_dialog.lbl_content", "Content / Password / Hash / Flag / Note:")
        )
        lbl_content.setProperty("class", "FormLabel")
        layout.addWidget(lbl_content)

        self.txt_content = QPlainTextEdit()
        self.txt_content.setObjectName("CommandBox")
        self.txt_content.setPlainText(self.initial_content)
        self.txt_content.setPlaceholderText(
            t("loot_dialog.ph_content", "e.g. admin:SuperSecretPass! or THM{fl4g_h3r3}")
        )
        self.txt_content.setFixedHeight(100)
        layout.addWidget(self.txt_content)

        # 4. Target IP
        lbl_target = QLabel(t("loot_dialog.lbl_target", "Associated Target (optional):"))
        lbl_target.setProperty("class", "FormLabel")
        layout.addWidget(lbl_target)

        self.txt_target = QLineEdit(self.current_target_ip)
        self.txt_target.setPlaceholderText("10.10.10.x")
        layout.addWidget(self.txt_target)

        # 5. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        lbl_hint = QLabel(t("loot_dialog.btn_hint", "↵ Enter: Save | Esc: Cancel"))
        lbl_hint.setStyleSheet("color: #6e7681; font-size: 11px;")
        btn_layout.addWidget(lbl_hint)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton(t("dialog.cancel", "Cancel"))
        self.btn_cancel.setProperty("class", "SecondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        save_label = t("dialog.update", "Update") if self.is_edit else t("dialog.save", "Save")
        self.btn_save = QPushButton(save_label)
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _on_save(self) -> None:
        if not self.txt_title.text().strip():
            QMessageBox.warning(
                self,
                t("dialog.error", "Error"),
                t("loot_dialog.err_title", "Please enter a title for the loot entry."),
            )
            return
        if not self.txt_content.toPlainText().strip():
            QMessageBox.warning(
                self,
                t("dialog.error", "Error"),
                t("loot_dialog.err_content", "Please enter the content / value."),
            )
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        data = {
            "type": self.combo_type.currentData(),
            "severity": self.combo_severity.currentData(),
            "category": self.combo_category.currentData(),
            "title": self.txt_title.text().strip(),
            "content": self.txt_content.toPlainText().strip(),
            "target_ip": self.txt_target.text().strip(),
        }
        if self.entry_id:
            data["id"] = self.entry_id
        return data

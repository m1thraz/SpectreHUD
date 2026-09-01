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
from typing import List, Dict, Any, Optional
from core.i18n import t
from ui.base_dialog import BaseHudDialog


class AddSnippetDialog(BaseHudDialog):
    """Dialog to create and save a new custom snippet with template variables."""

    def __init__(self, existing_categories: List[Dict[str, Any]], parent: Optional[QWidget] = None):
        super().__init__(
            title=t("snippet_dialog.title", "SPECTRE // ADD NEW COMMAND"), parent=parent
        )
        self.setMinimumWidth(540)
        self.resize(560, 480)
        self.existing_categories = existing_categories
        self._init_form()

    def _init_form(self) -> None:
        layout = self.body_layout

        # Title
        lbl_title = QLabel(t("snippet_dialog.lbl_title", "Title / Command Name:"))
        lbl_title.setProperty("class", "FormLabel")
        layout.addWidget(lbl_title)

        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText(
            t("snippet_dialog.ph_title", "e.g. Nmap UDP Scan with Scripts")
        )
        layout.addWidget(self.txt_title)

        # Row with Category & Subcategory
        cat_row = QHBoxLayout()
        cat_row.setSpacing(12)

        # Category
        cat_col = QVBoxLayout()
        cat_col.setSpacing(4)
        lbl_cat = QLabel(t("snippet_dialog.lbl_category", "Category:"))
        lbl_cat.setProperty("class", "FormLabel")
        cat_col.addWidget(lbl_cat)

        self.combo_category = QComboBox()
        for cat in self.existing_categories:
            if cat.get("id") != "all":
                self.combo_category.addItem(cat.get("name"), cat.get("id"))
        self.combo_category.addItem("Custom Notes & Snippets", "custom_snippets")
        cat_col.addWidget(self.combo_category)
        cat_row.addLayout(cat_col, stretch=1)

        # Subcategory
        subcat_col = QVBoxLayout()
        subcat_col.setSpacing(4)
        lbl_subcat = QLabel(t("snippet_dialog.lbl_subcategory", "Subcategory / Group:"))
        lbl_subcat.setProperty("class", "FormLabel")
        subcat_col.addWidget(lbl_subcat)

        self.txt_subcategory = QLineEdit()
        self.txt_subcategory.setPlaceholderText(
            t("snippet_dialog.ph_subcategory", "e.g. Port Scanning or Web Recon")
        )
        subcat_col.addWidget(self.txt_subcategory)
        cat_row.addLayout(subcat_col, stretch=1)

        layout.addLayout(cat_row)

        # Template Command
        lbl_tmpl = QLabel(
            t(
                "snippet_dialog.lbl_template",
                "Command / Template (supports {{TARGET_IP}}, {{ATTACKER_IP}}, {{PORT}}, {{WORDLIST}}):",
            )
        )
        lbl_tmpl.setProperty("class", "FormLabel")
        layout.addWidget(lbl_tmpl)

        self.txt_template = QPlainTextEdit()
        self.txt_template.setObjectName("CommandBox")
        self.txt_template.setPlaceholderText(
            t("snippet_dialog.ph_template", "e.g. nmap -sU -p {{PORT}} {{TARGET_IP}}")
        )
        self.txt_template.setFixedHeight(85)
        layout.addWidget(self.txt_template)

        # Description
        lbl_desc = QLabel(t("snippet_dialog.lbl_desc", "Optional Description / Note:"))
        lbl_desc.setProperty("class", "FormLabel")
        layout.addWidget(lbl_desc)

        self.txt_description = QLineEdit()
        self.txt_description.setPlaceholderText(
            t("snippet_dialog.ph_desc", "e.g. Scans UDP port with version detection")
        )
        layout.addWidget(self.txt_description)

        # Tags
        lbl_tags = QLabel(t("snippet_dialog.lbl_tags", "Tags (comma separated):"))
        lbl_tags.setProperty("class", "FormLabel")
        layout.addWidget(lbl_tags)

        self.txt_tags = QLineEdit()
        self.txt_tags.setPlaceholderText(t("snippet_dialog.ph_tags", "e.g. nmap, udp, recon"))
        layout.addWidget(self.txt_tags)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        lbl_hint = QLabel(t("snippet_dialog.btn_hint", "↵ Enter: Save | Esc: Cancel"))
        lbl_hint.setStyleSheet("color: #6e7681; font-size: 11px;")
        btn_layout.addWidget(lbl_hint)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton(t("dialog.cancel", "Cancel"))
        self.btn_cancel.setProperty("class", "SecondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(t("dialog.save", "Save"))
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _on_save(self) -> None:
        if not self.txt_title.text().strip():
            QMessageBox.warning(
                self,
                t("dialog.error", "Error"),
                t("snippet_dialog.err_title", "Please enter a title for the command."),
            )
            return
        if not self.txt_template.toPlainText().strip():
            QMessageBox.warning(
                self,
                t("dialog.error", "Error"),
                t("snippet_dialog.err_template", "Please enter the template command."),
            )
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        tags_raw = self.txt_tags.text().split(",")
        tags = [t_item.strip().lower() for t_item in tags_raw if t_item.strip()]
        return {
            "title": self.txt_title.text().strip(),
            "category": self.combo_category.currentText(),
            "category_id": self.combo_category.currentData(),
            "subcategory": self.txt_subcategory.text().strip() or "Allgemein",
            "template": self.txt_template.toPlainText().strip(),
            "description": self.txt_description.text().strip(),
            "tags": tags,
        }

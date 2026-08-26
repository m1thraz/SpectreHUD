from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPlainTextEdit, QPushButton, QComboBox, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt
from typing import List, Dict, Any, Optional
from ui.base_dialog import BaseHudDialog

class AddSnippetDialog(BaseHudDialog):
    """Dialog to create and save a new custom snippet with template variables."""

    def __init__(self, existing_categories: List[Dict[str, Any]], parent: Optional[QWidget] = None):
        super().__init__(title="SPECTRE // NEUEN BEFEHL HINZUFÜGEN", parent=parent)
        self.setMinimumWidth(540)
        self.resize(560, 480)
        self.existing_categories = existing_categories
        self._init_form()

    def _init_form(self) -> None:
        layout = self.body_layout

        # Title
        lbl_title = QLabel("Titel / Name des Befehls:")
        lbl_title.setProperty("class", "FormLabel")
        layout.addWidget(lbl_title)

        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("z.B. Nmap UDP Scan mit Skripten")
        layout.addWidget(self.txt_title)

        # Row with Category & Subcategory
        cat_row = QHBoxLayout()
        cat_row.setSpacing(12)

        # Category
        cat_col = QVBoxLayout()
        cat_col.setSpacing(4)
        lbl_cat = QLabel("Kategorie:")
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
        lbl_subcat = QLabel("Unterkategorie / Gruppe:")
        lbl_subcat.setProperty("class", "FormLabel")
        subcat_col.addWidget(lbl_subcat)

        self.txt_subcategory = QLineEdit()
        self.txt_subcategory.setPlaceholderText("z.B. Port Scanning oder Web Recon")
        subcat_col.addWidget(self.txt_subcategory)
        cat_row.addLayout(subcat_col, stretch=1)

        layout.addLayout(cat_row)

        # Template Command
        lbl_tmpl = QLabel("Befehl / Template (unterstützt {{TARGET_IP}}, {{ATTACKER_IP}}, {{PORT}}, {{WORDLIST}}):")
        lbl_tmpl.setProperty("class", "FormLabel")
        layout.addWidget(lbl_tmpl)

        self.txt_template = QPlainTextEdit()
        self.txt_template.setObjectName("CommandBox")
        self.txt_template.setPlaceholderText("z.B. nmap -sU -p {{PORT}} {{TARGET_IP}}")
        self.txt_template.setFixedHeight(85)
        layout.addWidget(self.txt_template)

        # Description
        lbl_desc = QLabel("Optionale Beschreibung / Notiz:")
        lbl_desc.setProperty("class", "FormLabel")
        layout.addWidget(lbl_desc)

        self.txt_description = QLineEdit()
        self.txt_description.setPlaceholderText("z.B. Scannt UDP-Port mit Versionserkennung")
        layout.addWidget(self.txt_description)

        # Tags
        lbl_tags = QLabel("Tags (durch Komma getrennt):")
        lbl_tags.setProperty("class", "FormLabel")
        layout.addWidget(lbl_tags)

        self.txt_tags = QLineEdit()
        self.txt_tags.setPlaceholderText("z.B. nmap, udp, recon")
        layout.addWidget(self.txt_tags)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        lbl_hint = QLabel("↵ Enter: Speichern | Esc: Abbrechen")
        lbl_hint.setStyleSheet("color: #6e7681; font-size: 11px;")
        btn_layout.addWidget(lbl_hint)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setProperty("class", "SecondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Speichern")
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _on_save(self) -> None:
        if not self.txt_title.text().strip():
            QMessageBox.warning(self, "Fehler", "Bitte gib einen Titel für den Befehl ein.")
            return
        if not self.txt_template.toPlainText().strip():
            QMessageBox.warning(self, "Fehler", "Bitte gib den auszuführenden Befehl ein.")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        tags_raw = self.txt_tags.text().split(",")
        tags = [t.strip().lower() for t in tags_raw if t.strip()]
        return {
            "title": self.txt_title.text().strip(),
            "category": self.combo_category.currentText(),
            "category_id": self.combo_category.currentData(),
            "subcategory": self.txt_subcategory.text().strip() or "Allgemein",
            "template": self.txt_template.toPlainText().strip(),
            "description": self.txt_description.text().strip(),
            "tags": tags
        }

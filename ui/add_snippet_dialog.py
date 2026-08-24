from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPlainTextEdit, QPushButton, QComboBox, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt
from typing import List, Dict, Any, Optional

class AddSnippetDialog(QDialog):
    """Dialog to create and save a new custom snippet with template variables."""

    def __init__(self, existing_categories: List[Dict[str, Any]], parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Neuen CTF / CLI Befehl hinzufügen")
        self.setMinimumWidth(500)
        self.setMinimumHeight(450)
        self.existing_categories = existing_categories
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Title
        layout.addWidget(QLabel("Titel / Name des Befehls:"))
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("z.B. Nmap UDP Scan mit Skripten")
        layout.addWidget(self.txt_title)

        # Category selection
        layout.addWidget(QLabel("Kategorie:"))
        self.combo_category = QComboBox()
        for cat in self.existing_categories:
            if cat.get("id") != "all":
                self.combo_category.addItem(cat.get("name"), cat.get("id"))
        self.combo_category.addItem("⭐ Eigene Notizen & Custom", "custom_snippets")
        layout.addWidget(self.combo_category)

        # Subcategory
        layout.addWidget(QLabel("Unterkategorie / Gruppe:"))
        self.txt_subcategory = QLineEdit()
        self.txt_subcategory.setPlaceholderText("z.B. Port Scanning oder Web Recon")
        layout.addWidget(self.txt_subcategory)

        # Template Command
        layout.addWidget(QLabel("Befehl / Template (unterstützt {{TARGET_IP}}, {{ATTACKER_IP}}, {{PORT}}, {{WORDLIST}}):"))
        self.txt_template = QPlainTextEdit()
        self.txt_template.setPlaceholderText("z.B. nmap -sU -p {{PORT}} {{TARGET_IP}}")
        self.txt_template.setFixedHeight(90)
        layout.addWidget(self.txt_template)

        # Description
        layout.addWidget(QLabel("Optionale Beschreibung / Notiz:"))
        self.txt_description = QLineEdit()
        self.txt_description.setPlaceholderText("z.B. Scannt UDP-Port mit Versionserkennung")
        layout.addWidget(self.txt_description)

        # Tags
        layout.addWidget(QLabel("Tags (durch Komma getrennt):"))
        self.txt_tags = QLineEdit()
        self.txt_tags.setPlaceholderText("z.B. nmap, udp, recon")
        layout.addWidget(self.txt_tags)

        # Buttons
        btn_layout = QHBoxLayout()
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

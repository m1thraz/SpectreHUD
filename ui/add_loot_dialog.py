from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPlainTextEdit, QPushButton, QComboBox, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt
from typing import Dict, Any
from core.loot_manager import LOOT_TYPES

class AddLootDialog(QDialog):
    """Dialog to quickly capture new credentials, hashes, flags or notes."""

    def __init__(self, current_target_ip: str = "", initial_content: str = "", initial_title: str = "", initial_type: str = "note", parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("📝 Neuen Session-Loot erfassen")
        self.setMinimumWidth(480)
        self.setMinimumHeight(380)
        self.current_target_ip = current_target_ip
        self.initial_content = initial_content
        self.initial_title = initial_title
        self.initial_type = initial_type
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # 1. Type Selection
        layout.addWidget(QLabel("Typ des Eintrags:"))
        self.combo_type = QComboBox()
        for i, t in enumerate(LOOT_TYPES):
            self.combo_type.addItem(f"{t['icon']} {t['name']}", t['id'])
            if t['id'] == self.initial_type:
                self.combo_type.setCurrentIndex(i)
        layout.addWidget(self.combo_type)

        # 2. Title
        layout.addWidget(QLabel("Titel / Bezeichner:"))
        self.txt_title = QLineEdit(self.initial_title)
        self.txt_title.setPlaceholderText("z.B. SSH Key user 'alice', MySQL Root Password, user.txt")
        layout.addWidget(self.txt_title)

        # 3. Content / Value
        layout.addWidget(QLabel("Inhalt / Passwort / Hash / Flag / Notiz:"))
        self.txt_content = QPlainTextEdit()
        self.txt_content.setPlainText(self.initial_content)
        self.txt_content.setPlaceholderText("z.B. admin:SuperSecretPass! oder THM{fl4g_h3r3}")
        self.txt_content.setFixedHeight(110)
        layout.addWidget(self.txt_content)

        # 4. Target IP
        layout.addWidget(QLabel("Zugehöriges Target (optional):"))
        self.txt_target = QLineEdit(self.current_target_ip)
        self.txt_target.setPlaceholderText("10.10.10.x")
        layout.addWidget(self.txt_target)

        # 5. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setProperty("class", "SecondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("💾 Speichern")
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _on_save(self) -> None:
        if not self.txt_title.text().strip():
            QMessageBox.warning(self, "Fehler", "Bitte gib einen Titel für den Eintrag ein.")
            return
        if not self.txt_content.toPlainText().strip():
            QMessageBox.warning(self, "Fehler", "Bitte gib den Inhalt / Wert ein.")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "type": self.combo_type.currentData(),
            "title": self.txt_title.text().strip(),
            "content": self.txt_content.toPlainText().strip(),
            "target_ip": self.txt_target.text().strip()
        }

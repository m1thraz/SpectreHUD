from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt
from typing import Dict, Any
from ui.styles import CYBER_DARK_QSS

class NewProjectDialog(QDialog):
    """Dialog to create a new isolated CTF / Pentest project workspace."""

    def __init__(self, default_attacker_ip: str = "10.10.14.5", parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("📁 Neues CTF-Projekt / Box anlegen")
        self.setMinimumWidth(440)
        self.resize(460, 260)
        self.default_attacker_ip = default_attacker_ip
        self.setStyleSheet(CYBER_DARK_QSS)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # Header Title
        lbl_header = QLabel("📁 Neues Projekt / Box initialisieren:")
        lbl_header.setStyleSheet("color: #00e5ff; font-size: 14px; font-weight: bold;")
        layout.addWidget(lbl_header)

        # Project Name
        lbl_name = QLabel("Projekt- / Box-Name:")
        lbl_name.setStyleSheet("color: #c9d1d9; font-weight: 600; font-size: 12px;")
        layout.addWidget(lbl_name)

        self.txt_name = QLineEdit()
        self.txt_name.setObjectName("SpotlightSearch")
        self.txt_name.setPlaceholderText("z. B. PickleRick, Blue, Lame, InternalAudit...")
        layout.addWidget(self.txt_name)

        # Target IP
        lbl_ip = QLabel("Target IP:")
        lbl_ip.setStyleSheet("color: #c9d1d9; font-weight: 600; font-size: 12px;")
        layout.addWidget(lbl_ip)

        self.txt_target = QLineEdit()
        self.txt_target.setObjectName("SpotlightSearch")
        self.txt_target.setPlaceholderText("z. B. 10.10.10.80")
        layout.addWidget(self.txt_target)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        lbl_hint = QLabel("↵ Enter: Anlegen | Esc: Abbrechen")
        lbl_hint.setStyleSheet("color: #6e7681; font-size: 11px;")
        btn_layout.addWidget(lbl_hint)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setProperty("class", "SecondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_create = QPushButton("📁 Projekt erstellen")
        self.btn_create.setProperty("class", "PrimaryBtn")
        self.btn_create.clicked.connect(self._on_create)
        btn_layout.addWidget(self.btn_create)

        layout.addLayout(btn_layout)

    def _on_create(self) -> None:
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Fehler", "Bitte gib einen Namen für das Projekt / die Box ein.")
            return
        self.accept()

    def get_data(self) -> Dict[str, str]:
        return {
            "name": self.txt_name.text().strip(),
            "target_ip": self.txt_target.text().strip(),
            "attacker_ip": self.default_attacker_ip
        }

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPlainTextEdit, QPushButton, QComboBox, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt
from typing import Dict, Any, Optional
from core.loot_manager import LOOT_TYPES, CATEGORIES
from ui.styles import CYBER_DARK_QSS

class AddLootDialog(QDialog):
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
        **kwargs
    ):
        super().__init__(parent)
        self.entry_id = entry_id or kwargs.get("id")
        self.is_edit = is_edit or bool(self.entry_id)

        self.setWindowTitle("✏️ Session-Loot bearbeiten" if self.is_edit else "📝 Neuen Session-Loot erfassen")
        self.setMinimumWidth(500)
        self.setMinimumHeight(420)
        
        self.current_target_ip = target_ip or current_target_ip or kwargs.get("target", "")
        self.initial_type = default_type or initial_type or entry_type or kwargs.get("type", "note")
        self.initial_category = default_category or initial_category or category or kwargs.get("cat", "misc")
        self.initial_title = default_title or initial_title or title or kwargs.get("name", "")
        self.initial_content = default_content or initial_content or content or kwargs.get("text", "")
        
        self.setStyleSheet(CYBER_DARK_QSS)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # 1. Type and Category Selection (Side by Side)
        select_row = QHBoxLayout()
        select_row.setSpacing(12)

        # 1a. Type
        type_col = QVBoxLayout()
        type_col.setSpacing(4)
        type_col.addWidget(QLabel("Typ des Eintrags:"))
        self.combo_type = QComboBox()
        for i, t in enumerate(LOOT_TYPES):
            self.combo_type.addItem(f"{t['icon']} {t['name']}", t['id'])
            if t['id'] == self.initial_type:
                self.combo_type.setCurrentIndex(i)
        type_col.addWidget(self.combo_type)
        select_row.addLayout(type_col, stretch=1)

        # 1b. Pentest Category
        cat_col = QVBoxLayout()
        cat_col.setSpacing(4)
        cat_col.addWidget(QLabel("Pentest-Phase / Kategorie:"))
        self.combo_category = QComboBox()
        for i, c in enumerate(sorted(CATEGORIES, key=lambda x: x["order"])):
            self.combo_category.addItem(f"{c['icon']} {c['name']}", c['id'])
            if c['id'] == self.initial_category:
                self.combo_category.setCurrentIndex(i)
        cat_col.addWidget(self.combo_category)
        select_row.addLayout(cat_col, stretch=1)

        layout.addLayout(select_row)

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

        save_label = "💾 Aktualisieren" if self.is_edit else "💾 Speichern"
        self.btn_save = QPushButton(save_label)
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
        data = {
            "type": self.combo_type.currentData(),
            "category": self.combo_category.currentData(),
            "title": self.txt_title.text().strip(),
            "content": self.txt_content.toPlainText().strip(),
            "target_ip": self.txt_target.text().strip()
        }
        if self.entry_id:
            data["id"] = self.entry_id
        return data

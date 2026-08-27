from pathlib import Path
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QWidget, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt
from typing import Dict, Any, Optional
from core.project_manager import get_default_projects_dir
from ui.base_dialog import BaseHudDialog

class NewProjectDialog(BaseHudDialog):
    """Dialog to create a new isolated CTF / Pentest project workspace with custom folder selection."""

    def __init__(
        self, 
        parent: Optional[QWidget] = None, 
        default_name: str = "",
        default_target: str = "",
        default_attacker: str = "10.10.14.5",
        default_port: str = "4444",
        default_base_dir: Optional[Path] = None,
        project_manager: Optional[Any] = None,
        **kwargs
    ):
        super().__init__(title="SPECTRE // NEUES PROJEKT / BOX ERSTELLEN", parent=parent)
        self.setMinimumWidth(520)
        self.resize(540, 380)
        
        self.project_manager = project_manager
        self.default_name = default_name or kwargs.get("name", "")
        self.default_target = default_target or kwargs.get("target_ip", "")
        self.default_attacker = default_attacker or kwargs.get("attacker_ip", "10.10.14.5")
        self.default_port = default_port or kwargs.get("port", "4444")
        self.base_projects_dir = Path(default_base_dir) if default_base_dir else get_default_projects_dir()
        
        self._init_form()

    def _init_form(self) -> None:
        layout = self.body_layout

        # 1. Project Name
        lbl_name = QLabel("Projekt- / Box-Name:")
        lbl_name.setProperty("class", "FormLabel")
        layout.addWidget(lbl_name)

        self.txt_name = QLineEdit(self.default_name)
        self.txt_name.setPlaceholderText("z. B. PickleRick, Blue, Lame, InternalAudit...")
        self.txt_name.textChanged.connect(self._update_path_preview)
        layout.addWidget(self.txt_name)

        # 2. Target IP
        lbl_ip = QLabel("Target IP:")
        lbl_ip.setProperty("class", "FormLabel")
        layout.addWidget(lbl_ip)

        self.txt_target = QLineEdit(self.default_target)
        self.txt_target.setPlaceholderText("z. B. 10.10.10.80")
        layout.addWidget(self.txt_target)

        # 3. Base Directory / Location
        lbl_dir = QLabel("Basis-Verzeichnis für Projekte:")
        lbl_dir.setProperty("class", "FormLabel")
        layout.addWidget(lbl_dir)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)

        self.txt_dir = QLineEdit(str(self.base_projects_dir))
        self.txt_dir.setPlaceholderText("Pfad zum Workspace-Ordner...")
        self.txt_dir.textChanged.connect(self._update_path_preview)
        dir_row.addWidget(self.txt_dir, stretch=1)

        self.btn_browse = QPushButton("Durchsuchen...")
        self.btn_browse.setProperty("class", "BrowseBtn")
        self.btn_browse.clicked.connect(self._on_browse_directory)
        dir_row.addWidget(self.btn_browse)

        layout.addLayout(dir_row)

        # 4. Target Directory Preview
        self.lbl_path_preview = QLabel(f"Zielpfad: {self.base_projects_dir / (self.default_name or 'Projektname')}")
        self.lbl_path_preview.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_path_preview.setStyleSheet("color: #6e7681; font-size: 11px; font-family: monospace;")
        layout.addWidget(self.lbl_path_preview)

        # 5. Buttons
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

        self.btn_create = QPushButton("Projekt erstellen")
        self.btn_create.setProperty("class", "PrimaryBtn")
        self.btn_create.clicked.connect(self._on_create)
        btn_layout.addWidget(self.btn_create)

        layout.addLayout(btn_layout)

    def _on_browse_directory(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, 
            "Basis-Verzeichnis für Projekte auswählen", 
            self.txt_dir.text().strip() or str(self.base_projects_dir)
        )
        if chosen:
            self.txt_dir.setText(chosen)

    def _update_path_preview(self) -> None:
        raw_name = self.txt_name.text().strip()
        base = Path(self.txt_dir.text().strip() or str(self.base_projects_dir))
        clean_name = self.project_manager._sanitize_name(raw_name) if self.project_manager else raw_name.replace(" ", "_")
        target_path = base / (clean_name or "Projektname")

        exists = False
        if self.project_manager and raw_name:
            exists = self.project_manager.project_exists(raw_name, base_dir=base)
        elif raw_name:
            exists = target_path.exists()

        if exists and clean_name != "Default":
            self.lbl_path_preview.setText(f"Zielpfad: {target_path} (⚠️ existiert bereits)")
            self.lbl_path_preview.setStyleSheet("color: #ff5555; font-size: 11px; font-family: monospace;")
        else:
            self.lbl_path_preview.setText(f"Zielpfad: {target_path}")
            self.lbl_path_preview.setStyleSheet("color: #6e7681; font-size: 11px; font-family: monospace;")

    def _on_create(self) -> None:
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Fehler", "Bitte gib einen Namen für das Projekt / die Box ein.")
            return

        base = Path(self.txt_dir.text().strip() or str(self.base_projects_dir))
        if self.project_manager and self.project_manager.project_exists(name, base_dir=base):
            clean = self.project_manager._sanitize_name(name)
            QMessageBox.warning(
                self, 
                "Projekt existiert bereits", 
                f"Ein Projekt mit dem bereinigten Namen '{clean}' existiert bereits im gewählten Workspace.\n\n"
                "Bitte wähle einen eindeutigen Projektnamen."
            )
            return

        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "name": self.txt_name.text().strip(),
            "target_ip": self.txt_target.text().strip(),
            "attacker_ip": self.default_attacker,
            "port": self.default_port,
            "base_dir": Path(self.txt_dir.text().strip()) if self.txt_dir.text().strip() else self.base_projects_dir
        }

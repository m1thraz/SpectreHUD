from pathlib import Path
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QWidget, QMessageBox, QFileDialog, QCheckBox
)
from PyQt6.QtCore import Qt
from typing import Dict, Any, Optional
from core.project import get_default_projects_dir
from core.i18n import t
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
        super().__init__(
            title=t("project_dialog.title", "SPECTRE // CREATE NEW PROJECT / BOX"),
            parent=parent
        )
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
        lbl_name = QLabel(t("project_dialog.lbl_name", "Project / Box Name:"))
        lbl_name.setProperty("class", "FormLabel")
        layout.addWidget(lbl_name)

        self.txt_name = QLineEdit(self.default_name)
        self.txt_name.setPlaceholderText(
            t("project_dialog.ph_name", "e.g. PickleRick, Blue, Lame, InternalAudit...")
        )
        self.txt_name.textChanged.connect(self._update_path_preview)
        layout.addWidget(self.txt_name)

        # 2. Target IP
        lbl_ip = QLabel(t("project_dialog.lbl_target", "Target IP:"))
        lbl_ip.setProperty("class", "FormLabel")
        layout.addWidget(lbl_ip)

        self.txt_target = QLineEdit(self.default_target)
        self.txt_target.setPlaceholderText(
            t("project_dialog.ph_target", "e.g. 10.10.10.80")
        )
        layout.addWidget(self.txt_target)

        # 3. Base Directory / Location
        lbl_dir = QLabel(t("project_dialog.lbl_dir", "Base Directory for Projects:"))
        lbl_dir.setProperty("class", "FormLabel")
        layout.addWidget(lbl_dir)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)

        self.txt_dir = QLineEdit(str(self.base_projects_dir))
        self.txt_dir.setPlaceholderText(
            t("project_dialog.ph_dir", "Path to workspace directory...")
        )
        self.txt_dir.textChanged.connect(self._update_path_preview)
        dir_row.addWidget(self.txt_dir, stretch=1)

        self.btn_browse = QPushButton(t("dialog.browse", "Browse..."))
        self.btn_browse.setProperty("class", "BrowseBtn")
        self.btn_browse.clicked.connect(self._on_browse_directory)
        dir_row.addWidget(self.btn_browse)

        layout.addLayout(dir_row)

        # 4. Optional encrypted project state (Pentest Mode)
        self.chk_pentest_mode = QCheckBox("Pentest-Modus (project_state.json verschlüsseln)")
        self.chk_pentest_mode.toggled.connect(self._toggle_pentest_mode_fields)
        layout.addWidget(self.chk_pentest_mode)

        self.txt_pentest_password = QLineEdit()
        self.txt_pentest_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pentest_password.setPlaceholderText("Passwort für Pentest-Modus")
        self.txt_pentest_password_confirm = QLineEdit()
        self.txt_pentest_password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pentest_password_confirm.setPlaceholderText("Passwort bestätigen")
        layout.addWidget(self.txt_pentest_password)
        layout.addWidget(self.txt_pentest_password_confirm)
        self._toggle_pentest_mode_fields(False)

        # 5. Target Directory Preview
        self.lbl_path_preview = QLabel(
            t("project_dialog.preview_path", "Destination path: {path}", path=self.base_projects_dir / (self.default_name or "Projektname"))
        )
        self.lbl_path_preview.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_path_preview.setStyleSheet("color: #6e7681; font-size: 11px; font-family: monospace;")
        layout.addWidget(self.lbl_path_preview)

        # 6. Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        lbl_hint = QLabel(t("project_dialog.btn_hint", "↵ Enter: Create | Esc: Cancel"))
        lbl_hint.setStyleSheet("color: #6e7681; font-size: 11px;")
        btn_layout.addWidget(lbl_hint)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton(t("dialog.cancel", "Cancel"))
        self.btn_cancel.setProperty("class", "SecondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_create = QPushButton(t("dialog.create", "Create Project"))
        self.btn_create.setProperty("class", "PrimaryBtn")
        self.btn_create.clicked.connect(self._on_create)
        btn_layout.addWidget(self.btn_create)

        layout.addLayout(btn_layout)

    def _toggle_pentest_mode_fields(self, enabled: bool) -> None:
        self.txt_pentest_password.setVisible(enabled)
        self.txt_pentest_password_confirm.setVisible(enabled)
        if not enabled:
            self.txt_pentest_password.clear()
            self.txt_pentest_password_confirm.clear()

    def _on_browse_directory(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, 
            t("project_dialog.select_dir_title", "Select Base Directory for Projects"), 
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
            self.lbl_path_preview.setText(
                t("project_dialog.preview_path", "Destination path: {path}", path=f"{target_path} (⚠️)")
            )
            self.lbl_path_preview.setStyleSheet("color: #ff5555; font-size: 11px; font-family: monospace;")
        else:
            self.lbl_path_preview.setText(
                t("project_dialog.preview_path", "Destination path: {path}", path=target_path)
            )
            self.lbl_path_preview.setStyleSheet("color: #6e7681; font-size: 11px; font-family: monospace;")

    def _on_create(self) -> None:
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(
                self,
                t("dialog.error", "Error"),
                t("project_dialog.err_name", "Please enter a name for the project / box.")
            )
            return

        base = Path(self.txt_dir.text().strip() or str(self.base_projects_dir))
        if self.project_manager and self.project_manager.project_exists(name, base_dir=base):
            clean = self.project_manager._sanitize_name(name)
            QMessageBox.warning(
                self, 
                t("project_dialog.err_exists_title", "Project Already Exists"), 
                t(
                    "project_dialog.err_exists_msg",
                    "A project named '{name}' already exists in the selected workspace.\n\nPlease choose a unique project name.",
                    name=clean
                )
            )
            return

        if self.chk_pentest_mode.isChecked():
            password = self.txt_pentest_password.text()
            if not password:
                QMessageBox.warning(self, "Passwort fehlt", "Für den Pentest-Modus ist ein Passwort erforderlich.")
                return
            if password != self.txt_pentest_password_confirm.text():
                QMessageBox.warning(self, "Passwörter stimmen nicht überein", "Bitte bestätige das gleiche Passwort.")
                return

        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "name": self.txt_name.text().strip(),
            "target_ip": self.txt_target.text().strip(),
            "attacker_ip": self.default_attacker,
            "port": self.default_port,
            "base_dir": Path(self.txt_dir.text().strip()) if self.txt_dir.text().strip() else self.base_projects_dir,
            "pentest_mode": self.chk_pentest_mode.isChecked(),
            "pentest_password": self.txt_pentest_password.text() if self.chk_pentest_mode.isChecked() else None,
        }


class ProjectUnlockDialog(BaseHudDialog):
    """Minimal password prompt for an encrypted Pentest-Mode project."""

    def __init__(self, project_name: str, parent: Optional[QWidget] = None):
        super().__init__(title="SPECTRE // PENTEST-MODUS ENTSPERREN", parent=parent)
        self.project_name = project_name
        self.setMinimumWidth(420)
        layout = self.body_layout
        layout.addWidget(QLabel(
            f"Das Projekt '{project_name}' verwendet den Pentest-Modus.\n"
            "Gib das Passwort ein, um dessen project_state.json zu entsperren."
        ))
        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setPlaceholderText("Passwort")
        self.txt_password.returnPressed.connect(self._on_unlock)
        layout.addWidget(self.txt_password)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Abbrechen")
        cancel.setProperty("class", "SecondaryBtn")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        unlock = QPushButton("Entsperren")
        unlock.setProperty("class", "PrimaryBtn")
        unlock.clicked.connect(self._on_unlock)
        buttons.addWidget(unlock)
        layout.addLayout(buttons)

    def _on_unlock(self) -> None:
        if not self.txt_password.text():
            QMessageBox.warning(self, "Passwort fehlt", "Bitte gib das Projektpasswort ein.")
            return
        self.accept()

    def get_password(self) -> str:
        return self.txt_password.text()

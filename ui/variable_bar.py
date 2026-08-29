from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QWidget, QToolTip
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from typing import Dict, Any
from core.net_detector import NetDetector
from core.i18n import t

class VariableBar(QFrame):
    """
    Compact horizontal status bar for Target IP, LHOST, Port and Auto-Detect.
    Emits `variables_changed` whenever any input field changes.
    """
    
    variables_changed = pyqtSignal(dict)
    add_snippet_clicked = pyqtSignal()

    def __init__(self, initial_vars: Dict[str, Any], parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("CompactVarBar")
        self.initial_vars = initial_vars
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        # 1. Target IP Input
        self.lbl_target = QLabel(t("varbar.target", "Target:"))
        self.lbl_target.setProperty("class", "VarTagLabel")
        self.txt_target = QLineEdit(str(self.initial_vars.get("target_ip", "10.10.10.10")))
        self.txt_target.setProperty("class", "CompactVarInput")
        self.txt_target.setPlaceholderText("10.10.10.x")
        self.txt_target.setFixedWidth(110)
        self.txt_target.textChanged.connect(self._on_values_changed)
        layout.addWidget(self.lbl_target)
        layout.addWidget(self.txt_target)

        # 2. Attacker IP / LHOST Input
        self.lbl_attacker = QLabel(t("varbar.attacker", "LHOST:"))
        self.lbl_attacker.setProperty("class", "VarTagLabel")
        self.txt_attacker = QLineEdit(str(self.initial_vars.get("attacker_ip", "10.10.14.5")))
        self.txt_attacker.setProperty("class", "CompactVarInput")
        self.txt_attacker.setPlaceholderText("10.10.14.x")
        self.txt_attacker.setFixedWidth(110)
        self.txt_attacker.textChanged.connect(self._on_values_changed)
        layout.addWidget(self.lbl_attacker)
        layout.addWidget(self.txt_attacker)

        # 3. Auto-Detect Button
        self.btn_auto = QPushButton(t("varbar.auto", "Auto"))
        self.btn_auto.setProperty("class", "AutoDetectBtn")
        self.btn_auto.setToolTip(t("varbar.auto_tip", "Auto-Erkennung für tun0 / VPN / lokale IP"))
        self.btn_auto.clicked.connect(self.auto_detect_ip)
        layout.addWidget(self.btn_auto)

        # 4. Port / LPORT Input
        self.lbl_port = QLabel(t("varbar.port", "Port:"))
        self.lbl_port.setProperty("class", "VarTagLabel")
        self.txt_port = QLineEdit(str(self.initial_vars.get("port", "4444")))
        self.txt_port.setProperty("class", "CompactVarInput")
        self.txt_port.setPlaceholderText("4444")
        self.txt_port.setFixedWidth(55)
        self.txt_port.textChanged.connect(self._on_values_changed)
        layout.addWidget(self.lbl_port)
        layout.addWidget(self.txt_port)

        # 5. Username Input
        self.lbl_user = QLabel(t("varbar.user", "User:"))
        self.lbl_user.setProperty("class", "VarTagLabel")
        self.txt_user = QLineEdit(str(self.initial_vars.get("username", "")))
        self.txt_user.setProperty("class", "CompactVarInput")
        self.txt_user.setPlaceholderText("admin")
        self.txt_user.setFixedWidth(110)
        self.txt_user.textChanged.connect(self._on_values_changed)
        layout.addWidget(self.lbl_user)
        layout.addWidget(self.txt_user)

        # 6. Password Input with Toggle
        self.lbl_pass = QLabel(t("varbar.pass", "Pass:"))
        self.lbl_pass.setProperty("class", "VarTagLabel")
        self.txt_pass = QLineEdit(str(self.initial_vars.get("password", "")))
        self.txt_pass.setProperty("class", "CompactVarInput")
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pass.setPlaceholderText("••••")
        self.txt_pass.setFixedWidth(110)
        self.txt_pass.textChanged.connect(self._on_values_changed)
        layout.addWidget(self.lbl_pass)
        layout.addWidget(self.txt_pass)

        self.btn_toggle_pass = QPushButton("👁")
        self.btn_toggle_pass.setProperty("class", "VarPassToggleBtn")
        self.btn_toggle_pass.setToolTip(t("varbar.pass_toggle_tip", "Passwort ein-/ausblenden"))
        self.btn_toggle_pass.setFixedWidth(24)
        self.btn_toggle_pass.clicked.connect(self._toggle_pass_visibility)
        layout.addWidget(self.btn_toggle_pass)

        layout.addStretch()

        # 7. Add Snippet Button
        self.btn_add = QPushButton(t("varbar.add_btn", "+ Neu"))
        self.btn_add.setProperty("class", "MiniPrimaryBtn")
        self.btn_add.setToolTip(t("varbar.add_btn_tip", "Neuen Befehl anlegen (Ctrl+N)"))
        self.btn_add.clicked.connect(self.add_snippet_clicked.emit)
        layout.addWidget(self.btn_add)

    def _toggle_pass_visibility(self) -> None:
        """Toggles password field between masked (dots) and plaintext."""
        if self.txt_pass.echoMode() == QLineEdit.EchoMode.Password:
            self.txt_pass.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_pass.setText("🔒")
        else:
            self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_pass.setText("👁")

    def retranslate(self) -> None:
        """Updates text elements when language changes."""
        self.lbl_target.setText(t("varbar.target", "Target:"))
        self.lbl_attacker.setText(t("varbar.attacker", "LHOST:"))
        self.lbl_port.setText(t("varbar.port", "Port:"))
        self.lbl_user.setText(t("varbar.user", "User:"))
        self.lbl_pass.setText(t("varbar.pass", "Pass:"))
        self.btn_toggle_pass.setToolTip(t("varbar.pass_toggle_tip", "Passwort ein-/ausblenden"))
        self.btn_auto.setText(t("varbar.auto", "Auto"))
        self.btn_auto.setToolTip(t("varbar.auto_tip", "Auto-Erkennung für tun0 / VPN / lokale IP"))
        self.btn_add.setText(t("varbar.add_btn", "+ Neu"))
        self.btn_add.setToolTip(t("varbar.add_btn_tip", "Neuen Befehl anlegen (Ctrl+N)"))

    def auto_detect_ip(self) -> None:
        """Runs the network detector and fills the LHOST if an IP is detected."""
        detected = NetDetector.detect_attacker_ip()
        if detected:
            self.txt_attacker.setText(detected)
            self.btn_auto.setText("✓ " + detected)
            QTimer.singleShot(2000, lambda: self.btn_auto.setText(t("varbar.auto", "Auto")))
        else:
            self.btn_auto.setText(t("varbar.no_ip", "Keine IP"))
            QTimer.singleShot(2000, lambda: self.btn_auto.setText(t("varbar.auto", "Auto")))

    def _on_values_changed(self) -> None:
        self.variables_changed.emit(self.get_variables())

    def set_variables(self, vars: Dict[str, Any]) -> None:
        """Populates fields without losing signals."""
        self.txt_target.blockSignals(True)
        self.txt_attacker.blockSignals(True)
        self.txt_port.blockSignals(True)
        self.txt_user.blockSignals(True)
        self.txt_pass.blockSignals(True)

        if "target_ip" in vars:
            self.txt_target.setText(str(vars["target_ip"]))
        if "attacker_ip" in vars:
            self.txt_attacker.setText(str(vars["attacker_ip"]))
        if "port" in vars:
            self.txt_port.setText(str(vars["port"]))
        if "username" in vars:
            self.txt_user.setText(str(vars["username"]))
        if "password" in vars:
            self.txt_pass.setText(str(vars["password"]))

        self.txt_target.blockSignals(False)
        self.txt_attacker.blockSignals(False)
        self.txt_port.blockSignals(False)
        self.txt_user.blockSignals(False)
        self.txt_pass.blockSignals(False)

        self._on_values_changed()

    def get_variables(self) -> Dict[str, str]:
        return {
            "target_ip": self.txt_target.text().strip(),
            "attacker_ip": self.txt_attacker.text().strip(),
            "port": self.txt_port.text().strip(),
            "username": self.txt_user.text().strip(),
            "password": self.txt_pass.text().strip(),
            "wordlist": self.initial_vars.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        }

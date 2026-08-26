from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QWidget, QToolTip
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from typing import Dict, Any
from core.net_detector import NetDetector

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
        lbl_target = QLabel("Target:")
        lbl_target.setProperty("class", "VarTagLabel")
        self.txt_target = QLineEdit(str(self.initial_vars.get("target_ip", "10.10.10.10")))
        self.txt_target.setProperty("class", "CompactVarInput")
        self.txt_target.setPlaceholderText("10.10.10.x")
        self.txt_target.setFixedWidth(110)
        self.txt_target.textChanged.connect(self._on_values_changed)
        layout.addWidget(lbl_target)
        layout.addWidget(self.txt_target)

        # 2. Attacker IP / LHOST Input
        lbl_attacker = QLabel("LHOST:")
        lbl_attacker.setProperty("class", "VarTagLabel")
        self.txt_attacker = QLineEdit(str(self.initial_vars.get("attacker_ip", "10.10.14.5")))
        self.txt_attacker.setProperty("class", "CompactVarInput")
        self.txt_attacker.setPlaceholderText("10.10.14.x")
        self.txt_attacker.setFixedWidth(110)
        self.txt_attacker.textChanged.connect(self._on_values_changed)
        layout.addWidget(lbl_attacker)
        layout.addWidget(self.txt_attacker)

        # 3. Auto-Detect Button
        self.btn_auto = QPushButton("Auto")
        self.btn_auto.setProperty("class", "AutoDetectBtn")
        self.btn_auto.setToolTip("Auto-Erkennung für tun0 / VPN / lokale IP")
        self.btn_auto.clicked.connect(self.auto_detect_ip)
        layout.addWidget(self.btn_auto)

        # 4. Port / LPORT Input
        lbl_port = QLabel("Port:")
        lbl_port.setProperty("class", "VarTagLabel")
        self.txt_port = QLineEdit(str(self.initial_vars.get("port", "4444")))
        self.txt_port.setProperty("class", "CompactVarInput")
        self.txt_port.setPlaceholderText("4444")
        self.txt_port.setFixedWidth(65)
        self.txt_port.textChanged.connect(self._on_values_changed)
        layout.addWidget(lbl_port)
        layout.addWidget(self.txt_port)

        layout.addStretch()

        # 5. Add Snippet Button
        self.btn_add = QPushButton("+ Neu")
        self.btn_add.setProperty("class", "MiniPrimaryBtn")
        self.btn_add.setToolTip("Neuen Befehl anlegen (Ctrl+N)")
        self.btn_add.clicked.connect(self.add_snippet_clicked.emit)
        layout.addWidget(self.btn_add)

    def auto_detect_ip(self) -> None:
        """Runs the network detector and fills the LHOST if an IP is detected."""
        detected = NetDetector.detect_attacker_ip()
        if detected:
            self.txt_attacker.setText(detected)
            self.btn_auto.setText("✓ " + detected)
            QTimer.singleShot(2000, lambda: self.btn_auto.setText("Auto"))
        else:
            self.btn_auto.setText("Keine IP")
            QTimer.singleShot(2000, lambda: self.btn_auto.setText("Auto"))

    def _on_values_changed(self) -> None:
        self.variables_changed.emit(self.get_variables())

    def get_variables(self) -> Dict[str, str]:
        return {
            "target_ip": self.txt_target.text().strip(),
            "attacker_ip": self.txt_attacker.text().strip(),
            "port": self.txt_port.text().strip(),
            "wordlist": self.initial_vars.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        }

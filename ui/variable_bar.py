from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget
from PyQt6.QtCore import pyqtSignal, QTimer
from typing import Dict, Any, Optional
from core.net_detector import NetDetector
from core.i18n import t
from ui.variable_popovers import AuthPopover, ScopePopover
from ui.copyable_line_edit import CopyableLineEdit


class VariableBar(QFrame):
    """
    Compact horizontal status bar for Target IP, LHOST, Port and Auto-Detect,
    combined with quick-access popovers for Auth (User/Pass/Domain/Hash) and Scope (Wordlist/URL).
    Emits `variables_changed` whenever any input field changes.
    """

    variables_changed = pyqtSignal(dict)
    add_snippet_clicked = pyqtSignal()

    def __init__(self, initial_vars: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("CompactVarBar")
        self.initial_vars = initial_vars

        # Secondary popover frames
        self.popover_auth = AuthPopover(self)
        self.popover_scope = ScopePopover(self)

        # Backwards compatibility handles
        self.txt_user = self.popover_auth.txt_user
        self.txt_pass = self.popover_auth.txt_pass
        self.txt_port = self.popover_auth.txt_port
        self.btn_toggle_pass = self.popover_auth.btn_toggle_pass

        self._init_ui()

        # Connect popover changes
        self.popover_auth.values_changed.connect(self._on_popover_values_changed)
        self.popover_scope.values_changed.connect(self._on_popover_values_changed)

        # Initial popover values
        self.popover_auth.set_values(self.initial_vars)
        self.popover_scope.set_values(self.initial_vars)
        self._update_badge_buttons()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        # 1. Target IP Input
        self.lbl_target = QLabel(t("varbar.target", "Target:"))
        self.lbl_target.setProperty("class", "VarTagLabel")
        self.txt_target = CopyableLineEdit(str(self.initial_vars.get("target_ip", "10.10.10.10")))
        self.txt_target.setProperty("class", "CompactVarInput")
        self.txt_target.setPlaceholderText("10.10.10.x")
        self.txt_target.setFixedWidth(112)
        self.txt_target.textChanged.connect(self._on_values_changed)
        layout.addWidget(self.lbl_target)
        layout.addWidget(self.txt_target)

        # 2. Attacker IP / LHOST Input
        self.lbl_attacker = QLabel(t("varbar.attacker", "LHOST:"))
        self.lbl_attacker.setProperty("class", "VarTagLabel")
        self.txt_attacker = CopyableLineEdit(str(self.initial_vars.get("attacker_ip", "10.10.14.5")))
        self.txt_attacker.setProperty("class", "CompactVarInput")
        self.txt_attacker.setPlaceholderText("10.10.14.x")
        self.txt_attacker.setFixedWidth(112)
        self.txt_attacker.textChanged.connect(self._on_values_changed)
        layout.addWidget(self.lbl_attacker)
        layout.addWidget(self.txt_attacker)

        # 3. Auto-Detect Button
        self.btn_auto = QPushButton(t("varbar.auto", "Auto"))
        self.btn_auto.setProperty("class", "AutoDetectBtn")
        self.btn_auto.setToolTip(t("varbar.auto_tip", "Auto-Erkennung für tun0 / VPN / lokale IP"))
        self.btn_auto.clicked.connect(self.auto_detect_ip)
        layout.addWidget(self.btn_auto)

        # 4. Auth Popover Button (User, Pass, Port, Domain, Hash)
        self.btn_auth = QPushButton("👤 Auth ▾")
        self.btn_auth.setProperty("class", "VarBadgeBtn")
        self.btn_auth.setToolTip(t("varbar.auth_tip", "Benutzer, Passwort, Domain & Hash verwalten"))
        self.btn_auth.clicked.connect(lambda: self.popover_auth.show_below(self.btn_auth))
        layout.addWidget(self.btn_auth)

        # 6. Scope Popover Button (Wordlist, Target URL)
        self.btn_scope = QPushButton("📁 Scope ▾")
        self.btn_scope.setProperty("class", "VarBadgeBtn")
        self.btn_scope.setToolTip(t("varbar.scope_tip", "Wordlist-Pfad und Ziel-URL verwalten"))
        self.btn_scope.clicked.connect(lambda: self.popover_scope.show_below(self.btn_scope))
        layout.addWidget(self.btn_scope)

        layout.addStretch()

        # 7. Add Snippet Button
        self.btn_add = QPushButton(t("varbar.add_btn", "+ Neu"))
        self.btn_add.setProperty("class", "MiniPrimaryBtn")
        self.btn_add.setToolTip(t("varbar.add_btn_tip", "Neuen Befehl anlegen (Ctrl+N)"))
        self.btn_add.clicked.connect(self.add_snippet_clicked.emit)
        layout.addWidget(self.btn_add)

    def _update_badge_buttons(self) -> None:
        """Refreshes text and active styling on Auth and Scope buttons."""
        auth_vals = self.popover_auth.get_values()
        username = auth_vals.get("username", "")
        has_auth = self.popover_auth.has_active_values()

        if has_auth:
            label = f"👤 {username[:10]} ▾" if username else "👤 Auth* ▾"
            self.btn_auth.setText(label)
            self.btn_auth.setProperty("class", "VarBadgeBtnActive")
        else:
            self.btn_auth.setText("👤 Auth ▾")
            self.btn_auth.setProperty("class", "VarBadgeBtn")
        self.btn_auth.style().unpolish(self.btn_auth)
        self.btn_auth.style().polish(self.btn_auth)

        has_scope = self.popover_scope.has_active_values()
        if has_scope:
            self.btn_scope.setText("📁 Scope* ▾")
            self.btn_scope.setProperty("class", "VarBadgeBtnActive")
        else:
            self.btn_scope.setText("📁 Scope ▾")
            self.btn_scope.setProperty("class", "VarBadgeBtn")
        self.btn_scope.style().unpolish(self.btn_scope)
        self.btn_scope.style().polish(self.btn_scope)

    def _on_popover_values_changed(self) -> None:
        self._update_badge_buttons()
        self._on_values_changed()

    def retranslate(self) -> None:
        """Updates text elements when language changes."""
        self.lbl_target.setText(t("varbar.target", "Target:"))
        self.lbl_attacker.setText(t("varbar.attacker", "LHOST:"))
        self.txt_target.retranslate()
        self.txt_attacker.retranslate()
        self.btn_auto.setText(t("varbar.auto", "Auto"))
        self.btn_auto.setToolTip(t("varbar.auto_tip", "Auto-Erkennung für tun0 / VPN / lokale IP"))
        self.btn_auth.setToolTip(t("varbar.auth_tip", "Benutzer, Passwort, Port, Domain & Hash verwalten"))
        self.btn_scope.setToolTip(t("varbar.scope_tip", "Wordlist-Pfad und Ziel-URL verwalten"))
        self.btn_add.setText(t("varbar.add_btn", "+ Neu"))
        self.btn_add.setToolTip(t("varbar.add_btn_tip", "Neuen Befehl anlegen (Ctrl+N)"))
        self.popover_auth.retranslate()
        self.popover_scope.retranslate()
        self._update_badge_buttons()

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

        if "target_ip" in vars:
            self.txt_target.setText(str(vars["target_ip"]))
        if "attacker_ip" in vars:
            self.txt_attacker.setText(str(vars["attacker_ip"]))
        if "port" in vars:
            self.txt_port.setText(str(vars["port"]))

        self.popover_auth.set_values(vars)
        self.popover_scope.set_values(vars)
        self._update_badge_buttons()

        self.txt_target.blockSignals(False)
        self.txt_attacker.blockSignals(False)
        self.txt_port.blockSignals(False)

        self._on_values_changed()

    def get_variables(self) -> Dict[str, str]:
        auth_vals = self.popover_auth.get_values()
        scope_vals = self.popover_scope.get_values()
        return {
            "target_ip": self.txt_target.text().strip(),
            "attacker_ip": self.txt_attacker.text().strip(),
            "port": self.txt_port.text().strip(),
            "username": auth_vals.get("username", ""),
            "password": auth_vals.get("password", ""),
            "domain": auth_vals.get("domain", ""),
            "ntlm_hash": auth_vals.get("ntlm_hash", ""),
            "hash": auth_vals.get("hash", ""),
            "hash_file": auth_vals.get("hash_file", ""),
            "wordlist": scope_vals.get("wordlist", "") or self.initial_vars.get("wordlist", "/usr/share/wordlists/dirb/common.txt"),
            "url": scope_vals.get("url", ""),
            "subnet": scope_vals.get("subnet", ""),
            "dns_server": scope_vals.get("dns_server", ""),
            "dns": scope_vals.get("dns", ""),
        }

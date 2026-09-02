"""Popover flyout dialogs for secondary variables (Auth & Scope)."""

from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
    QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QGuiApplication
from core.i18n import t
from ui.copyable_line_edit import CopyableLineEdit


class BaseVarPopover(QFrame):
    """Base frameless popup frame that anchors below a trigger button."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("VarPopoverFrame")
        self.setStyleSheet("""
            QFrame#VarPopoverFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
            QLabel.VarPopoverTitle {
                color: #58a6ff;
                font-size: 11px;
                font-weight: 600;
                padding-bottom: 2px;
                border-bottom: 1px solid #21262d;
            }
            QLabel.VarPopoverLabel {
                color: #8b949e;
                font-size: 11px;
                font-weight: 500;
                min-width: 60px;
            }
            QLineEdit.VarPopoverInput {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-family: monospace;
            }
            QLineEdit.VarPopoverInput:focus {
                border-color: #58a6ff;
            }
            QPushButton.VarPopoverBtn {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton.VarPopoverBtn:hover {
                background-color: #30363d;
                color: #f0f6fc;
                border-color: #58a6ff;
            }
        """)

    def show_below(self, anchor: QWidget) -> None:
        """Positions and displays the popover directly beneath the anchor widget."""
        self.adjustSize()
        global_pos = anchor.mapToGlobal(QPoint(0, anchor.height() + 4))

        screen = QGuiApplication.screenAt(global_pos)
        if screen:
            screen_geo = screen.availableGeometry()
            pop_w = self.width()
            pop_h = self.height()
            x = min(global_pos.x(), screen_geo.right() - pop_w - 8)
            y = min(global_pos.y(), screen_geo.bottom() - pop_h - 8)
            self.move(max(screen_geo.left() + 8, x), y)
        else:
            self.move(global_pos)

        self.show()
        self.raise_()
        self.activateWindow()


class AuthPopover(BaseVarPopover):
    """Flyout popover for Username, Password, Domain, and NTLM Hash."""

    values_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.lbl_title = QLabel(t("varbar.auth_title", "Authentifizierung"))
        self.lbl_title.setProperty("class", "VarPopoverTitle")
        layout.addWidget(self.lbl_title)

        row_user = QHBoxLayout()
        row_user.setSpacing(6)
        self.lbl_user = QLabel(t("varbar.user", "User:"))
        self.lbl_user.setProperty("class", "VarPopoverLabel")
        self.txt_user = CopyableLineEdit()
        self.txt_user.setProperty("class", "VarPopoverInput")
        self.txt_user.setPlaceholderText("admin / root")
        self.txt_user.textChanged.connect(self.values_changed.emit)
        row_user.addWidget(self.lbl_user)
        row_user.addWidget(self.txt_user)
        layout.addLayout(row_user)

        row_pass = QHBoxLayout()
        row_pass.setSpacing(6)
        self.lbl_pass = QLabel(t("varbar.pass", "Pass:"))
        self.lbl_pass.setProperty("class", "VarPopoverLabel")
        self.txt_pass = QLineEdit()
        self.txt_pass.setProperty("class", "VarPopoverInput")
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pass.setPlaceholderText("••••••••")
        self.txt_pass.textChanged.connect(self.values_changed.emit)

        self.btn_toggle_pass = QPushButton("👁")
        self.btn_toggle_pass.setProperty("class", "VarPopoverBtn")
        self.btn_toggle_pass.setFixedWidth(28)
        self.btn_toggle_pass.setToolTip(t("varbar.pass_toggle_tip", "Passwort ein-/ausblenden"))
        self.btn_toggle_pass.clicked.connect(self._toggle_pass_visibility)

        row_pass.addWidget(self.lbl_pass)
        row_pass.addWidget(self.txt_pass)
        row_pass.addWidget(self.btn_toggle_pass)
        layout.addLayout(row_pass)

        row_port = QHBoxLayout()
        row_port.setSpacing(6)
        self.lbl_port = QLabel(t("varbar.port", "Port:"))
        self.lbl_port.setProperty("class", "VarPopoverLabel")
        self.txt_port = CopyableLineEdit()
        self.txt_port.setProperty("class", "VarPopoverInput")
        self.txt_port.setPlaceholderText("4444 / 8080")
        self.txt_port.textChanged.connect(self.values_changed.emit)
        row_port.addWidget(self.lbl_port)
        row_port.addWidget(self.txt_port)
        layout.addLayout(row_port)

        row_domain = QHBoxLayout()
        row_domain.setSpacing(6)
        self.lbl_domain = QLabel(t("varbar.domain", "Domain:"))
        self.lbl_domain.setProperty("class", "VarPopoverLabel")
        self.txt_domain = CopyableLineEdit()
        self.txt_domain.setProperty("class", "VarPopoverInput")
        self.txt_domain.setPlaceholderText("corp.local / htb.local")
        self.txt_domain.textChanged.connect(self.values_changed.emit)
        row_domain.addWidget(self.lbl_domain)
        row_domain.addWidget(self.txt_domain)
        layout.addLayout(row_domain)

        row_hash = QHBoxLayout()
        row_hash.setSpacing(6)
        self.lbl_hash = QLabel(t("varbar.ntlm_hash", "Hash:"))
        self.lbl_hash.setProperty("class", "VarPopoverLabel")
        self.txt_hash = CopyableLineEdit()
        self.txt_hash.setProperty("class", "VarPopoverInput")
        self.txt_hash.setPlaceholderText("aad3b435b5... / LM:NTLM")
        self.txt_hash.textChanged.connect(self.values_changed.emit)
        row_hash.addWidget(self.lbl_hash)
        row_hash.addWidget(self.txt_hash)
        layout.addLayout(row_hash)

    def _toggle_pass_visibility(self) -> None:
        if self.txt_pass.echoMode() == QLineEdit.EchoMode.Password:
            self.txt_pass.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_pass.setText("🔒")
        else:
            self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_pass.setText("👁")

    def get_values(self) -> Dict[str, str]:
        return {
            "username": self.txt_user.text().strip(),
            "password": self.txt_pass.text().strip(),
            "port": self.txt_port.text().strip(),
            "domain": self.txt_domain.text().strip(),
            "ntlm_hash": self.txt_hash.text().strip(),
        }

    def set_values(self, vals: Dict[str, Any]) -> None:
        self.txt_user.blockSignals(True)
        self.txt_pass.blockSignals(True)
        self.txt_port.blockSignals(True)
        self.txt_domain.blockSignals(True)
        self.txt_hash.blockSignals(True)

        if "username" in vals:
            self.txt_user.setText(str(vals.get("username", "")))
        if "password" in vals:
            self.txt_pass.setText(str(vals.get("password", "")))
        if "port" in vals:
            self.txt_port.setText(str(vals.get("port", "")))
        if "domain" in vals:
            self.txt_domain.setText(str(vals.get("domain", "")))
        if "ntlm_hash" in vals:
            self.txt_hash.setText(str(vals.get("ntlm_hash", "")))

        self.txt_user.blockSignals(False)
        self.txt_pass.blockSignals(False)
        self.txt_port.blockSignals(False)
        self.txt_domain.blockSignals(False)
        self.txt_hash.blockSignals(False)

    def has_active_values(self) -> bool:
        vals = self.get_values()
        return bool(
            vals.get("username")
            or vals.get("password")
            or vals.get("domain")
            or vals.get("ntlm_hash")
        )

    def retranslate(self) -> None:
        self.lbl_title.setText(t("varbar.auth_title", "Authentifizierung"))
        self.lbl_user.setText(t("varbar.user", "User:"))
        self.lbl_pass.setText(t("varbar.pass", "Pass:"))
        self.lbl_port.setText(t("varbar.port", "Port:"))
        self.lbl_domain.setText(t("varbar.domain", "Domain:"))
        self.lbl_hash.setText(t("varbar.ntlm_hash", "Hash:"))
        self.btn_toggle_pass.setToolTip(t("varbar.pass_toggle_tip", "Passwort ein-/ausblenden"))
        self.txt_user.retranslate()
        self.txt_port.retranslate()
        self.txt_domain.retranslate()
        self.txt_hash.retranslate()


class ScopePopover(BaseVarPopover):
    """Flyout popover for Wordlist and Target URL/Path."""

    values_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedWidth(320)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.lbl_title = QLabel(t("varbar.scope_title", "Scope & Umgebung"))
        self.lbl_title.setProperty("class", "VarPopoverTitle")
        layout.addWidget(self.lbl_title)

        self.lbl_wordlist = QLabel(t("varbar.wordlist", "Wordlist:"))
        self.lbl_wordlist.setProperty("class", "VarPopoverLabel")
        layout.addWidget(self.lbl_wordlist)

        row_wl = QHBoxLayout()
        row_wl.setSpacing(6)
        self.txt_wordlist = QLineEdit()
        self.txt_wordlist.setProperty("class", "VarPopoverInput")
        self.txt_wordlist.setPlaceholderText("/usr/share/wordlists/dirb/common.txt")
        self.txt_wordlist.textChanged.connect(self.values_changed.emit)

        self.btn_browse = QPushButton(t("varbar.browse", "..."))
        self.btn_browse.setProperty("class", "VarPopoverBtn")
        self.btn_browse.setFixedWidth(28)
        self.btn_browse.setToolTip(t("varbar.browse_tip", "Wordlist-Datei auswählen"))
        self.btn_browse.clicked.connect(self._browse_wordlist)

        row_wl.addWidget(self.txt_wordlist)
        row_wl.addWidget(self.btn_browse)
        layout.addLayout(row_wl)

        self.lbl_url = QLabel(t("varbar.url", "Target URL / Endpoint:"))
        self.lbl_url.setProperty("class", "VarPopoverLabel")
        layout.addWidget(self.lbl_url)

        self.txt_url = CopyableLineEdit()
        self.txt_url.setProperty("class", "VarPopoverInput")
        self.txt_url.setPlaceholderText("http://10.10.10.10:8080/api")
        self.txt_url.textChanged.connect(self.values_changed.emit)
        layout.addWidget(self.txt_url)

    def _browse_wordlist(self) -> None:
        import os
        start_dir = "/usr/share/wordlists" if os.name != "nt" else "C:\\"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("varbar.select_wordlist", "Wordlist auswählen"),
            start_dir,
            "Text / Lists (*.txt *.lst *.dict);;All Files (*.*)",
        )
        if file_path:
            self.txt_wordlist.setText(file_path)

    def get_values(self) -> Dict[str, str]:
        return {
            "wordlist": self.txt_wordlist.text().strip(),
            "url": self.txt_url.text().strip(),
        }

    def set_values(self, vals: Dict[str, Any]) -> None:
        self.txt_wordlist.blockSignals(True)
        self.txt_url.blockSignals(True)

        if "wordlist" in vals:
            self.txt_wordlist.setText(str(vals.get("wordlist", "")))
        if "url" in vals:
            self.txt_url.setText(str(vals.get("url", "")))

        self.txt_wordlist.blockSignals(False)
        self.txt_url.blockSignals(False)

    def has_active_values(self) -> bool:
        wl = self.txt_wordlist.text().strip()
        url = self.txt_url.text().strip()
        return bool(url) or (bool(wl) and wl != "/usr/share/wordlists/dirb/common.txt")

    def retranslate(self) -> None:
        self.lbl_title.setText(t("varbar.scope_title", "Scope & Umgebung"))
        self.lbl_wordlist.setText(t("varbar.wordlist", "Wordlist:"))
        self.lbl_url.setText(t("varbar.url", "Target URL / Endpoint:"))
        self.btn_browse.setToolTip(t("varbar.browse_tip", "Wordlist-Datei auswählen"))
        self.txt_url.retranslate()
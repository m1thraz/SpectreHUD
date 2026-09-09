from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget
from PyQt6.QtCore import pyqtSignal, QTimer, QSize
from typing import Dict, Any, Optional
from core.net_detector import NetDetector
from core.i18n import t
from ui.variable_popovers import AuthPopover, ScopePopover
from ui.copyable_line_edit import CopyableLineEdit
from ui.styles.icons import icon
from ui.styles.palette import STATUS_SUCCESS


VARIABLE_BAR_ICON_SIZE = QSize(12, 12)
COLLAPSED_RESTORE_SIZE = 16


class VariableBar(QFrame):
    """
    Compact horizontal status bar for Target IP, LHOST, Port and Auto-Detect,
    combined with quick-access popovers for Auth (User/Pass/Domain/Hash) and Scope (Wordlist/URL).
    Emits `variables_changed` whenever any input field changes.

    A chevron toggle on the far right hides the complete bar surface and leaves
    only the restore control visible.
    """

    variables_changed = pyqtSignal(dict)
    add_snippet_clicked = pyqtSignal()

    def __init__(self, initial_vars: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("CompactVarBar")
        self.initial_vars = initial_vars
        self._collapsed = False
        self._add_visible = True
        self._expanded_minimum_height = self.minimumHeight()
        self._expanded_maximum_height = self.maximumHeight()

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
        self._outer_layout = QHBoxLayout(self)
        self._outer_layout.setContentsMargins(12, 4, 12, 4)
        self._outer_layout.setSpacing(8)

        # --- Content container (everything that collapses) ---
        self._content = QWidget(self)
        layout = QHBoxLayout(self._content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 1. Target IP Input
        self.lbl_target = QLabel(t("varbar.target", "Target:"))
        self.lbl_target.setProperty("class", "VarTagLabel")
        self.txt_target = CopyableLineEdit(str(self.initial_vars.get("target_ip", "10.10.10.10")))
        self.txt_target.setProperty("class", "CompactVarInput")
        self.txt_target.setPlaceholderText("10.10.10.x")
        self.txt_target.setFixedWidth(138)
        self.txt_target.setToolTip(
            t("varbar.target_tip", "Target used to fill variables in copied Cheatsheet commands")
        )
        self.txt_target.textChanged.connect(self._on_values_changed)
        layout.addWidget(self.lbl_target)
        layout.addWidget(self.txt_target)

        # 2. Attacker IP / LHOST Input
        self.lbl_attacker = QLabel(t("varbar.attacker", "LHOST:"))
        self.lbl_attacker.setProperty("class", "VarTagLabel")
        self.txt_attacker = CopyableLineEdit(str(self.initial_vars.get("attacker_ip", "10.10.14.5")))
        self.txt_attacker.setProperty("class", "CompactVarInput")
        self.txt_attacker.setPlaceholderText("10.10.14.x")
        self.txt_attacker.setFixedWidth(138)
        self.txt_attacker.setToolTip(
            t("varbar.attacker_tip", "LHOST used to fill variables in copied Cheatsheet commands")
        )
        self.txt_attacker.textChanged.connect(self._on_values_changed)
        layout.addWidget(self.lbl_attacker)
        layout.addWidget(self.txt_attacker)

        # 3. Auto-Detect Button
        self.btn_auto = QPushButton(t("varbar.auto", "Auto"))
        self.btn_auto.setIcon(icon("fa5s.crosshairs"))
        self.btn_auto.setIconSize(VARIABLE_BAR_ICON_SIZE)
        self.btn_auto.setProperty("class", "AutoDetectBtn")
        self.btn_auto.setToolTip(t("varbar.auto_tip", "Auto-Erkennung für tun0 / VPN / lokale IP"))
        self.btn_auto.clicked.connect(self.auto_detect_ip)
        layout.addWidget(self.btn_auto)

        # 4. Auth Popover Button (User, Pass, Port, Domain, Hash)
        self.btn_auth = QPushButton("Auth ▾")
        self.btn_auth.setIcon(icon("fa5s.user"))
        self.btn_auth.setIconSize(VARIABLE_BAR_ICON_SIZE)
        self.btn_auth.setProperty("class", "VarBadgeBtn")
        self.btn_auth.setToolTip(
            t("varbar.auth_tip", "Set authentication variables used in copied Cheatsheet commands")
        )
        self.btn_auth.clicked.connect(lambda: self.popover_auth.show_below(self.btn_auth))
        layout.addWidget(self.btn_auth)

        # 5. Scope Popover Button (Wordlist, Target URL)
        self.btn_scope = QPushButton("Scope ▾")
        self.btn_scope.setIcon(icon("fa5s.folder"))
        self.btn_scope.setIconSize(VARIABLE_BAR_ICON_SIZE)
        self.btn_scope.setProperty("class", "VarBadgeBtn")
        self.btn_scope.setToolTip(
            t("varbar.scope_tip", "Set scope and environment variables used in copied Cheatsheet commands")
        )
        self.btn_scope.clicked.connect(lambda: self.popover_scope.show_below(self.btn_scope))
        layout.addWidget(self.btn_scope)

        self._outer_layout.addWidget(self._content)
        self._outer_layout.addStretch()

        # 6. Add Snippet Button — only shown in cheatsheet mode (see set_add_visible)
        self.btn_add = QPushButton(t("varbar.add_btn", "Neu"))
        self.btn_add.setIcon(icon("fa5s.plus"))
        self.btn_add.setIconSize(VARIABLE_BAR_ICON_SIZE)
        self.btn_add.setProperty("class", "MiniPrimaryBtn")
        self.btn_add.setToolTip(t("varbar.add_btn_tip", "Neuen Befehl anlegen (Ctrl+N)"))
        self.btn_add.clicked.connect(self.add_snippet_clicked.emit)
        self.btn_add.setVisible(True)
        self._outer_layout.addWidget(self.btn_add)

        # --- Chevron toggle (always visible, far right) ---
        self.btn_collapse = QPushButton(self)
        self.btn_collapse.setProperty("class", "SecondaryBtn FormatToolBtn ReportIconBtn")
        self.btn_collapse.setFixedSize(22, 22)
        self.btn_collapse.clicked.connect(self._toggle_collapsed)
        self._outer_layout.addWidget(self.btn_collapse)

        self._apply_collapsed_state()

    # ------------------------------------------------------------------ #
    # Collapse / expand
    # ------------------------------------------------------------------ #

    def _toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self._apply_collapsed_state()

    def _apply_collapsed_state(self) -> None:
        self._content.setVisible(not self._collapsed)
        self.btn_add.setVisible(self._add_visible and not self._collapsed)
        self.setProperty("collapsed", self._collapsed)
        if self._collapsed:
            self._outer_layout.setContentsMargins(0, 0, 0, 0)
            self.btn_collapse.setFixedSize(COLLAPSED_RESTORE_SIZE, COLLAPSED_RESTORE_SIZE)
            self.setFixedHeight(COLLAPSED_RESTORE_SIZE)
        else:
            self.setMinimumHeight(self._expanded_minimum_height)
            self.setMaximumHeight(self._expanded_maximum_height)
            self._outer_layout.setContentsMargins(12, 4, 12, 4)
            self.btn_collapse.setFixedSize(22, 22)
        self.style().unpolish(self)
        self.style().polish(self)
        if self._collapsed:
            tip = t("varbar.expand_tip", "Show variable bar")
            ico = "fa5s.chevron-down"
        else:
            tip = t("varbar.collapse_tip", "Hide variable bar")
            ico = "fa5s.chevron-up"
        self.btn_collapse.setToolTip(tip)
        self.btn_collapse.setIcon(icon(ico))
        self.btn_collapse.setIconSize(VARIABLE_BAR_ICON_SIZE)

    def set_add_visible(self, visible: bool) -> None:
        """Show or hide the New-snippet button (only relevant in cheatsheet mode)."""
        self._add_visible = visible
        self.btn_add.setVisible(visible and not self._collapsed)

    # ------------------------------------------------------------------ #
    # Badge / popover helpers
    # ------------------------------------------------------------------ #

    def _update_badge_buttons(self) -> None:
        """Refreshes text and active styling on Auth and Scope buttons."""
        auth_vals = self.popover_auth.get_values()
        username = auth_vals.get("username", "")
        has_auth = self.popover_auth.has_active_values()

        if has_auth:
            label = f"{username[:10]} ▾" if username else "Auth* ▾"
            self.btn_auth.setText(label)
            self.btn_auth.setProperty("class", "VarBadgeBtnActive")
        else:
            self.btn_auth.setText("Auth ▾")
            self.btn_auth.setProperty("class", "VarBadgeBtn")
        self.btn_auth.style().unpolish(self.btn_auth)
        self.btn_auth.style().polish(self.btn_auth)

        has_scope = self.popover_scope.has_active_values()
        if has_scope:
            self.btn_scope.setText("Scope* ▾")
            self.btn_scope.setProperty("class", "VarBadgeBtnActive")
        else:
            self.btn_scope.setText("Scope ▾")
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
        self.txt_target.setToolTip(
            t("varbar.target_tip", "Target used to fill variables in copied Cheatsheet commands")
        )
        self.txt_attacker.setToolTip(
            t("varbar.attacker_tip", "LHOST used to fill variables in copied Cheatsheet commands")
        )
        self.btn_auth.setToolTip(
            t("varbar.auth_tip", "Set authentication variables used in copied Cheatsheet commands")
        )
        self.btn_scope.setToolTip(
            t("varbar.scope_tip", "Set scope and environment variables used in copied Cheatsheet commands")
        )
        self.btn_add.setText(t("varbar.add_btn", "Neu"))
        self.btn_add.setToolTip(t("varbar.add_btn_tip", "Neuen Befehl anlegen (Ctrl+N)"))
        self.popover_auth.retranslate()
        self.popover_scope.retranslate()
        self._update_badge_buttons()
        self._apply_collapsed_state()

    # ------------------------------------------------------------------ #
    # IP auto-detection
    # ------------------------------------------------------------------ #

    def auto_detect_ip(self) -> None:
        """Runs the network detector and fills the LHOST if an IP is detected."""
        detected = NetDetector.detect_attacker_ip()
        if detected:
            self.txt_attacker.setText(detected)
            self.btn_auto.setText(detected)
            self.btn_auto.setIcon(icon("fa5s.check", color=STATUS_SUCCESS))
            QTimer.singleShot(2000, self._reset_auto_button)
        else:
            self.btn_auto.setText(t("varbar.no_ip", "Keine IP"))
            QTimer.singleShot(2000, self._reset_auto_button)

    def _reset_auto_button(self) -> None:
        self.btn_auto.setText(t("varbar.auto", "Auto"))
        self.btn_auto.setIcon(icon("fa5s.crosshairs"))

    # ------------------------------------------------------------------ #
    # Data access
    # ------------------------------------------------------------------ #

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

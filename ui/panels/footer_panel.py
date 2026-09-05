from typing import Optional
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QWidget,
)
from PyQt6.QtCore import pyqtSignal, Qt
from core.i18n import t


class FooterPanel(QFrame):
    """
    Bottom HUD status footer.
    Contains quick shortcut hint status, active results item count,
    Always-On-Top toggle, and corner window resize grip.
    """

    always_on_top_toggled = pyqtSignal(bool)
    shortcuts_requested = pyqtSignal()
    phase_menu_requested = pyqtSignal(QPushButton)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("HudFooter")
        self._current_phase_key: Optional[str] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 6, 4)

        # 1. Hotkey Status Hint -> Clean single entry point to Shortcuts overview
        self.btn_shortcuts = QPushButton(t("footer.shortcuts_hint", "Ctrl+/  Shortcuts"), self)
        self.btn_shortcuts.setObjectName("FooterShortcutsBtn")
        self.btn_shortcuts.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_shortcuts.setToolTip(
            t("footer.shortcuts_tip", "Tastenkürzel-Übersicht öffnen (Ctrl+/)")
        )
        self.btn_shortcuts.setStyleSheet(
            """
            QPushButton#FooterShortcutsBtn {
                background-color: transparent;
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 4px;
                color: #8b949e;
                font-size: 11px;
                font-weight: 700;
                font-family: Consolas, "Courier New", monospace;
                padding: 2px 8px;
            }
            QPushButton#FooterShortcutsBtn:hover {
                color: #00e5ff;
                border-color: rgba(0, 229, 255, 0.6);
                background-color: rgba(0, 229, 255, 0.08);
            }
            """
        )
        self.btn_shortcuts.clicked.connect(self.shortcuts_requested.emit)
        layout.addWidget(self.btn_shortcuts)

        layout.addSpacing(6)

        # 2. Phase Dropdown Menu Trigger
        self.btn_phase = QPushButton(t("footer.phase_unassigned", "Phase: Unassigned ▾"), self)
        self.btn_phase.setObjectName("FooterPhaseBtn")
        self.btn_phase.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_phase.setToolTip(
            t("footer.phase_tip", "Aktive Pentest-Phase auswählen (Ctrl+Alt+1..6)")
        )
        self.btn_phase.clicked.connect(lambda: self.phase_menu_requested.emit(self.btn_phase))
        self._apply_phase_button_style(None)
        layout.addWidget(self.btn_phase)

        # Legacy label kept for backward compatibility
        self.lbl_status = QLabel("", self)
        self.lbl_status.setVisible(False)

        layout.addStretch()

        # 2. Item Count Label
        self.lbl_count = QLabel(t("footer.entries_count", "{count} entries", count=0))
        self.lbl_count.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_count.setObjectName("FooterText")
        layout.addWidget(self.lbl_count)

        layout.addSpacing(10)

        # 3. Always On Top Checkbox
        self.chk_always_on_top = QCheckBox(t("footer.always_on_top", "Im Vordergrund"))
        self.chk_always_on_top.setObjectName("AlwaysOnTopCheck")
        self.chk_always_on_top.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_always_on_top.setToolTip(
            t(
                "footer.always_on_top_tip",
                "Overlay immer über allen anderen Fenstern im Vordergrund halten",
            )
        )
        self.chk_always_on_top.toggled.connect(self.always_on_top_toggled.emit)
        layout.addWidget(self.chk_always_on_top)

        # 4. Resizing Grip
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(16, 16)
        layout.addWidget(
            self.size_grip, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight
        )

    def set_count(self, text: str) -> None:
        self.lbl_count.setText(text)

    def set_status(self, text: str) -> None:
        self.lbl_status.setText(text)

    def set_always_on_top(self, checked: bool) -> None:
        self.chk_always_on_top.blockSignals(True)
        self.chk_always_on_top.setChecked(checked)
        self.chk_always_on_top.blockSignals(False)

    def is_always_on_top(self) -> bool:
        return self.chk_always_on_top.isChecked()

    @staticmethod
    def _format_hotkey(hotkey_raw: str) -> str:
        s = (
            hotkey_raw.replace("<ctrl>", "Strg")
            .replace("<cmd>", "Super")
            .replace("<shift>", "Shift")
            .replace("<alt>", "Alt")
            .replace("<space>", "Space")
        )
        parts = [
            p.strip("<>").upper() if len(p.strip("<>")) == 1 else p.strip("<>")
            for p in s.split("+")
            if p.strip()
        ]
        return " + ".join(parts)

    def _apply_phase_button_style(self, phase_key: Optional[str]) -> None:
        if not phase_key:
            self.btn_phase.setStyleSheet(
                """
                QPushButton#FooterPhaseBtn {
                    background-color: transparent;
                    border: 1px solid rgba(0, 229, 255, 0.25);
                    border-radius: 4px;
                    color: #8b949e;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 2px 8px;
                }
                QPushButton#FooterPhaseBtn:hover {
                    color: #00e5ff;
                    border-color: rgba(0, 229, 255, 0.6);
                    background-color: rgba(0, 229, 255, 0.08);
                }
                """
            )
        else:
            self.btn_phase.setStyleSheet(
                """
                QPushButton#FooterPhaseBtn {
                    background-color: rgba(0, 229, 255, 0.12);
                    border: 1px solid #00e5ff;
                    border-radius: 4px;
                    color: #00e5ff;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 2px 8px;
                }
                QPushButton#FooterPhaseBtn:hover {
                    background-color: rgba(0, 229, 255, 0.22);
                    border-color: #00e5ff;
                }
                """
            )

    def set_phase(self, phase_key: Optional[str]) -> None:
        """Updates the footer phase dropdown button text and styling."""
        self._current_phase_key = phase_key
        if not phase_key:
            self.btn_phase.setText(t("footer.phase_unassigned", "Phase: Unassigned ▾"))
        else:
            from core.phases import get_phase

            phase = get_phase(phase_key)
            self.btn_phase.setText(f"{phase.short} ▾")
        self._apply_phase_button_style(phase_key)

    def update_hotkey_display(
        self,
        hotkey_raw: str = "<ctrl>+<alt>+h",
        quit_hotkey_raw: str = "<ctrl>+<alt>+q",
        quick_note_hotkey_raw: str = "<ctrl>+<alt>+n",
        quick_ip_hotkey_raw: str = "<ctrl>+<alt>+i",
        quick_loot_hotkey_raw: str = "<ctrl>+<alt>+l",
    ) -> None:
        self.btn_shortcuts.setText(t("footer.shortcuts_hint", "Ctrl+/  Shortcuts"))
        self.btn_shortcuts.setToolTip(
            t("footer.shortcuts_tip", "Tastenkürzel-Übersicht öffnen (Ctrl+/)")
        )
        self.btn_phase.setToolTip(
            t("footer.phase_tip", "Aktive Pentest-Phase auswählen (Ctrl+Alt+1..6)")
        )
        self.set_phase(self._current_phase_key)
        self.lbl_status.setText(t("footer.shortcuts_hint", "Ctrl+/  Shortcuts"))
        self.chk_always_on_top.setText(t("footer.always_on_top", "Im Vordergrund"))
        self.chk_always_on_top.setToolTip(
            t(
                "footer.always_on_top_tip",
                "Overlay immer über allen anderen Fenstern im Vordergrund halten",
            )
        )

from typing import Optional
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QCheckBox, QSizeGrip, QWidget
from PyQt6.QtCore import pyqtSignal, Qt
from core.i18n import t


class FooterPanel(QFrame):
    """
    Bottom HUD status footer.
    Contains quick shortcut hint status, active results item count,
    Always-On-Top toggle, and corner window resize grip.
    """

    always_on_top_toggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("HudFooter")
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 6, 4)

        # 1. Hotkey Status Hint Label
        self.lbl_status = QLabel(
            t(
                "footer.status",
                "{hotkey}: Toggle | {quit_hotkey}: Quit | Ctrl+P: REC Toggle | Ctrl+S: Snip | Esc: Hide",
                hotkey="Ctrl+Super+<",
                quit_hotkey="Ctrl+Super+Q"
            )
        )
        self.lbl_status.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_status.setObjectName("FooterText")
        layout.addWidget(self.lbl_status)

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
            t("footer.always_on_top_tip", "Overlay immer über allen anderen Fenstern im Vordergrund halten")
        )
        self.chk_always_on_top.toggled.connect(self.always_on_top_toggled.emit)
        layout.addWidget(self.chk_always_on_top)

        # 4. Resizing Grip
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(16, 16)
        layout.addWidget(self.size_grip, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

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
        return (
            hotkey_raw.replace("<ctrl>", "Strg")
            .replace("<cmd>", "Super")
            .replace("<shift>", "Shift")
            .replace("<alt>", "Alt")
            .replace("<", "")
            .replace(">", "")
            .replace("+", " + ")
        )
    def update_hotkey_display(self, hotkey_raw: str, quit_hotkey_raw: str = "<ctrl>+<cmd>+q") -> None:
        hotkey_display = self._format_hotkey(hotkey_raw)
        quit_hotkey_display = self._format_hotkey(quit_hotkey_raw)
        self.lbl_status.setText(
            t("footer.status", "{hotkey}: Toggle | {quit_hotkey}: Quit | Ctrl+P: REC Toggle | Ctrl+S: Snip | Esc: Hide", hotkey=hotkey_display, quit_hotkey=quit_hotkey_display)
        )
        self.chk_always_on_top.setText(t("footer.always_on_top", "Im Vordergrund"))
        self.chk_always_on_top.setToolTip(
            t("footer.always_on_top_tip", "Overlay immer über allen anderen Fenstern im Vordergrund halten")
        )

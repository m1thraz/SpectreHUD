from typing import Optional
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget
from PyQt6.QtCore import pyqtSignal, Qt
from core.i18n import t


class HeaderPanel(QFrame):
    """
    Top HUD navigation and control bar.
    Contains Brand logo, Project/Box selector, Mode Switcher Tabs (Cheatsheet, Loot, History, Report),
    Snip trigger, Clipboard REC indicator, Settings/Options, and Minimize button.
    """

    project_menu_requested = pyqtSignal(QPushButton)
    mode_changed = pyqtSignal(str)
    screenshot_requested = pyqtSignal()
    toggle_rec_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    minimize_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.active_mode = "cheatsheet"
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 10, 6)
        layout.setSpacing(8)

        # Brand Title
        self.lbl_brand = QLabel("SPECTRE // HUD")
        self.lbl_brand.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_brand.setStyleSheet(
            "color: #00e5ff; font-size: 13px; font-weight: 800; letter-spacing: 0.5px; margin-right: 4px;"
        )
        layout.addWidget(self.lbl_brand)

        # Project Selector Button
        self.btn_project = QPushButton("Box: Default ▾")
        self.btn_project.setProperty("class", "ProjectSelectBtn")
        self.btn_project.setToolTip(t("header.project_tip", "Aktives CTF-Projekt / Box wechseln"))
        self.btn_project.clicked.connect(lambda: self.project_menu_requested.emit(self.btn_project))
        layout.addWidget(self.btn_project)

        layout.addSpacing(4)

        # Mode Switcher Tabs
        self.btn_mode_cheatsheet = QPushButton(t("header.mode_cheatsheet", "Cheatsheet"))
        self.btn_mode_cheatsheet.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_cheatsheet.setProperty("class", "ModeSwitchBtnActive")
        self.btn_mode_cheatsheet.clicked.connect(lambda: self.mode_changed.emit("cheatsheet"))
        layout.addWidget(self.btn_mode_cheatsheet)

        self.btn_mode_history = QPushButton(t("header.mode_history", "History"))
        self.btn_mode_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_history.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_history.clicked.connect(lambda: self.mode_changed.emit("history"))
        layout.addWidget(self.btn_mode_history)

        self.btn_mode_loot = QPushButton(t("header.mode_loot", "Loot"))
        self.btn_mode_loot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_loot.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_loot.clicked.connect(lambda: self.mode_changed.emit("loot"))
        layout.addWidget(self.btn_mode_loot)

        self.btn_mode_report = QPushButton(t("header.mode_report", "Report"))
        self.btn_mode_report.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_report.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_report.setToolTip(
            t("header.report_tip", "Editierbaren Markdown-Report des aktiven Projekts öffnen (Ctrl+4)")
        )
        self.btn_mode_report.clicked.connect(lambda: self.mode_changed.emit("report"))
        layout.addWidget(self.btn_mode_report)

        layout.addStretch()

        # Screenshot Snip Button
        self.btn_screenshot = QPushButton(t("header.snip", "Snip"))
        self.btn_screenshot.setProperty("class", "ScreenshotBtn")
        self.btn_screenshot.setToolTip(
            t("header.snip_tip", "Bereichs-Screenshot aufnehmen (Strg+Super+X oder Ctrl+S)")
        )
        self.btn_screenshot.clicked.connect(self.screenshot_requested.emit)
        layout.addWidget(self.btn_screenshot)

        # Clipboard Recording Indicator Button
        self.btn_rec_indicator = QPushButton("REC: Off")
        self.btn_rec_indicator.setObjectName("RecIndicatorBtn")
        self.btn_rec_indicator.setProperty("paused", "true")
        self.btn_rec_indicator.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rec_indicator.setToolTip(
            "Clipboard-Logger ist PAUSIERT (keine Aufzeichnung).\nKlicken oder Ctrl+P zum Starten der Aufzeichnung."
        )
        self.btn_rec_indicator.clicked.connect(self.toggle_rec_requested.emit)
        layout.addWidget(self.btn_rec_indicator)

        # Settings & Hotkeys Button
        self.btn_settings = QPushButton(t("header.opt", "⚙"))
        self.btn_settings.setProperty("class", "ScreenshotBtn")
        self.btn_settings.setToolTip(
            t("header.opt_tip", "Einstellungen & Optionen öffnen (Ctrl+,)")
        )
        self.btn_settings.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.btn_settings)

        # Minimize button in HUD header
        self.btn_minimize = QPushButton("🗕")
        self.btn_minimize.setProperty("class", "MinimizeBtn")
        self.btn_minimize.setToolTip(t("header.minimize_tip", "Overlay minimieren / verstecken (Esc)"))
        self.btn_minimize.clicked.connect(self.minimize_requested.emit)
        layout.addWidget(self.btn_minimize)

    def set_active_mode(self, mode: str) -> None:
        """Updates visual active tab styling for the selected mode."""
        self.active_mode = mode
        self.btn_mode_cheatsheet.setProperty("class", "ModeSwitchBtnActive" if mode == "cheatsheet" else "ModeSwitchBtn")
        self.btn_mode_loot.setProperty("class", "ModeSwitchBtnActive" if mode == "loot" else "ModeSwitchBtn")
        self.btn_mode_history.setProperty("class", "ModeSwitchBtnActive" if mode == "history" else "ModeSwitchBtn")
        self.btn_mode_report.setProperty("class", "ModeSwitchBtnActive" if mode == "report" else "ModeSwitchBtn")

        for btn in [self.btn_mode_cheatsheet, self.btn_mode_loot, self.btn_mode_history, self.btn_mode_report]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_project_title(self, project_name: str) -> None:
        """Updates the project dropdown button text."""
        self.btn_project.setText(f"Box: {project_name} ▾")

    def update_rec_indicator(self, is_active: bool) -> None:
        """Updates the visual indicator for clipboard history recording state."""
        if is_active:
            self.btn_rec_indicator.setText("REC: ON")
            self.btn_rec_indicator.setProperty("paused", "false")
            self.btn_rec_indicator.setToolTip(
                "Clipboard-Logger ist AKTIV (Aufzeichnung läuft).\nKlicken oder Ctrl+P zum Pausieren."
            )
        else:
            self.btn_rec_indicator.setText("REC: Off")
            self.btn_rec_indicator.setProperty("paused", "true")
            self.btn_rec_indicator.setToolTip(
                "Clipboard-Logger ist PAUSIERT (keine Aufzeichnung).\nKlicken oder Ctrl+P zum Starten der Aufzeichnung."
            )
        self.btn_rec_indicator.style().unpolish(self.btn_rec_indicator)
        self.btn_rec_indicator.style().polish(self.btn_rec_indicator)

    def retranslate(self) -> None:
        """Dynamically re-translates all texts on language changes."""
        self.btn_mode_cheatsheet.setText(t("header.mode_cheatsheet", "Cheatsheet"))
        self.btn_mode_loot.setText(t("header.mode_loot", "Loot"))
        self.btn_mode_history.setText(t("header.mode_history", "History"))
        self.btn_mode_report.setText(t("header.mode_report", "Report"))
        self.btn_mode_report.setToolTip(
            t("header.report_tip", "Editierbaren Markdown-Report des aktiven Projekts öffnen (Ctrl+4)")
        )
        self.btn_screenshot.setText(t("header.snip", "Snip"))
        self.btn_screenshot.setToolTip(
            t("header.snip_tip", "Bereichs-Screenshot aufnehmen (Strg+Super+X oder Ctrl+S)")
        )
        self.btn_settings.setText(t("header.opt", "⚙"))
        self.btn_settings.setToolTip(
            t("header.opt_tip", "Einstellungen & Optionen öffnen (Ctrl+,)")
        )
        self.btn_minimize.setToolTip(t("header.minimize_tip", "Overlay minimieren / verstecken (Esc)"))
        self.btn_project.setToolTip(t("header.project_tip", "Aktives CTF-Projekt / Box wechseln"))

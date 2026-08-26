import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QScrollArea, QFrame, QLabel, QPushButton, QMessageBox, 
    QApplication, QSizeGrip, QCheckBox
)
from PyQt6.QtCore import Qt, QPoint, QRect, QEvent
from PyQt6.QtGui import QKeySequence, QShortcut, QGuiApplication, QMouseEvent

from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
from core.screenshot_manager import ScreenshotManager
from core.project_session_service import ProjectSessionService
from core.report_file_manager import ReportFileManager
from core.logger import get_logger

from ui.variable_bar import VariableBar
from ui.search_bar import SearchBar
from ui.settings_dialog import SettingsDialog
from ui.styles import CYBER_DARK_QSS
from ui.controllers import (
    WindowFrameManager,
    CheatsheetController,
    LootController,
    HistoryController,
    ReportController,
    ProjectController
)

logger = get_logger("main_window")

EXPORT_COPY_TOOLTIP = (
    "Erstellt eine neue Kopie basierend auf dem aktuellen Loot. "
    "Für die bearbeitbare Version siehe Report-Tab."
)


class MainWindow(QMainWindow):
    """Sleek, frameless, resizable Spotlight-style HUD Overlay coordinator for Cheatsheets, Session Loot, History & Workspaces."""

    def __init__(
        self, 
        config_manager: ConfigManager, 
        snippet_manager: SnippetManager, 
        loot_manager: Optional[LootManager] = None,
        clipboard_watcher: Optional[ClipboardWatcher] = None,
        project_manager: Optional[ProjectManager] = None,
        screenshot_manager: Optional[ScreenshotManager] = None
    ):
        super().__init__()
        self.config = config_manager
        self.snippet_manager = snippet_manager
        self.project_manager = project_manager if project_manager is not None else ProjectManager()
        self.loot_manager = loot_manager if loot_manager is not None else LootManager()
        self.clipboard_watcher = clipboard_watcher if clipboard_watcher is not None else ClipboardWatcher()
        self.screenshot_manager = screenshot_manager if screenshot_manager is not None else ScreenshotManager()

        # Domain Session Service
        self.session_service = ProjectSessionService(
            project_manager=self.project_manager,
            loot_manager=self.loot_manager,
            clipboard_watcher=self.clipboard_watcher
        )

        self.screenshot_manager.screenshot_saved.connect(self._on_screenshot_saved)
        
        # Connect watcher target provider & listener
        self.clipboard_watcher.set_target_provider(lambda: self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else "")
        self.clipboard_watcher.entry_added.connect(self._on_clipboard_entry_added)

        self.active_mode = "cheatsheet"  # 'cheatsheet', 'loot', 'history', or 'report'
        self.cards: List[QWidget] = []

        # Initialize Controllers
        self.frame_manager = WindowFrameManager(self, self.config)
        self.cheatsheet_ctrl = CheatsheetController(self.snippet_manager, parent=self)
        self.loot_ctrl = LootController(self.loot_manager, self.project_manager, parent=self)
        self.history_ctrl = HistoryController(self.clipboard_watcher, self.loot_manager, self.project_manager, parent=self)
        self.report_ctrl = ReportController(self.project_manager, self.loot_manager, self.clipboard_watcher, parent_widget=self)
        self.project_ctrl = ProjectController(self.project_manager, parent=self)

        # Controller Signal Connections
        self.cheatsheet_ctrl.snippets_updated.connect(self._on_data_updated)
        self.loot_ctrl.loot_updated.connect(self._on_loot_data_updated)
        self.history_ctrl.history_updated.connect(self._on_history_data_updated)

        self._init_window()
        self._init_ui()
        self._setup_shortcuts()
        
        # Load initial active project state
        self._load_active_project_state()
        
        self.refresh_filter_pills()
        self.refresh_content()
        self._center_on_screen()

    # --- Backward compatibility properties for controllers & tests ---
    @property
    def filter_buttons(self) -> Dict[str, QPushButton]:
        if self.active_mode == "cheatsheet":
            return self.cheatsheet_ctrl.filter_buttons
        elif self.active_mode == "loot":
            return self.loot_ctrl.filter_buttons
        elif self.active_mode == "history":
            return self.history_ctrl.filter_buttons
        return {}

    @property
    def current_category_id(self) -> str:
        return self.cheatsheet_ctrl.current_category_id

    @current_category_id.setter
    def current_category_id(self, val: str) -> None:
        self.cheatsheet_ctrl.current_category_id = val

    @property
    def current_loot_type(self) -> str:
        return self.loot_ctrl.current_loot_type

    @current_loot_type.setter
    def current_loot_type(self, val: str) -> None:
        self.loot_ctrl.current_loot_type = val

    @property
    def current_history_filter(self) -> str:
        return self.history_ctrl.current_history_filter

    @current_history_filter.setter
    def current_history_filter(self, val: str) -> None:
        self.history_ctrl.current_history_filter = val

    @property
    def report_file_manager(self) -> ReportFileManager:
        return self.report_ctrl.report_file_manager

    @property
    def report_editor_tab(self):
        return self.report_ctrl.get_tab_widget()

    # -------------------------------------------------------------
    # Window & UI Setup
    # -------------------------------------------------------------
    def _init_window(self) -> None:
        self.setWindowTitle("SpectreHUD")
        w = int(self.config.get("window_width", 900))
        h = int(self.config.get("window_height", 640))
        self.resize(w, h)
        self.setMinimumSize(740, 480)
        self.setMouseTracking(True)
        
        is_always_on_top = self.config.get("always_on_top", True)
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if is_always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(CYBER_DARK_QSS)

    def _init_ui(self) -> None:
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        central_widget.setMouseTracking(True)
        self.setCentralWidget(central_widget)

        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(0)

        # Main HUD Glass Frame
        self.hud_frame = QFrame()
        self.hud_frame.setObjectName("HudFrame")
        self.hud_frame.setMouseTracking(True)
        
        hud_layout = QVBoxLayout(self.hud_frame)
        hud_layout.setContentsMargins(0, 0, 0, 0)
        hud_layout.setSpacing(0)

        # 1. Header Bar
        self.header_bar = QFrame()
        self.header_bar.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(12, 6, 10, 6)
        header_layout.setSpacing(8)

        lbl_brand = QLabel("SPECTRE // HUD")
        lbl_brand.setStyleSheet("color: #00e5ff; font-size: 13px; font-weight: 800; letter-spacing: 0.5px; margin-right: 4px;")
        header_layout.addWidget(lbl_brand)

        # Project Selector Button
        active_proj = self.project_manager.get_active_project()
        self.btn_project = QPushButton(f"Box: {active_proj} ▾")
        self.btn_project.setProperty("class", "ProjectSelectBtn")
        self.btn_project.setToolTip("Aktives CTF-Projekt / Box wechseln")
        self.btn_project.clicked.connect(self._show_project_menu)
        header_layout.addWidget(self.btn_project)

        header_layout.addSpacing(4)

        # Mode Switcher Tabs
        self.btn_mode_cheatsheet = QPushButton("Cheatsheet")
        self.btn_mode_cheatsheet.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_cheatsheet.setProperty("class", "ModeSwitchBtnActive")
        self.btn_mode_cheatsheet.clicked.connect(lambda: self.switch_mode("cheatsheet"))
        header_layout.addWidget(self.btn_mode_cheatsheet)

        self.btn_mode_loot = QPushButton("Loot")
        self.btn_mode_loot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_loot.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_loot.clicked.connect(lambda: self.switch_mode("loot"))
        header_layout.addWidget(self.btn_mode_loot)

        self.btn_mode_history = QPushButton("History")
        self.btn_mode_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_history.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_history.clicked.connect(lambda: self.switch_mode("history"))
        header_layout.addWidget(self.btn_mode_history)

        self.btn_mode_report = QPushButton("Report")
        self.btn_mode_report.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_report.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_report.setToolTip("Editierbaren Markdown-Report des aktiven Projekts öffnen (Ctrl+4)")
        self.btn_mode_report.clicked.connect(lambda: self.switch_mode("report"))
        header_layout.addWidget(self.btn_mode_report)

        header_layout.addStretch()

        # Screenshot Snip Button
        self.btn_screenshot = QPushButton("Snip")
        self.btn_screenshot.setProperty("class", "ScreenshotBtn")
        self.btn_screenshot.setToolTip("Bereichs-Screenshot aufnehmen (Strg+Super+X oder Ctrl+S)")
        self.btn_screenshot.clicked.connect(self.trigger_screenshot)
        header_layout.addWidget(self.btn_screenshot)

        # Clipboard Recording Indicator Button
        self.btn_rec_indicator = QPushButton("REC: Off")
        self.btn_rec_indicator.setObjectName("RecIndicatorBtn")
        self.btn_rec_indicator.setProperty("paused", "true")
        self.btn_rec_indicator.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rec_indicator.setToolTip("Clipboard-Logger ist PAUSIERT (keine Aufzeichnung).\nKlicken oder Ctrl+P zum Starten der Aufzeichnung.")
        self.btn_rec_indicator.clicked.connect(self._toggle_pause_history)
        header_layout.addWidget(self.btn_rec_indicator)

        # Settings & Hotkeys Button
        self.btn_settings = QPushButton("Opt")
        self.btn_settings.setProperty("class", "ScreenshotBtn")
        self.btn_settings.setToolTip("Optionen, Sprache & Hotkeys öffnen (Ctrl+,)")
        self.btn_settings.clicked.connect(self.open_settings_dialog)
        header_layout.addWidget(self.btn_settings)

        # Close button in HUD header
        btn_close = QPushButton("✕")
        btn_close.setProperty("class", "DangerBtn")
        btn_close.setToolTip("Overlay schließen (Esc)")
        btn_close.clicked.connect(self.hide)
        header_layout.addWidget(btn_close)

        hud_layout.addWidget(self.header_bar)

        # 2. Spotlight Search Bar
        self.search_bar = SearchBar()
        self.search_bar.search_changed.connect(self._on_search_changed)
        hud_layout.addWidget(self.search_bar)

        # 3. Filter Pills Bar
        self.pills_frame = QFrame()
        self.pills_frame.setObjectName("FilterPillsFrame")
        self.pills_layout = QHBoxLayout(self.pills_frame)
        self.pills_layout.setContentsMargins(12, 2, 12, 6)
        self.pills_layout.setSpacing(6)
        hud_layout.addWidget(self.pills_frame)

        # 4. Variable Bar
        initial_vars = {
            "target_ip": self.config.get("target_ip", "10.10.10.10"),
            "attacker_ip": self.config.get("attacker_ip", "10.10.14.5"),
            "port": self.config.get("port", "4444"),
            "wordlist": self.config.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        }
        self.var_bar = VariableBar(initial_vars)
        self.var_bar.variables_changed.connect(self._on_variables_changed)
        self.var_bar.add_snippet_clicked.connect(self._on_add_button_clicked)
        hud_layout.addWidget(self.var_bar)

        # 4b. Privacy Warning Banner for History Mode
        self.privacy_banner = QFrame()
        self.privacy_banner.setObjectName("PrivacyWarningBanner")
        banner_layout = QHBoxLayout(self.privacy_banner)
        banner_layout.setContentsMargins(10, 4, 10, 4)
        lbl_warn = QLabel("Datenschutz-Hinweis: Kopierte Passwörter oder persönliche Daten werden protokolliert, solange REC aktiv ist (Pausieren mit Ctrl+P oder Klick auf REC: ON).")
        lbl_warn.setObjectName("PrivacyWarningText")
        lbl_warn.setWordWrap(True)
        banner_layout.addWidget(lbl_warn)
        self.privacy_banner.setVisible(False)
        hud_layout.addWidget(self.privacy_banner)

        # 5. Scrollable Content Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("MainScrollArea")
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(12, 8, 12, 8)
        self.content_layout.setSpacing(6)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.content_container)
        hud_layout.addWidget(self.scroll_area, stretch=1)

        # 6. HUD Footer
        self.footer_frame = QFrame()
        self.footer_frame.setObjectName("HudFooter")
        footer_layout = QHBoxLayout(self.footer_frame)
        footer_layout.setContentsMargins(14, 4, 6, 4)

        hotkey_raw = self.config.get("hotkey", "<ctrl>+<cmd>+<")
        hotkey_display = hotkey_raw.replace("<ctrl>", "Strg").replace("<cmd>", "Super").replace("<shift>", "Shift").replace("<alt>", "Alt").replace("<", "").replace(">", "").replace("+", " + ")
        self.lbl_status = QLabel(f"{hotkey_display}: Toggle | Strg+Super+Q: Beenden | Ctrl+P: REC Toggle | Ctrl+S: Snip | Esc: Verstecken")
        self.lbl_status.setObjectName("FooterText")
        footer_layout.addWidget(self.lbl_status)

        footer_layout.addStretch()

        self.lbl_count = QLabel("0 Einträge")
        self.lbl_count.setObjectName("FooterText")
        footer_layout.addWidget(self.lbl_count)

        footer_layout.addSpacing(10)

        # Always on Top Toggle
        is_always_on_top = self.config.get("always_on_top", True)
        self.chk_always_on_top = QCheckBox("Im Vordergrund")
        self.chk_always_on_top.setObjectName("AlwaysOnTopCheck")
        self.chk_always_on_top.setChecked(is_always_on_top)
        self.chk_always_on_top.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_always_on_top.setToolTip("Overlay immer über allen anderen Fenstern im Vordergrund halten")
        self.chk_always_on_top.toggled.connect(self._on_always_on_top_toggled)
        footer_layout.addWidget(self.chk_always_on_top)

        # Resizing Grip
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(16, 16)
        footer_layout.addWidget(self.size_grip, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        hud_layout.addWidget(self.footer_frame)
        outer_layout.addWidget(self.hud_frame)

        # Install event filter for universal border resizing and drag-moving
        self.frame_manager.install_on([
            self.hud_frame, self.header_bar, self.pills_frame, 
            self.footer_frame, self.var_bar, self.content_container, 
            self.scroll_area, central_widget
        ])

        # Connect clipboard logging state listener
        self.clipboard_watcher.logging_state_changed.connect(self._on_logging_state_changed)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Esc"), self, activated=self.hide)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_bar.set_focus)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._on_add_button_clicked)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.trigger_screenshot)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self._toggle_pause_history)
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=QApplication.quit)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings_dialog)
        QShortcut(QKeySequence("Tab"), self, activated=self.toggle_mode)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self.switch_mode("cheatsheet"))
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.switch_mode("loot"))
        QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self.switch_mode("history"))
        QShortcut(QKeySequence("Ctrl+4"), self, activated=lambda: self.switch_mode("report"))

    def open_settings_dialog(self) -> None:
        """Opens the modular settings and options dialog."""
        dlg = SettingsDialog(self.config, parent=self)
        dlg.settings_applied.connect(self._on_settings_applied)
        dlg.exec()

    def _on_settings_applied(self, new_settings: Dict[str, Any]) -> None:
        """Applies updated configuration settings at runtime."""
        if "always_on_top" in new_settings:
            is_top = bool(new_settings["always_on_top"])
            self.chk_always_on_top.setChecked(is_top)

        hotkey_raw = self.config.get("hotkey", "<ctrl>+<cmd>+<")
        hotkey_display = hotkey_raw.replace("<ctrl>", "Strg").replace("<cmd>", "Super").replace("<shift>", "Shift").replace("<alt>", "Alt").replace("<", "").replace(">", "").replace("+", " + ")
        self.lbl_status.setText(f"{hotkey_display}: Toggle | Strg+Super+Q: Beenden | Ctrl+P: REC Toggle | Ctrl+S: Snip | Esc: Verstecken")

    # -------------------------------------------------------------
    # Navigation & Mode Switching
    # -------------------------------------------------------------
    def switch_mode(self, mode: str) -> None:
        """Switches between 'cheatsheet', 'loot', 'history', and 'report' modes."""
        if self.active_mode == "report" and mode != "report":
            if not self.report_ctrl.confirm_discard_if_dirty():
                return

        self.active_mode = mode
        
        self.btn_mode_cheatsheet.setProperty("class", "ModeSwitchBtnActive" if mode == "cheatsheet" else "ModeSwitchBtn")
        self.btn_mode_loot.setProperty("class", "ModeSwitchBtnActive" if mode == "loot" else "ModeSwitchBtn")
        self.btn_mode_history.setProperty("class", "ModeSwitchBtnActive" if mode == "history" else "ModeSwitchBtn")
        self.btn_mode_report.setProperty("class", "ModeSwitchBtnActive" if mode == "report" else "ModeSwitchBtn")

        self.privacy_banner.setVisible(mode == "history")
        self.search_bar.setVisible(mode != "report")
        self.pills_frame.setVisible(mode != "report")
        self.var_bar.setVisible(mode != "report")

        if mode == "cheatsheet":
            self.search_bar.txt_search.setPlaceholderText("Search commands, tools or syntax (e.g. 'curl', 'nmap', 'sql')...")
        elif mode == "loot":
            self.search_bar.txt_search.setPlaceholderText("Search session loot, credentials, hashes & notes...")
        elif mode == "history":
            self.search_bar.txt_search.setPlaceholderText("Search clipboard history, commands & outputs...")

        for btn in [self.btn_mode_cheatsheet, self.btn_mode_loot, self.btn_mode_history, self.btn_mode_report]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.refresh_filter_pills()
        self.refresh_content()
        if mode != "report":
            self.search_bar.set_focus()

    def toggle_mode(self) -> None:
        """Cycles through modes via Tab shortcut (Report mode excluded from Tab cycle)."""
        modes = ["cheatsheet", "loot", "history"]
        idx = modes.index(self.active_mode) if self.active_mode in modes else 0
        next_mode = modes[(idx + 1) % len(modes)]
        self.switch_mode(next_mode)

    # -------------------------------------------------------------
    # Content & Filter Rendering
    # -------------------------------------------------------------
    def refresh_filter_pills(self) -> None:
        """Populates horizontal filter pills and contextual actions depending on active mode."""
        while self.pills_layout.count():
            child = self.pills_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if self.active_mode == "report":
            return

        if self.active_mode == "cheatsheet":
            self.cheatsheet_ctrl.build_filter_pills(
                self.pills_layout, self._select_category
            )
        elif self.active_mode == "loot":
            self.loot_ctrl.build_filter_pills(
                self.pills_layout, self._select_loot_type,
                self._export_loot, self._clear_loot, EXPORT_COPY_TOOLTIP
            )
        else:
            self.history_ctrl.build_filter_pills(
                self.pills_layout, self._select_history_filter,
                self._export_report, self._clear_history, EXPORT_COPY_TOOLTIP
            )

    def refresh_content(self) -> None:
        """Rebuilds scrollable cards or displays ReportEditorTab based on active mode and query."""
        if self.active_mode == "report":
            self.cards = self.report_ctrl.render_content(self.content_layout)
            self.lbl_count.setText("Report Editor")
            return

        self.report_ctrl.detach_tab_if_needed(self.content_layout)

        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.cards.clear()

        query = self.search_bar.get_text()
        variables = self.var_bar.get_variables() if hasattr(self, 'var_bar') else {}

        if self.active_mode == "cheatsheet":
            self.cards = self.cheatsheet_ctrl.render_content(
                self.content_layout, query, variables,
                self._on_snippet_deleted, self, self._show_empty_state
            )
            self.lbl_count.setText(f"{len(self.cards)} Befehle")
        elif self.active_mode == "loot":
            active_proj = self.project_manager.get_active_project()
            proj_dir = self.project_manager.get_project_dir(active_proj)
            self.cards = self.loot_ctrl.render_content(
                self.content_layout, query, proj_dir,
                self._on_loot_deleted, self._on_edit_loot_requested,
                self, self._show_empty_state
            )
            self.lbl_count.setText(f"{len(self.cards)} Loot-Einträge")
        else:
            target_ip = variables.get("target_ip")
            self.cards = self.history_ctrl.render_content(
                self.content_layout, query, target_ip,
                self._on_history_add_to_loot, self._on_history_entry_deleted,
                self, self._show_empty_state
            )
            self.lbl_count.setText(f"{len(self.cards)} Verlaufseinträge")

    def _show_empty_state(self, message: str) -> None:
        empty_lbl = QLabel(message)
        empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_lbl.setStyleSheet("color: #6e7681; font-size: 13px; font-style: italic; padding: 40px 20px;")
        empty_lbl.setWordWrap(True)
        self.content_layout.addWidget(empty_lbl)

    # -------------------------------------------------------------
    # Action & Event Callbacks
    # -------------------------------------------------------------
    def _select_category(self, category_id: str) -> None:
        self.cheatsheet_ctrl.select_category(category_id)
        self.refresh_content()

    def _select_loot_type(self, type_id: str) -> None:
        self.loot_ctrl.select_loot_type(type_id)
        self.refresh_content()

    def _select_history_filter(self, filter_id: str) -> None:
        self.history_ctrl.select_history_filter(filter_id)
        self.refresh_content()

    def _on_search_changed(self, text: str) -> None:
        self.refresh_content()

    def _on_variables_changed(self, vars_dict: Dict[str, str]) -> None:
        if self.active_mode == "cheatsheet":
            self.cheatsheet_ctrl.update_variables(self.cards, vars_dict)

    def _on_add_button_clicked(self) -> None:
        if self.active_mode == "cheatsheet":
            if self.cheatsheet_ctrl.open_add_dialog(self):
                self.refresh_filter_pills()
                self.refresh_content()
        elif self.active_mode == "loot":
            target_ip = self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else ""
            if self.loot_ctrl.open_add_dialog(self, target_ip=target_ip):
                self._save_current_project_state()
                self.refresh_filter_pills()
                self.refresh_content()
        else:
            target_ip = self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else ""
            if self.loot_ctrl.open_add_dialog(self, target_ip=target_ip, default_type="note", default_category="recon"):
                self._save_current_project_state()
                self.refresh_filter_pills()
                self.refresh_content()

    def _on_edit_loot_requested(self, entry: Dict[str, Any]) -> None:
        if self.loot_ctrl.open_edit_dialog(self, entry):
            self._save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _on_snippet_deleted(self, snippet_id: str) -> None:
        self.cheatsheet_ctrl.delete_snippet(snippet_id)
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_loot_deleted(self, loot_id: str) -> None:
        self.loot_ctrl.delete_loot(loot_id)
        self._save_current_project_state()
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_clipboard_entry_added(self, entry: Dict[str, Any]) -> None:
        if self.active_mode == "history":
            self.refresh_filter_pills()
            self.refresh_content()
        self._save_current_project_state()

    def _on_history_entry_deleted(self, entry_id: str) -> None:
        self.history_ctrl.delete_entry(entry_id)
        self._save_current_project_state()
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_history_add_to_loot(self, history_item: Dict[str, Any]) -> None:
        target_ip = history_item.get("target_ip") or (self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else "")
        if self.loot_ctrl.open_add_dialog(
            parent_widget=self,
            target_ip=target_ip,
            default_type="credentials" if history_item.get("is_command") else "note",
            default_category="access" if history_item.get("is_command") else "recon",
            default_title=f"Kopiert aus Terminal ({history_item.get('timestamp', '')})",
            default_content=history_item.get("text", "")
        ):
            self._save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _clear_loot(self) -> None:
        if self.loot_ctrl.clear_loot(self):
            self._save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _clear_history(self) -> None:
        if self.history_ctrl.clear_history(self):
            self._save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _export_loot(self) -> None:
        self._export_report()

    def _export_report(self) -> None:
        target_ip = self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else ""
        active_proj = self.project_manager.get_active_project()
        self.history_ctrl.export_report(self, target_ip, active_proj)

    def _toggle_pause_history(self) -> None:
        self.history_ctrl.toggle_pause()

    def _on_logging_state_changed(self, is_active: bool) -> None:
        self.history_ctrl.update_rec_indicator(self.btn_rec_indicator, is_active)

    def _on_data_updated(self) -> None:
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_loot_data_updated(self) -> None:
        self._save_current_project_state()
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_history_data_updated(self) -> None:
        self._save_current_project_state()
        self.refresh_filter_pills()
        self.refresh_content()

    # -------------------------------------------------------------
    # Project Management
    # -------------------------------------------------------------
    def _show_project_menu(self) -> None:
        self.project_ctrl.show_project_menu(
            self.btn_project, self._switch_to_project, self._open_new_project_dialog, self
        )

    def _open_new_project_dialog(self) -> None:
        curr_target = self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else ""
        curr_attacker = self.var_bar.txt_attacker.text().strip() if hasattr(self, 'var_bar') else ""
        curr_port = self.var_bar.txt_port.text().strip() if hasattr(self, 'var_bar') else "4444"

        self.project_ctrl.open_new_project_dialog(
            self, curr_target, curr_attacker, curr_port, self._switch_to_project
        )

    def _load_active_project_state(self) -> None:
        active_proj = self.project_manager.get_active_project()
        self.btn_project.setText(f"Box: {active_proj} ▾")

        state = self.session_service.load_project_session(active_proj)
        if hasattr(self, 'var_bar') and self.var_bar:
            self.var_bar.txt_target.blockSignals(True)
            self.var_bar.txt_attacker.blockSignals(True)
            self.var_bar.txt_port.blockSignals(True)

            self.var_bar.txt_target.setText(state.get("target_ip", "10.10.10.10"))
            self.var_bar.txt_attacker.setText(state.get("attacker_ip", "10.10.14.5"))
            self.var_bar.txt_port.setText(state.get("port", "4444"))

            self.var_bar.txt_target.blockSignals(False)
            self.var_bar.txt_attacker.blockSignals(False)
            self.var_bar.txt_port.blockSignals(False)

    def _save_current_project_state(self) -> None:
        variables = self.var_bar.get_variables() if hasattr(self, 'var_bar') else {}
        self.session_service.save_project_session(variables)

    def _switch_to_project(self, project_name: str) -> None:
        if project_name == self.project_manager.get_active_project():
            return
        
        if not self.report_ctrl.confirm_discard_if_dirty():
            return

        self._save_current_project_state()
        self.project_manager.set_active_project(project_name)
        self._load_active_project_state()
        self.report_ctrl.load_project(project_name)
        self.refresh_filter_pills()
        self.refresh_content()

    # -------------------------------------------------------------
    # Screenshot & Window Visibility
    # -------------------------------------------------------------
    def trigger_screenshot(self) -> None:
        target_ip = self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else ""
        self.screenshot_manager.start_capture(self, self.project_manager, self.loot_manager, target_ip=target_ip)

    def _on_screenshot_saved(self, loot_entry: Dict[str, Any]) -> None:
        self._save_current_project_state()
        self.switch_mode("loot")

    def _center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2 + geo.x()
            y = max(geo.y() + 60, (geo.height() - self.height()) // 3 + geo.y())
            self.move(x, y)

    def _on_always_on_top_toggled(self, checked: bool) -> None:
        self.config.set("always_on_top", checked)
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()
            self.raise_()
            self.activateWindow()

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.show()
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            self.raise_()
            self.activateWindow()
            self.search_bar.set_focus()

    # -------------------------------------------------------------
    # Event Overrides Delegated to FrameManager
    # -------------------------------------------------------------
    def _get_resize_edge(self, pos: QPoint) -> str:
        return self.frame_manager.get_resize_edge(pos)

    def closeEvent(self, event) -> None:
        if not self.report_ctrl.confirm_discard_if_dirty():
            event.ignore()
            return
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.config.set("window_width", self.width())
        self.config.set("window_height", self.height())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.frame_manager.handle_mouse_press(event):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self.frame_manager.handle_mouse_move(event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if not self.frame_manager.handle_mouse_release(event):
            super().mouseReleaseEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self.frame_manager.handle_leave(event)
        super().leaveEvent(event)

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QScrollArea, QFrame, QLabel, QPushButton, QMessageBox, 
    QFileDialog, QMenu, QApplication, QSizeGrip, QCheckBox
)
from PyQt6.QtCore import Qt, QPoint, QRect, QEvent, pyqtSlot
from PyQt6.QtGui import QKeySequence, QShortcut, QGuiApplication, QMouseEvent, QAction
from typing import Dict, Any, List, Optional

from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager, LOOT_TYPES
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
from core.screenshot_manager import ScreenshotManager
from core.report_builder import ReportBuilder
from core.report_file_manager import ReportFileManager
from ui.report_editor_tab import ReportEditorTab
from ui.variable_bar import VariableBar
from ui.search_bar import SearchBar
from ui.snippet_card import SnippetCard
from ui.loot_card import LootCard
from ui.history_card import HistoryCard
from ui.add_snippet_dialog import AddSnippetDialog
from ui.add_loot_dialog import AddLootDialog
from ui.project_dialog import NewProjectDialog
from ui.styles import CYBER_DARK_QSS
from core.logger import get_logger

logger = get_logger("main_window")

RESIZE_MARGIN = 20
CORNER_MARGIN = 32

def _is_interactive_widget(widget: Optional[QWidget]) -> bool:
    """Checks if a widget or its parents are interactive controls (buttons, inputs, sliders, grips)."""
    if widget is None:
        return False
    from PyQt6.QtWidgets import (
        QAbstractButton, QLineEdit, QTextEdit, QPlainTextEdit, 
        QComboBox, QScrollBar, QAbstractSlider, QMenu, QSizeGrip
    )
    curr = widget
    while curr is not None and not isinstance(curr, MainWindow):
        if isinstance(curr, (QAbstractButton, QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QScrollBar, QAbstractSlider, QMenu, QSizeGrip)):
            return True
        if isinstance(curr, QLabel) and curr.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse:
            return True
        curr = curr.parentWidget()
    return False

class MainWindow(QMainWindow):
    """Sleek, frameless, resizable Spotlight-style HUD Overlay for Cheatsheets, Session Loot, History & Workspaces."""

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
        
        self.screenshot_manager.screenshot_saved.connect(self._on_screenshot_saved)
        
        # Connect watcher target provider
        self.clipboard_watcher.set_target_provider(lambda: self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else "")
        self.clipboard_watcher.entry_added.connect(self._on_clipboard_entry_added)

        self.active_mode = "cheatsheet"  # 'cheatsheet', 'loot', 'history', or 'report'
        self.current_category_id = "all"
        self.current_loot_type = "all"
        self.current_history_filter = "all"
        
        self.cards: List[QWidget] = []
        self.filter_buttons: Dict[str, QPushButton] = {}
        
        # Report File Manager & Editor Tab
        self.report_file_manager = ReportFileManager(self.project_manager)
        self.report_editor_tab = ReportEditorTab(
            self.report_file_manager, self.loot_manager, self.clipboard_watcher, parent=self
        )
        self.report_editor_tab.load_project(self.project_manager.get_active_project())

        # Window moving and resizing state
        self._is_resizing = False
        self._resize_edge = ""
        self._resize_start_pos = QPoint()
        self._resize_start_geo = QRect()
        self._is_moving = False
        self._drag_pos = QPoint()

        self._init_window()
        self._init_ui()
        self._setup_shortcuts()
        
        # Load initial active project state
        self._load_active_project_state()
        
        self.refresh_filter_pills()
        self.refresh_content()
        self._center_on_screen()

    def _init_window(self) -> None:
        self.setWindowTitle("SpectreHUD")
        w = int(self.config.get("window_width", 900))
        h = int(self.config.get("window_height", 640))
        self.resize(w, h)
        self.setMinimumSize(740, 480)
        self.setMouseTracking(True)
        
        is_always_on_top = self.config.get("always_on_top", True)
        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
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

        # 1. Clean Top Header Row: Brand + Project Selector + Mode Switcher + Tools
        self.header_bar = QFrame()
        self.header_bar.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(12, 6, 10, 6)
        header_layout.setSpacing(8)

        # SpectreHUD Brand Badge
        lbl_brand = QLabel("👻 SpectreHUD")
        lbl_brand.setStyleSheet("color: #00e5ff; font-size: 13px; font-weight: 800; letter-spacing: 0.5px; margin-right: 4px;")
        header_layout.addWidget(lbl_brand)

        # Project / Box Selector Dropdown Button
        active_proj = self.project_manager.get_active_project()
        self.btn_project = QPushButton(f"📁 Box: {active_proj} ▾")
        self.btn_project.setProperty("class", "ProjectSelectBtn")
        self.btn_project.setToolTip("Aktives CTF-Projekt / Box wechseln")
        self.btn_project.clicked.connect(self._show_project_menu)
        header_layout.addWidget(self.btn_project)

        header_layout.addSpacing(4)

        # Mode Switcher Tabs
        self.btn_mode_cheatsheet = QPushButton("⚡ Cheatsheet")
        self.btn_mode_cheatsheet.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_cheatsheet.setProperty("class", "ModeSwitchBtnActive")
        self.btn_mode_cheatsheet.clicked.connect(lambda: self.switch_mode("cheatsheet"))
        header_layout.addWidget(self.btn_mode_cheatsheet)

        self.btn_mode_loot = QPushButton("📝 Loot")
        self.btn_mode_loot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_loot.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_loot.clicked.connect(lambda: self.switch_mode("loot"))
        header_layout.addWidget(self.btn_mode_loot)

        self.btn_mode_history = QPushButton("📜 History")
        self.btn_mode_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_history.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_history.clicked.connect(lambda: self.switch_mode("history"))
        header_layout.addWidget(self.btn_mode_history)

        self.btn_mode_report = QPushButton("📊 Report")
        self.btn_mode_report.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_report.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_report.setToolTip("Editierbaren Markdown-Report des aktiven Projekts öffnen (Ctrl+4)")
        self.btn_mode_report.clicked.connect(lambda: self.switch_mode("report"))
        header_layout.addWidget(self.btn_mode_report)

        header_layout.addStretch()

        # Screenshot Snip Button
        self.btn_screenshot = QPushButton("📷 Snip")
        self.btn_screenshot.setProperty("class", "ScreenshotBtn")
        self.btn_screenshot.setToolTip("Bereichs-Screenshot aufnehmen (Strg+Super+X oder Ctrl+S)")
        self.btn_screenshot.clicked.connect(self.trigger_screenshot)
        header_layout.addWidget(self.btn_screenshot)

        # Clipboard Recording Indicator Button (Default: PAUSED for privacy)
        self.btn_rec_indicator = QPushButton("⏸️ REC: Aus")
        self.btn_rec_indicator.setObjectName("RecIndicatorBtn")
        self.btn_rec_indicator.setProperty("paused", "true")
        self.btn_rec_indicator.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rec_indicator.setToolTip("Clipboard-Logger ist PAUSIERT (keine Aufzeichnung).\nKlicken oder Ctrl+P zum Starten der Aufzeichnung.")
        self.btn_rec_indicator.clicked.connect(self._toggle_pause_history)
        header_layout.addWidget(self.btn_rec_indicator)

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

        # 3. Horizontal Filter Pills & Contextual Actions Bar
        self.pills_frame = QFrame()
        self.pills_frame.setObjectName("FilterPillsFrame")
        self.pills_layout = QHBoxLayout(self.pills_frame)
        self.pills_layout.setContentsMargins(12, 2, 12, 6)
        self.pills_layout.setSpacing(6)
        hud_layout.addWidget(self.pills_frame)

        # Instantiate Contextual Action Buttons
        self.btn_export_loot = QPushButton("💾 Export (.md)")
        self.btn_export_loot.setProperty("class", "MiniActionBtn")
        self.btn_export_loot.setToolTip("Erstellt eine neue Kopie basierend auf dem aktuellen Loot. Für die bearbeitbare Version siehe Report-Tab.")
        self.btn_export_loot.clicked.connect(self._export_loot)

        self.btn_clear_loot = QPushButton("🗑️ Leeren")
        self.btn_clear_loot.setProperty("class", "MiniDangerBtn")
        self.btn_clear_loot.setToolTip("Session-Loot dieses Projekts leeren")
        self.btn_clear_loot.clicked.connect(self._clear_loot)

        self.btn_export_report = QPushButton("💾 Report (.md)")
        self.btn_export_report.setProperty("class", "MiniActionBtn")
        self.btn_export_report.setToolTip("Erstellt eine neue Kopie basierend auf dem aktuellen Loot. Für die bearbeitbare Version siehe Report-Tab.")
        self.btn_export_report.clicked.connect(self._export_report)

        self.btn_clear_history = QPushButton("🗑️ Leeren")
        self.btn_clear_history.setProperty("class", "MiniDangerBtn")
        self.btn_clear_history.setToolTip("Clipboard-Historie dieses Projekts leeren")
        self.btn_clear_history.clicked.connect(self._clear_history)

        # 4. Compact Variable Status Bar
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
        lbl_warn = QLabel("⚠️ Datenschutz-Hinweis: Kopierte Passwörter oder persönliche Daten werden protokolliert, solange REC aktiv ist (Pausieren mit Ctrl+P oder Klick auf 🔴 REC).")
        lbl_warn.setObjectName("PrivacyWarningText")
        lbl_warn.setWordWrap(True)
        banner_layout.addWidget(lbl_warn)
        self.privacy_banner.setVisible(False)
        hud_layout.addWidget(self.privacy_banner)

        # 5. Scrollable Content Area (Snippets, Loot Cards, or History Cards)
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

        # 6. Minimal HUD Footer with Native QSizeGrip
        self.footer_frame = QFrame()
        self.footer_frame.setObjectName("HudFooter")
        footer_layout = QHBoxLayout(self.footer_frame)
        footer_layout.setContentsMargins(14, 4, 6, 4)

        hotkey_raw = self.config.get("hotkey", "<ctrl>+<cmd>+<")
        hotkey_display = hotkey_raw.replace("<ctrl>", "Strg").replace("<cmd>", "Super").replace("<shift>", "Shift").replace("<alt>", "Alt").replace("<", "").replace(">", "").replace("+", " + ")
        self.lbl_status = QLabel(f"⌨ {hotkey_display}: Toggle | Strg+Super+Q: Beenden | Ctrl+P: REC Toggle | Ctrl+S: Snip | Esc: Verstecken")
        self.lbl_status.setObjectName("FooterText")
        footer_layout.addWidget(self.lbl_status)

        footer_layout.addStretch()

        self.lbl_count = QLabel("0 Einträge")
        self.lbl_count.setObjectName("FooterText")
        footer_layout.addWidget(self.lbl_count)

        footer_layout.addSpacing(10)

        # Always on Top Toggle Checkbox
        is_always_on_top = self.config.get("always_on_top", True)
        self.chk_always_on_top = QCheckBox("📌 Im Vordergrund")
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

        # Install event filter on interactive frames for universal border resizing and drag-moving
        for w in [self.hud_frame, self.header_bar, self.pills_frame, self.footer_frame, self.var_bar, self.content_container, self.scroll_area, central_widget]:
            w.installEventFilter(self)

        # Connect clipboard logging state listener
        self.clipboard_watcher.logging_state_changed.connect(self._on_logging_state_changed)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Esc"), self, activated=self.hide)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_bar.set_focus)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._on_add_button_clicked)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.trigger_screenshot)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self._toggle_pause_history)
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=QApplication.quit)
        QShortcut(QKeySequence("Tab"), self, activated=self.toggle_mode)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self.switch_mode("cheatsheet"))
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.switch_mode("loot"))
        QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self.switch_mode("history"))
        QShortcut(QKeySequence("Ctrl+4"), self, activated=lambda: self.switch_mode("report"))

    def trigger_screenshot(self) -> None:
        """Triggers screenshot & snipping overlay."""
        target_ip = self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else ""
        self.screenshot_manager.start_capture(self, self.project_manager, self.loot_manager, target_ip=target_ip)

    def _on_screenshot_saved(self, loot_entry: Dict[str, Any]) -> None:
        """Called when a screenshot is successfully captured and saved."""
        self._save_current_project_state()
        self.switch_mode("loot")

    def _show_project_menu(self) -> None:
        """Displays project switcher popup menu."""
        menu = QMenu(self)
        active_proj = self.project_manager.get_active_project()
        all_projects = self.project_manager.list_projects()

        # Project list
        for p in all_projects:
            prefix = "✓ " if p == active_proj else "   "
            act = QAction(f"{prefix}{p}", menu)
            act.triggered.connect(lambda checked=False, pname=p: self._switch_to_project(pname))
            menu.addAction(act)

        menu.addSeparator()

        # Action: New Project
        act_new = QAction("➕ Neues Projekt / Box erstellen...", menu)
        act_new.triggered.connect(self._open_new_project_dialog)
        menu.addAction(act_new)

        # Action: Open in Explorer
        act_open_folder = QAction("📂 Projektordner im Explorer öffnen", menu)
        act_open_folder.triggered.connect(lambda: self.project_manager.open_project_folder())
        menu.addAction(act_open_folder)

        # Show menu under project button
        menu.exec(self.btn_project.mapToGlobal(QPoint(0, self.btn_project.height() + 4)))

    def _open_new_project_dialog(self) -> None:
        curr_target = self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else ""
        curr_attacker = self.var_bar.txt_attacker.text().strip() if hasattr(self, 'var_bar') else ""
        curr_port = self.var_bar.txt_port.text().strip() if hasattr(self, 'var_bar') else "4444"

        dlg = NewProjectDialog(self, default_target=curr_target, default_attacker=curr_attacker, default_port=curr_port)
        if dlg.exec():
            data = dlg.get_data()
            pname = data.get("name")
            if pname:
                self.project_manager.create_project(
                    name=pname,
                    target_ip=data.get("target_ip", ""),
                    attacker_ip=data.get("attacker_ip", ""),
                    port=data.get("port", "4444")
                )
                self._switch_to_project(pname)

    def _load_active_project_state(self) -> None:
        """Loads state for active project and injects into UI and Loot/History managers."""
        active_proj = self.project_manager.get_active_project()
        self.btn_project.setText(f"📁 Box: {active_proj} ▾")
        
        state = self.project_manager.load_project_state()
        if not state:
            return

        # Restore Variables in VariableBar
        if hasattr(self, 'var_bar'):
            self.var_bar.txt_target.blockSignals(True)
            self.var_bar.txt_attacker.blockSignals(True)
            self.var_bar.txt_port.blockSignals(True)

            self.var_bar.txt_target.setText(state.get("target_ip", "10.10.10.10"))
            self.var_bar.txt_attacker.setText(state.get("attacker_ip", "10.10.14.5"))
            self.var_bar.txt_port.setText(state.get("port", "4444"))

            self.var_bar.txt_target.blockSignals(False)
            self.var_bar.txt_attacker.blockSignals(False)
            self.var_bar.txt_port.blockSignals(False)

        # Restore Loot
        self.loot_manager.set_entries(state.get("loot", []))
        
        # Restore Clipboard History
        self.clipboard_watcher.set_history(state.get("clipboard_history", []))

    def _save_current_project_state(self) -> None:
        """Persists active project state to project_state.json."""
        target_ip = self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else "10.10.10.10"
        attacker_ip = self.var_bar.txt_attacker.text().strip() if hasattr(self, 'var_bar') else "10.10.14.5"
        port = self.var_bar.txt_port.text().strip() if hasattr(self, 'var_bar') else "4444"

        state = {
            "target_ip": target_ip,
            "attacker_ip": attacker_ip,
            "port": port,
            "loot": self.loot_manager.get_all_entries(),
            "clipboard_history": self.clipboard_watcher.get_all_history()
        }
        self.project_manager.save_project_state(state=state)

    def _switch_to_project(self, project_name: str) -> None:
        """Saves current state and switches to another project with dirty check."""
        if project_name == self.project_manager.get_active_project():
            return
        
        # Check dirty state on report editor tab before switching
        if hasattr(self, "report_editor_tab") and not self.report_editor_tab.confirm_discard_if_dirty():
            return

        # 1. Save current project state
        self._save_current_project_state()
        
        # 2. Switch active project in ProjectManager
        self.project_manager.set_active_project(project_name)
        
        # 3. Load new project state
        self._load_active_project_state()
        
        # 4. Load project report into ReportEditorTab
        if hasattr(self, "report_editor_tab"):
            self.report_editor_tab.load_project(project_name)

        # 5. Refresh UI
        self.refresh_filter_pills()
        self.refresh_content()

    def switch_mode(self, mode: str) -> None:
        """Switches between 'cheatsheet', 'loot', 'history', and 'report' modes."""
        if self.active_mode == "report" and mode != "report":
            if hasattr(self, "report_editor_tab") and not self.report_editor_tab.confirm_discard_if_dirty():
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
            self.search_bar.txt_search.setPlaceholderText("⚡ Befehl, Tool oder Syntax suchen (z. B. 'curl', 'nmap', 'sql')...")
        elif mode == "loot":
            self.search_bar.txt_search.setPlaceholderText("🔍 Session Loot, User, Passwörter, Hashes & Notizen durchsuchen...")
        elif mode == "history":
            self.search_bar.txt_search.setPlaceholderText("📜 Clipboard-Historie, kopierte Befehle & Ausgaben durchsuchen...")

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

    def closeEvent(self, event) -> None:
        """Intercepts window close to check for unsaved report modifications."""
        if hasattr(self, "report_editor_tab") and not self.report_editor_tab.confirm_discard_if_dirty():
            event.ignore()
            return
        event.accept()

    def refresh_filter_pills(self) -> None:
        """Populates horizontal filter pills and contextual actions depending on active mode."""
        while self.pills_layout.count():
            child = self.pills_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.filter_buttons.clear()

        if self.active_mode == "report":
            return

        if self.active_mode == "cheatsheet":
            cats = self.snippet_manager.get_categories()
            for c in cats:
                cat_id = c.get("id")
                pill_text = f"{c.get('icon', '')} {c.get('name').split(' ')[-1] if ' ' in c.get('name') else c.get('name')}"
                if cat_id == "all":
                    pill_text = "⚡ Alle Befehle"

                btn = QPushButton(pill_text)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setProperty("class", "FilterPillActive" if cat_id == self.current_category_id else "FilterPill")
                btn.clicked.connect(lambda checked=False, cid=cat_id: self._select_category(cid))
                self.filter_buttons[cat_id] = btn
                self.pills_layout.addWidget(btn)

            self.pills_layout.addStretch()

        elif self.active_mode == "loot":
            counts = self.loot_manager.get_type_counts(target_ip=None)
            all_btn = QPushButton(f"⚡ Alle ({counts.get('all', 0)})")
            all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            all_btn.setProperty("class", "FilterPillActive" if self.current_loot_type == "all" else "FilterPill")
            all_btn.clicked.connect(lambda: self._select_loot_type("all"))
            self.filter_buttons["all"] = all_btn
            self.pills_layout.addWidget(all_btn)

            for t in LOOT_TYPES:
                tid = t["id"]
                count = counts.get(tid, 0)
                btn = QPushButton(f"{t['icon']} {t['name'].split(' ')[1]} ({count})")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setProperty("class", "FilterPillActive" if self.current_loot_type == tid else "FilterPill")
                btn.clicked.connect(lambda checked=False, type_id=tid: self._select_loot_type(type_id))
                self.filter_buttons[tid] = btn
                self.pills_layout.addWidget(btn)

            self.pills_layout.addStretch()

            # Add Contextual Loot Action Buttons
            self.btn_export_loot = QPushButton("💾 Export (.md)")
            self.btn_export_loot.setProperty("class", "MiniActionBtn")
            self.btn_export_loot.setToolTip("Loot als formatierte Markdown-Datei exportieren")
            self.btn_export_loot.clicked.connect(self._export_loot)
            self.pills_layout.addWidget(self.btn_export_loot)

            self.btn_clear_loot = QPushButton("🗑️ Leeren")
            self.btn_clear_loot.setProperty("class", "MiniDangerBtn")
            self.btn_clear_loot.setToolTip("Session-Loot dieses Projekts leeren")
            self.btn_clear_loot.clicked.connect(self._clear_loot)
            self.pills_layout.addWidget(self.btn_clear_loot)

        else:
            # History mode filter pills
            history_all = self.clipboard_watcher.get_history()
            pills = [
                ("all", f"⚡ Alle ({len(history_all)})"),
                ("target_only", "🎯 Nur Ziel-IP"),
                ("commands", "⌨️ Befehle"),
                ("outputs", "📄 Ausgaben")
            ]
            for pid, ptext in pills:
                btn = QPushButton(ptext)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setProperty("class", "FilterPillActive" if self.current_history_filter == pid else "FilterPill")
                btn.clicked.connect(lambda checked=False, fid=pid: self._select_history_filter(fid))
                self.filter_buttons[pid] = btn
                self.pills_layout.addWidget(btn)

            self.pills_layout.addStretch()

            # Add Contextual History Action Buttons
            self.btn_export_report = QPushButton("💾 Report (.md)")
            self.btn_export_report.setProperty("class", "MiniActionBtn")
            self.btn_export_report.setToolTip("Vollständigen CTF Write-Up Report als Markdown exportieren")
            self.btn_export_report.clicked.connect(self._export_report)
            self.pills_layout.addWidget(self.btn_export_report)

            self.btn_clear_history = QPushButton("🗑️ Leeren")
            self.btn_clear_history.setProperty("class", "MiniDangerBtn")
            self.btn_clear_history.setToolTip("Clipboard-Historie dieses Projekts leeren")
            self.btn_clear_history.clicked.connect(self._clear_history)
            self.pills_layout.addWidget(self.btn_clear_history)

    def _select_category(self, category_id: str) -> None:
        self.current_category_id = category_id
        for cid, btn in self.filter_buttons.items():
            btn.setProperty("class", "FilterPillActive" if cid == category_id else "FilterPill")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.refresh_content()

    def _select_loot_type(self, type_id: str) -> None:
        self.current_loot_type = type_id
        for tid, btn in self.filter_buttons.items():
            btn.setProperty("class", "FilterPillActive" if tid == type_id else "FilterPill")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.refresh_content()

    def _select_history_filter(self, filter_id: str) -> None:
        self.current_history_filter = filter_id
        for fid, btn in self.filter_buttons.items():
            btn.setProperty("class", "FilterPillActive" if fid == filter_id else "FilterPill")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.refresh_content()

    def refresh_content(self) -> None:
        """Rebuilds scrollable cards or displays ReportEditorTab based on active mode and query."""
        if self.active_mode == "report":
            while self.content_layout.count():
                child = self.content_layout.takeAt(0)
                if child.widget() and child.widget() != self.report_editor_tab:
                    child.widget().deleteLater()
            self.cards.clear()
            self.content_layout.addWidget(self.report_editor_tab)
            self.lbl_count.setText("Report Editor")
            return

        # Detach report_editor_tab if previously attached without deleting
        if hasattr(self, "report_editor_tab") and self.report_editor_tab.parent() is not None:
            self.content_layout.removeWidget(self.report_editor_tab)
            self.report_editor_tab.setParent(None)

        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.cards.clear()

        query = self.search_bar.get_text()
        variables = self.var_bar.get_variables() if hasattr(self, 'var_bar') else {}

        if self.active_mode == "cheatsheet":
            snippets = self.snippet_manager.get_snippets(
                category_id=self.current_category_id,
                search_query=query
            )
            self.lbl_count.setText(f"{len(snippets)} Befehle")

            if not snippets:
                self._show_empty_state("Keine Befehle gefunden. Drücke Ctrl+N zum Hinzufügen.")
                return

            for s in snippets:
                card = SnippetCard(s, variables=variables, parent=self)
                card.snippet_deleted.connect(self._on_snippet_deleted)
                self.content_layout.addWidget(card)
                self.cards.append(card)

        elif self.active_mode == "loot":
            loot_entries = self.loot_manager.get_entries(
                target_ip=None,
                entry_type=self.current_loot_type,
                search_query=query
            )
            self.lbl_count.setText(f"{len(loot_entries)} Loot-Einträge")

            if not loot_entries:
                self._show_empty_state("Kein Session-Loot vorhanden. Drücke Ctrl+N um Notizen/Creds anzulegen oder 📷 Snip für Screenshots.")
                return

            active_proj = self.project_manager.get_active_project()
            proj_dir = self.project_manager.get_project_dir(active_proj)

            for entry in loot_entries:
                card = LootCard(entry, project_dir=proj_dir, parent=self)
                card.loot_deleted.connect(self._on_loot_deleted)
                card.edit_requested.connect(self._on_edit_loot_requested)
                self.content_layout.addWidget(card)
                self.cards.append(card)

        else:
            # History mode
            history_items = self.clipboard_watcher.get_history(
                target_ip=variables.get("target_ip") if self.current_history_filter == "target_only" else None,
                filter_type=self.current_history_filter if self.current_history_filter in ["commands", "outputs"] else "all",
                search_query=query
            )
            self.lbl_count.setText(f"{len(history_items)} Verlaufseinträge")

            if not history_items:
                self._show_empty_state("Keine Clipboard-Historie vorhanden. Aktiviere 🔴 REC (Ctrl+P) und kopiere Befehle im Terminal.")
                return

            for item in history_items:
                card = HistoryCard(item, parent=self)
                card.add_to_loot_requested.connect(self._on_history_add_to_loot)
                card.entry_deleted.connect(self._on_history_entry_deleted)
                self.content_layout.addWidget(card)
                self.cards.append(card)

    def _show_empty_state(self, message: str) -> None:
        empty_lbl = QLabel(message)
        empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_lbl.setStyleSheet("color: #6e7681; font-size: 13px; font-style: italic; padding: 40px 20px;")
        empty_lbl.setWordWrap(True)
        self.content_layout.addWidget(empty_lbl)

    def _on_search_changed(self, text: str) -> None:
        self.refresh_content()

    def _on_variables_changed(self, vars_dict: Dict[str, str]) -> None:
        if self.active_mode == "cheatsheet":
            for card in self.cards:
                if isinstance(card, SnippetCard):
                    card.update_variables(vars_dict)

    def _on_add_button_clicked(self) -> None:
        if self.active_mode == "cheatsheet":
            cats = self.snippet_manager.get_categories()
            dlg = AddSnippetDialog(cats, parent=self)
            if dlg.exec():
                data = dlg.get_data()
                self.snippet_manager.add_custom_snippet(
                    title=data["title"],
                    category=data["category"],
                    subcategory=data["subcategory"],
                    template=data["template"],
                    description=data["description"],
                    tags=data.get("tags", [])
                )
                self.refresh_filter_pills()
                self.refresh_content()
        elif self.active_mode == "loot":
            target_ip = self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else ""
            dlg = AddLootDialog(target_ip=target_ip, parent=self)
            if dlg.exec():
                data = dlg.get_data()
                self.loot_manager.add_entry(
                    entry_type=data["type"],
                    category=data.get("category", "misc"),
                    title=data["title"],
                    content=data["content"],
                    target_ip=data["target_ip"]
                )
                self._save_current_project_state()
                self.refresh_filter_pills()
                self.refresh_content()
        else:
            # History mode -> add custom note to loot
            target_ip = self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else ""
            dlg = AddLootDialog(target_ip=target_ip, default_type="note", default_category="recon", parent=self)
            if dlg.exec():
                data = dlg.get_data()
                self.loot_manager.add_entry(
                    entry_type=data["type"],
                    category=data.get("category", "misc"),
                    title=data["title"],
                    content=data["content"],
                    target_ip=data["target_ip"]
                )
                self._save_current_project_state()
                self.refresh_filter_pills()
                self.refresh_content()

    def _on_edit_loot_requested(self, entry: Dict[str, Any]) -> None:
        """Opens AddLootDialog in edit mode to modify an existing loot entry."""
        dlg = AddLootDialog(
            parent=self,
            entry_id=entry.get("id"),
            is_edit=True,
            initial_type=entry.get("type", "note"),
            initial_category=entry.get("category", "misc"),
            initial_title=entry.get("title", ""),
            initial_content=entry.get("content", ""),
            current_target_ip=entry.get("target_ip", "")
        )
        if dlg.exec():
            data = dlg.get_data()
            self.loot_manager.update_entry(
                entry_id=data.get("id") or entry.get("id", ""),
                type=data.get("type"),
                category=data.get("category"),
                title=data.get("title"),
                content=data.get("content"),
                target_ip=data.get("target_ip")
            )
            self._save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _on_snippet_deleted(self, snippet_id: str) -> None:
        self.snippet_manager.delete_snippet(snippet_id)
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_loot_deleted(self, loot_id: str) -> None:
        self.loot_manager.delete_entry(loot_id)
        self._save_current_project_state()
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_clipboard_entry_added(self, entry: Dict[str, Any]) -> None:
        if self.active_mode == "history":
            self.refresh_filter_pills()
            self.refresh_content()
        self._save_current_project_state()

    def _on_history_entry_deleted(self, entry_id: str) -> None:
        self.clipboard_watcher.delete_entry(entry_id)
        self._save_current_project_state()
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_history_add_to_loot(self, history_item: Dict[str, Any]) -> None:
        target_ip = history_item.get("target_ip") or (self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else "")
        dlg = AddLootDialog(
            target_ip=target_ip,
            default_type="credentials" if history_item.get("is_command") else "note",
            default_category="access" if history_item.get("is_command") else "recon",
            default_title=f"Kopiert aus Terminal ({history_item.get('timestamp', '')})",
            default_content=history_item.get("text", ""),
            parent=self
        )
        if dlg.exec():
            data = dlg.get_data()
            self.loot_manager.add_entry(
                entry_type=data["type"],
                category=data.get("category", "misc"),
                title=data["title"],
                content=data["content"],
                target_ip=data["target_ip"]
            )
            self._save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _export_loot(self) -> None:
        self._export_report()

    def _clear_loot(self) -> None:
        reply = QMessageBox.question(
            self, "Session leeren", 
            "Möchtest du wirklich alle Loot-Einträge dieses Projekts löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.loot_manager.clear_session()
            self._save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _export_report(self) -> None:
        active_proj = self.project_manager.get_active_project()
        proj_dir = self.project_manager.get_project_dir(active_proj)
        default_path = proj_dir / "report.md"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "CTF Write-Up Report exportieren", str(default_path), "Markdown (*.md)"
        )
        if file_path:
            target_ip = self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else ""
            builder = ReportBuilder(
                loot_manager=self.loot_manager,
                clipboard_watcher=self.clipboard_watcher,
                project_manager=self.project_manager
            )
            msg = builder.export(
                Path(file_path), 
                target_ip=target_ip if target_ip else None, 
                project_name=active_proj
            )
            QMessageBox.information(self, "Report generiert", msg)

    def _toggle_pause_history(self) -> None:
        self.clipboard_watcher.toggle_pause()

    def _on_logging_state_changed(self, is_active: bool) -> None:
        """Updates REC button indicator, tooltips, and styles when recording state changes."""
        if is_active:
            self.btn_rec_indicator.setText("🔴 REC")
            self.btn_rec_indicator.setProperty("paused", "false")
            self.btn_rec_indicator.setToolTip("Clipboard-Logger ist AKTIV (schneidet alle Kopien mit).\nKlicken oder Ctrl+P zum Pausieren.")
        else:
            self.btn_rec_indicator.setText("⏸️ REC: Aus")
            self.btn_rec_indicator.setProperty("paused", "true")
            self.btn_rec_indicator.setToolTip("Clipboard-Logger ist PAUSIERT (keine Aufzeichnung).\nKlicken oder Ctrl+P zum Fortsetzen.")

        self.btn_rec_indicator.style().unpolish(self.btn_rec_indicator)
        self.btn_rec_indicator.style().polish(self.btn_rec_indicator)

    def _clear_history(self) -> None:
        reply = QMessageBox.question(
            self, "Historie leeren", 
            "Möchtest du wirklich die gesamte Clipboard-Historie dieses Projekts löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.clipboard_watcher.clear_history()
            self._save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2 + geo.x()
            y = max(geo.y() + 60, (geo.height() - self.height()) // 3 + geo.y())
            self.move(x, y)

    def _on_always_on_top_toggled(self, checked: bool) -> None:
        """Dynamically toggles WindowStaysOnTopHint and updates config."""
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

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.config.set("window_width", self.width())
        self.config.set("window_height", self.height())

    # -------------------------------------------------------------
    # Frameless Window Drag & Resizing Engine
    # -------------------------------------------------------------
    def _get_resize_edge(self, pos: QPoint) -> str:
        """Determines if the mouse position is on an outer resize border/corner with generous grab zones."""
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        margin = RESIZE_MARGIN
        corner = CORNER_MARGIN

        # Corners take priority with a larger radius
        if x <= corner and y <= corner:
            return "top_left"
        if x >= w - corner and y <= corner:
            return "top_right"
        if x <= corner and y >= h - corner:
            return "bottom_left"
        if x >= w - corner and y >= h - corner:
            return "bottom_right"

        # Edges
        if x <= margin:
            return "left"
        if x >= w - margin:
            return "right"
        if y <= margin:
            return "top"
        if y >= h - margin:
            return "bottom"
        return ""

    def _update_cursor_for_edge(self, edge: str) -> None:
        if edge in ("top_left", "bottom_right"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in ("top_right", "bottom_left"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edge in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in ("top", "bottom"):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def eventFilter(self, watched, event: QEvent) -> bool:
        if not self.isVisible():
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.MouseMove:
            if hasattr(event, "globalPosition"):
                global_pt = event.globalPosition().toPoint()

                if self._is_resizing:
                    delta = global_pt - self._resize_start_pos
                    geo = QRect(self._resize_start_geo)
                    min_w = self.minimumWidth()
                    min_h = self.minimumHeight()

                    if "right" in self._resize_edge:
                        new_w = max(min_w, self._resize_start_geo.width() + delta.x())
                        geo.setWidth(new_w)
                    elif "left" in self._resize_edge:
                        new_w = max(min_w, self._resize_start_geo.width() - delta.x())
                        geo.setLeft(self._resize_start_geo.right() - new_w)

                    if "bottom" in self._resize_edge:
                        new_h = max(min_h, self._resize_start_geo.height() + delta.y())
                        geo.setHeight(new_h)
                    elif "top" in self._resize_edge:
                        new_h = max(min_h, self._resize_start_geo.height() - delta.y())
                        geo.setTop(self._resize_start_geo.bottom() - new_h)

                    self.setGeometry(geo)
                    return True

                if self._is_moving and not self._drag_pos.isNull():
                    self.move(global_pt - self._drag_pos)
                    return True

                local_pt = self.mapFromGlobal(global_pt)
                edge = self._get_resize_edge(local_pt)
                self._update_cursor_for_edge(edge)

        elif event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if hasattr(event, "globalPosition"):
                global_pt = event.globalPosition().toPoint()
                local_pt = self.mapFromGlobal(global_pt)
                edge = self._get_resize_edge(local_pt)

                if edge:
                    self._is_resizing = True
                    self._resize_edge = edge
                    self._resize_start_pos = global_pt
                    self._resize_start_geo = self.geometry()
                    return True

                # Check if clicked on a non-interactive area to start dragging/moving the window
                clicked_widget = self.childAt(local_pt)
                if not _is_interactive_widget(clicked_widget):
                    self._is_moving = True
                    self._drag_pos = global_pt - self.frameGeometry().topLeft()
                    return True

        elif event.type() == QEvent.Type.MouseButtonRelease:
            if self._is_resizing:
                self._is_resizing = False
                self._resize_edge = ""
                self.unsetCursor()
                self.config.set("window_width", self.width())
                self.config.set("window_height", self.height())
                return True
            elif self._is_moving:
                self._is_moving = False
                self._drag_pos = QPoint()
                return True

        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._get_resize_edge(event.pos())
            if edge:
                self._is_resizing = True
                self._resize_edge = edge
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geo = self.geometry()
                event.accept()
                return

            clicked_widget = self.childAt(event.pos())
            if not _is_interactive_widget(clicked_widget):
                self._is_moving = True
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_resizing:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geo = QRect(self._resize_start_geo)
            min_w = self.minimumWidth()
            min_h = self.minimumHeight()

            if "right" in self._resize_edge:
                new_w = max(min_w, self._resize_start_geo.width() + delta.x())
                geo.setWidth(new_w)
            elif "left" in self._resize_edge:
                new_w = max(min_w, self._resize_start_geo.width() - delta.x())
                geo.setLeft(self._resize_start_geo.right() - new_w)

            if "bottom" in self._resize_edge:
                new_h = max(min_h, self._resize_start_geo.height() + delta.y())
                geo.setHeight(new_h)
            elif "top" in self._resize_edge:
                new_h = max(min_h, self._resize_start_geo.height() - delta.y())
                geo.setTop(self._resize_start_geo.bottom() - new_h)

            self.setGeometry(geo)
            event.accept()
            return

        if self._is_moving and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return

        edge = self._get_resize_edge(event.pos())
        self._update_cursor_for_edge(edge)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._is_resizing:
            self._is_resizing = False
            self._resize_edge = ""
            self.unsetCursor()
            self.config.set("window_width", self.width())
            self.config.set("window_height", self.height())
            event.accept()
        elif self._is_moving:
            self._is_moving = False
            self._drag_pos = QPoint()
            event.accept()

    def leaveEvent(self, event: QEvent) -> None:
        if not self._is_resizing:
            self.unsetCursor()
        super().leaveEvent(event)

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.show()
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            self.raise_()
            self.activateWindow()
            self.search_bar.set_focus()

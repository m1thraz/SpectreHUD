from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QScrollArea, QFrame, QLabel, QPushButton, QMessageBox, 
    QFileDialog, QMenu, QApplication
)
from PyQt6.QtCore import Qt, QPoint, pyqtSlot
from PyQt6.QtGui import QKeySequence, QShortcut, QGuiApplication, QMouseEvent, QAction
from typing import Dict, Any, List, Optional

from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager, LOOT_TYPES
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
from ui.variable_bar import VariableBar
from ui.search_bar import SearchBar
from ui.snippet_card import SnippetCard
from ui.loot_card import LootCard
from ui.history_card import HistoryCard
from ui.add_snippet_dialog import AddSnippetDialog
from ui.add_loot_dialog import AddLootDialog
from ui.project_dialog import NewProjectDialog
from ui.styles import CYBER_DARK_QSS

class MainWindow(QMainWindow):
    """Sleek, frameless, translucent Spotlight-style HUD Overlay for Cheatsheets, Session Loot, History & Workspaces."""

    def __init__(
        self, 
        config_manager: ConfigManager, 
        snippet_manager: SnippetManager, 
        loot_manager: Optional[LootManager] = None,
        clipboard_watcher: Optional[ClipboardWatcher] = None,
        project_manager: Optional[ProjectManager] = None
    ):
        super().__init__()
        self.config = config_manager
        self.snippet_manager = snippet_manager
        self.project_manager = project_manager if project_manager is not None else ProjectManager()
        self.loot_manager = loot_manager if loot_manager is not None else LootManager()
        self.clipboard_watcher = clipboard_watcher if clipboard_watcher is not None else ClipboardWatcher()
        
        # Connect watcher target provider
        self.clipboard_watcher.set_target_provider(lambda: self.var_bar.txt_target.text().strip() if hasattr(self, 'var_bar') else "")
        self.clipboard_watcher.entry_added.connect(self._on_clipboard_entry_added)

        self.active_mode = "cheatsheet"  # 'cheatsheet', 'loot', or 'history'
        self.current_category_id = "all"
        self.current_loot_type = "all"
        self.current_history_filter = "all"
        
        self.cards: List[QWidget] = []
        self.filter_buttons: Dict[str, QPushButton] = {}
        self._drag_pos: QPoint = QPoint()

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
        self.resize(830, 600)
        self.setMinimumSize(680, 460)
        
        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(CYBER_DARK_QSS)

    def _init_ui(self) -> None:
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(0)

        # Main HUD Glass Frame
        self.hud_frame = QFrame()
        self.hud_frame.setObjectName("HudFrame")
        
        hud_layout = QVBoxLayout(self.hud_frame)
        hud_layout.setContentsMargins(0, 0, 0, 0)
        hud_layout.setSpacing(0)

        # 1. Top Header Row: Brand + Project Selector + Mode Switcher + Actions
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

        header_layout.addSpacing(6)

        # Mode Switcher Tabs
        self.btn_mode_cheatsheet = QPushButton("⚡ Cheatsheet")
        self.btn_mode_cheatsheet.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_cheatsheet.setProperty("class", "ModeSwitchBtnActive")
        self.btn_mode_cheatsheet.clicked.connect(lambda: self.switch_mode("cheatsheet"))
        header_layout.addWidget(self.btn_mode_cheatsheet)

        self.btn_mode_loot = QPushButton("📝 Session Loot")
        self.btn_mode_loot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_loot.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_loot.clicked.connect(lambda: self.switch_mode("loot"))
        header_layout.addWidget(self.btn_mode_loot)

        self.btn_mode_history = QPushButton("📜 History / Report")
        self.btn_mode_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_history.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_history.clicked.connect(lambda: self.switch_mode("history"))
        header_layout.addWidget(self.btn_mode_history)

        header_layout.addStretch()

        # Loot Mode Specific Actions
        self.btn_export_loot = QPushButton("💾 Exportieren")
        self.btn_export_loot.setProperty("class", "SecondaryBtn")
        self.btn_export_loot.setToolTip("Loot als loot.txt exportieren")
        self.btn_export_loot.clicked.connect(self._export_loot)
        self.btn_export_loot.setVisible(False)
        header_layout.addWidget(self.btn_export_loot)

        self.btn_clear_loot = QPushButton("🗑️ Leeren")
        self.btn_clear_loot.setProperty("class", "DangerBtn")
        self.btn_clear_loot.setToolTip("Session-Loot leeren")
        self.btn_clear_loot.clicked.connect(self._clear_loot)
        self.btn_clear_loot.setVisible(False)
        header_layout.addWidget(self.btn_clear_loot)

        # History Mode Specific Actions
        self.btn_export_report = QPushButton("💾 Report (.md)")
        self.btn_export_report.setProperty("class", "PrimaryBtn")
        self.btn_export_report.setToolTip("Vollständigen CTF Write-Up Report als Markdown exportieren")
        self.btn_export_report.clicked.connect(self._export_report)
        self.btn_export_report.setVisible(False)
        header_layout.addWidget(self.btn_export_report)

        self.btn_pause_history = QPushButton("⏸️ Pause")
        self.btn_pause_history.setProperty("class", "SecondaryBtn")
        self.btn_pause_history.setToolTip("Clipboard-Logging pausieren/fortsetzen")
        self.btn_pause_history.clicked.connect(self._toggle_pause_history)
        self.btn_pause_history.setVisible(False)
        header_layout.addWidget(self.btn_pause_history)

        self.btn_clear_history = QPushButton("🗑️ Leeren")
        self.btn_clear_history.setProperty("class", "DangerBtn")
        self.btn_clear_history.setToolTip("Clipboard-Historie leeren")
        self.btn_clear_history.clicked.connect(self._clear_history)
        self.btn_clear_history.setVisible(False)
        header_layout.addWidget(self.btn_clear_history)

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

        # 3. Horizontal Filter Pills Bar
        self.pills_frame = QFrame()
        self.pills_frame.setObjectName("FilterPillsFrame")
        self.pills_layout = QHBoxLayout(self.pills_frame)
        self.pills_layout.setContentsMargins(12, 2, 12, 6)
        self.pills_layout.setSpacing(6)
        self.pills_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        hud_layout.addWidget(self.pills_frame)

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

        # 6. Minimal HUD Footer
        self.footer_frame = QFrame()
        self.footer_frame.setObjectName("HudFooter")
        footer_layout = QHBoxLayout(self.footer_frame)
        footer_layout.setContentsMargins(14, 4, 14, 4)

        hotkey_raw = self.config.get("hotkey", "<ctrl>+<cmd>+<")
        hotkey_display = hotkey_raw.replace("<ctrl>", "Strg").replace("<cmd>", "Super").replace("<shift>", "Shift").replace("<alt>", "Alt").replace("<", "").replace(">", "").replace("+", " + ")
        self.lbl_status = QLabel(f"⌨ {hotkey_display}: Toggle | Tab: Modus | Ctrl+N: Neu | Esc: Schließen")
        self.lbl_status.setObjectName("FooterText")
        footer_layout.addWidget(self.lbl_status)

        footer_layout.addStretch()

        self.lbl_count = QLabel("0 Einträge")
        self.lbl_count.setObjectName("FooterText")
        footer_layout.addWidget(self.lbl_count)

        hud_layout.addWidget(self.footer_frame)
        outer_layout.addWidget(self.hud_frame)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Esc"), self, activated=self.hide)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_bar.set_focus)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._on_add_button_clicked)
        QShortcut(QKeySequence("Tab"), self, activated=self.toggle_mode)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self.switch_mode("cheatsheet"))
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.switch_mode("loot"))
        QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self.switch_mode("history"))

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
        """Opens dialog to create a new project workspace."""
        current_attacker = self.var_bar.txt_attacker.text().strip()
        dlg = NewProjectDialog(default_attacker_ip=current_attacker, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            name = data["name"]
            target_ip = data["target_ip"]
            attacker_ip = data["attacker_ip"]
            
            # Create project workspace
            self.project_manager.create_project(name, target_ip=target_ip, attacker_ip=attacker_ip)
            self._switch_to_project(name)

    def _save_current_project_state(self) -> None:
        """Persists active workspace data (IPs, loot, clipboard history) into project_state.json."""
        active_name = self.project_manager.get_active_project()
        current_vars = self.var_bar.get_variables() if hasattr(self, 'var_bar') else {}
        
        state = {
            "name": active_name,
            "target_ip": current_vars.get("target_ip", ""),
            "attacker_ip": current_vars.get("attacker_ip", ""),
            "port": current_vars.get("port", "4444"),
            "wordlist": current_vars.get("wordlist", "/usr/share/wordlists/dirb/common.txt"),
            "loot": self.loot_manager.get_all_entries(),
            "clipboard_history": self.clipboard_watcher.get_all_history()
        }
        self.project_manager.save_project_state(active_name, state)

    def _load_active_project_state(self) -> None:
        """Loads state data for currently active workspace into UI and managers."""
        active_name = self.project_manager.get_active_project()
        self.btn_project.setText(f"📁 Box: {active_name} ▾")
        
        state = self.project_manager.load_project_state(active_name)
        target_ip = state.get("target_ip", "10.10.10.10")
        attacker_ip = state.get("attacker_ip", "10.10.14.5")
        port = state.get("port", "4444")
        
        # Update inputs
        if hasattr(self, 'var_bar'):
            self.var_bar.txt_target.setText(target_ip)
            self.var_bar.txt_attacker.setText(attacker_ip)
            self.var_bar.txt_port.setText(port)

        # Update Loot and History items
        self.loot_manager.set_entries(state.get("loot", []))
        self.clipboard_watcher.set_history(state.get("clipboard_history", []))

    def _switch_to_project(self, project_name: str) -> None:
        """Switches workspace context and updates all state components."""
        # 1. Save current project state
        self._save_current_project_state()
        
        # 2. Switch active project in ProjectManager
        self.project_manager.set_active_project(project_name)
        
        # 3. Load new project state
        self._load_active_project_state()
        
        # 4. Refresh UI
        self.refresh_filter_pills()
        self.refresh_content()

    def switch_mode(self, mode: str) -> None:
        """Switches between 'cheatsheet', 'loot', and 'history' modes."""
        self.active_mode = mode
        
        self.btn_mode_cheatsheet.setProperty("class", "ModeSwitchBtnActive" if mode == "cheatsheet" else "ModeSwitchBtn")
        self.btn_mode_loot.setProperty("class", "ModeSwitchBtnActive" if mode == "loot" else "ModeSwitchBtn")
        self.btn_mode_history.setProperty("class", "ModeSwitchBtnActive" if mode == "history" else "ModeSwitchBtn")

        self.btn_export_loot.setVisible(mode == "loot")
        self.btn_clear_loot.setVisible(mode == "loot")
        self.btn_export_report.setVisible(mode == "history")
        self.btn_pause_history.setVisible(mode == "history")
        self.btn_clear_history.setVisible(mode == "history")

        if mode == "cheatsheet":
            self.search_bar.txt_search.setPlaceholderText("⚡ Befehl, Tool oder Syntax suchen (z. B. 'curl', 'nmap', 'sql')...")
        elif mode == "loot":
            self.search_bar.txt_search.setPlaceholderText("🔍 Session Loot, User, Passwörter, Hashes & Notizen durchsuchen...")
        else:
            self.search_bar.txt_search.setPlaceholderText("📜 Clipboard-Historie, kopierte Befehle & Ausgaben durchsuchen...")

        for btn in [self.btn_mode_cheatsheet, self.btn_mode_loot, self.btn_mode_history]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.refresh_filter_pills()
        self.refresh_content()
        self.search_bar.set_focus()

    def toggle_mode(self) -> None:
        """Cycles through modes via Tab shortcut."""
        modes = ["cheatsheet", "loot", "history"]
        idx = modes.index(self.active_mode) if self.active_mode in modes else 0
        next_mode = modes[(idx + 1) % len(modes)]
        self.switch_mode(next_mode)

    def refresh_filter_pills(self) -> None:
        """Populates horizontal filter pills depending on active mode."""
        while self.pills_layout.count():
            child = self.pills_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.filter_buttons.clear()

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

        else:
            # History mode filter pills
            history_all = self.clipboard_watcher.get_history()
            pills = [
                ("all", f"⚡ Alle Verlauf ({len(history_all)})"),
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
        """Rebuilds scrollable cards based on active mode and query."""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.cards.clear()

        query = self.search_bar.text()
        current_vars = self.var_bar.get_variables()
        target_ip = current_vars.get("target_ip", "")

        if self.active_mode == "cheatsheet":
            matched = self.snippet_manager.search(query=query, category_id=self.current_category_id)
            if not matched:
                empty_lbl = QLabel(f"🔍 Keine Befehle gefunden für: '{query}'")
                empty_lbl.setStyleSheet("color: #8b949e; font-size: 13px; padding: 30px;")
                empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.content_layout.addWidget(empty_lbl)
                self.lbl_count.setText("0 Befehle")
                return

            for snip in matched:
                card = SnippetCard(snip, current_vars)
                card.copied.connect(self._on_item_copied)
                card.deleted.connect(self._on_snippet_deleted)
                self.cards.append(card)
                self.content_layout.addWidget(card)

            self.lbl_count.setText(f"{len(matched)} Befehle geladen")

        elif self.active_mode == "loot":
            matched_loot = self.loot_manager.get_entries(
                target_ip=None,
                entry_type=self.current_loot_type,
                search_query=query
            )
            if not matched_loot:
                empty_lbl = QLabel("📝 Noch kein Loot oder Notizen in diesem Projekt erfasst.\nDrücke 'Ctrl + N' oder '＋ Neu', um Einträge hinzuzufügen.")
                empty_lbl.setStyleSheet("color: #8b949e; font-size: 13px; padding: 30px;")
                empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.content_layout.addWidget(empty_lbl)
                self.lbl_count.setText("0 Loot-Einträge")
                return

            for entry in matched_loot:
                card = LootCard(entry)
                card.copied.connect(self._on_item_copied)
                card.deleted.connect(self._on_loot_deleted)
                self.cards.append(card)
                self.content_layout.addWidget(card)

            self.lbl_count.setText(f"{len(matched_loot)} Loot-Einträge")

        else:
            # History mode
            target_filter = target_ip if self.current_history_filter == "target_only" else None
            filter_type = self.current_history_filter if self.current_history_filter in ["commands", "outputs"] else None

            matched_history = self.clipboard_watcher.get_history(
                search_query=query,
                target_ip=target_filter,
                filter_type=filter_type
            )
            if not matched_history:
                empty_lbl = QLabel("📜 Noch keine Clipboard-Historie in diesem Projekt aufgezeichnet.\nKopierte Befehle oder Textblöcke erscheinen hier automatisch!")
                empty_lbl.setStyleSheet("color: #8b949e; font-size: 13px; padding: 30px;")
                empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.content_layout.addWidget(empty_lbl)
                self.lbl_count.setText("0 Verlaufseinträge")
                return

            for item in matched_history:
                card = HistoryCard(item)
                card.copied.connect(self._on_item_copied)
                card.transfer_to_loot.connect(self._on_history_transfer_to_loot)
                card.deleted.connect(self._on_history_deleted)
                self.cards.append(card)
                self.content_layout.addWidget(card)

            self.lbl_count.setText(f"{len(matched_history)} Verlaufseinträge")

    def _on_search_changed(self, text: str) -> None:
        self.refresh_content()

    def _on_variables_changed(self, vars_dict: Dict[str, str]) -> None:
        self.config.set("target_ip", vars_dict.get("target_ip", ""))
        self.config.set("attacker_ip", vars_dict.get("attacker_ip", ""))
        self.config.set("port", vars_dict.get("port", ""))
        
        # Save to project state
        self._save_current_project_state()

        if self.active_mode == "cheatsheet":
            for card in self.cards:
                if isinstance(card, SnippetCard):
                    card.update_variables(vars_dict)
        else:
            self.refresh_filter_pills()
            self.refresh_content()

    def _on_clipboard_entry_added(self, entry: Dict[str, Any]) -> None:
        """Auto-saves to active project state and updates view."""
        self._save_current_project_state()
        if self.active_mode == "history":
            self.refresh_filter_pills()
            self.refresh_content()

    def _on_item_copied(self, text: str) -> None:
        if self.config.get("auto_hide_on_copy", False):
            self.hide()

    def _on_snippet_deleted(self, snippet_id: str) -> None:
        reply = QMessageBox.question(
            self, "Befehl löschen", 
            "Möchtest du diesen eigenen Befehl wirklich entfernen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.snippet_manager.delete_snippet(snippet_id):
                self.refresh_filter_pills()
                self.refresh_content()

    def _on_loot_deleted(self, loot_id: str) -> None:
        if self.loot_manager.delete_entry(loot_id):
            self._save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _on_history_deleted(self, history_id: str) -> None:
        if self.clipboard_watcher.delete_entry(history_id):
            self._save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _on_history_transfer_to_loot(self, history_item: Dict[str, Any]) -> None:
        """Opens AddLootDialog with pre-filled content from clipboard history."""
        target_ip = history_item.get("target_ip", "") or self.var_bar.txt_target.text().strip()
        text = history_item.get("text", "")
        first_line = text.split("\n")[0][:40]
        dlg = AddLootDialog(
            current_target_ip=target_ip,
            initial_content=text,
            initial_title=f"Aus Clipboard: {first_line}",
            initial_type="note",
            parent=self
        )
        if dlg.exec():
            data = dlg.get_data()
            self.loot_manager.add_entry(
                entry_type=data["type"],
                title=data["title"],
                content=data["content"],
                target_ip=data["target_ip"]
            )
            self._save_current_project_state()
            QMessageBox.information(self, "Erfolg", "Eintrag erfolgreich in Session-Loot gespeichert!")

    def _on_add_button_clicked(self) -> None:
        if self.active_mode == "cheatsheet":
            self._open_add_snippet_dialog()
        else:
            self._open_add_loot_dialog()

    def _open_add_snippet_dialog(self) -> None:
        cats = self.snippet_manager.get_categories()
        dlg = AddSnippetDialog(cats, self)
        if dlg.exec():
            data = dlg.get_data()
            self.snippet_manager.add_custom_snippet(
                title=data["title"],
                category=data["category"],
                subcategory=data["subcategory"],
                template=data["template"],
                description=data["description"],
                tags=data["tags"]
            )
            self.refresh_filter_pills()
            self.refresh_content()

    def _open_add_loot_dialog(self) -> None:
        target_ip = self.var_bar.txt_target.text().strip()
        dlg = AddLootDialog(current_target_ip=target_ip, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            self.loot_manager.add_entry(
                entry_type=data["type"],
                title=data["title"],
                content=data["content"],
                target_ip=data["target_ip"]
            )
            self._save_current_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

    def _export_loot(self) -> None:
        active_proj = self.project_manager.get_active_project()
        proj_dir = self.project_manager.get_project_dir(active_proj)
        default_path = proj_dir / "loot" / "loot.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Session-Loot exportieren", str(default_path), "Text / Markdown (*.txt *.md)"
        )
        if file_path:
            target_ip = self.var_bar.txt_target.text().strip()
            msg = self.loot_manager.export_loot(Path(file_path), target_ip=target_ip if target_ip else None)
            QMessageBox.information(self, "Export erfolgreich", msg)

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
        default_path = proj_dir / "notes.md"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "CTF Write-Up Report exportieren", str(default_path), "Markdown (*.md)"
        )
        if file_path:
            target_ip = self.var_bar.txt_target.text().strip()
            msg = self.clipboard_watcher.export_report_markdown(
                Path(file_path), 
                target_ip=target_ip if target_ip else None, 
                loot_manager=self.loot_manager
            )
            QMessageBox.information(self, "Report generiert", msg)

    def _toggle_pause_history(self) -> None:
        paused = self.clipboard_watcher.toggle_pause()
        if paused:
            self.btn_pause_history.setText("▶️ Fortsetzen")
            self.btn_pause_history.setStyleSheet("color: #e3b341;")
        else:
            self.btn_pause_history.setText("⏸️ Pause")
            self.btn_pause_history.setStyleSheet("")

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

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.show()
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            self.raise_()
            self.activateWindow()
            self.search_bar.set_focus()

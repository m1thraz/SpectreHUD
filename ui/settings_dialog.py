from typing import Dict, Any, Optional
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QComboBox, QCheckBox, 
    QStackedWidget, QFrame, QScrollArea, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFontDatabase, QStandardItemModel
from core.config import ConfigManager
from core.i18n import t
from core.theme_loader import ThemeLoader
from ui.base_dialog import BaseHudDialog
from ui.styles.fonts import (
    UI_FONT_OPTIONS,
    CODE_FONT_OPTIONS,
    REPORT_FONT_OPTIONS,
    get_font_family,
)

HOTKEY_PRESETS = [
    {"label": "Ctrl + Super + < (Standard)", "value": "<ctrl>+<cmd>+<"},
    {"label": "Ctrl + Super + Space", "value": "<ctrl>+<cmd>+<space>"},
    {"label": "Ctrl + Alt + S", "value": "<ctrl>+<alt>+s"},
    {"label": "Ctrl + Shift + H", "value": "<ctrl>+<shift>+h"},
    {"label": "F12 (Single Key)", "value": "<f12>"},
]

SNIP_PRESETS = [
    {"label": "Ctrl + Super + X (Standard)", "value": "<ctrl>+<cmd>+x"},
    {"label": "Ctrl + Super + S", "value": "<ctrl>+<cmd>+s"},
    {"label": "F11 (Single Key)", "value": "<f11>"},
]

QUIT_PRESETS = [
    {"label": "Ctrl + Super + Q (Standard)", "value": "<ctrl>+<cmd>+q"},
    {"label": "Ctrl + Alt + Q", "value": "<ctrl>+<alt>+q"},
    {"label": "Ctrl + Shift + Q", "value": "<ctrl>+<shift>+q"},
    {"label": "F10 (Single Key)", "value": "<f10>"},
]


def _configure_transparent_scroll_surfaces(scroll: QScrollArea) -> None:
    """Keep a scroll area's viewport and hosted page transparent to window glass."""
    scroll.setAutoFillBackground(False)
    scroll.viewport().setAutoFillBackground(False)
    content = scroll.widget()
    if content is not None:
        # QScrollArea.setWidget() enables auto-fill on the hosted widget.
        content.setAutoFillBackground(False)


class HotkeySettingsPage(QWidget):
    """Modular settings page for global and in-app keyboard shortcuts."""

    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config_manager
        self._init_ui()

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("SettingsScrollArea")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 4, 12, 8)
        layout.setSpacing(14)

        # 1. Global Hotkeys Section
        lbl_global = QLabel(t("settings.lbl_global_hotkeys", "Global Shortcuts (System-wide)"))
        lbl_global.setProperty("class", "SettingsSectionTitle")
        layout.addWidget(lbl_global)

        card_global = QFrame()
        card_global.setProperty("class", "SettingsCard")
        card_layout = QVBoxLayout(card_global)
        card_layout.setSpacing(12)

        # Overlay Toggle Hotkey
        row_toggle = QHBoxLayout()
        lbl_toggle = QLabel(t("settings.lbl_toggle_hotkey", "SpectreHUD Toggle Overlay:"))
        lbl_toggle.setProperty("class", "FormLabel")
        row_toggle.addWidget(lbl_toggle, stretch=1)

        self.combo_toggle = QComboBox()
        self.combo_toggle.setMinimumWidth(220)
        curr_hotkey = self.config.get("hotkey", "<ctrl>+<cmd>+<")
        for i, preset in enumerate(HOTKEY_PRESETS):
            self.combo_toggle.addItem(preset["label"], preset["value"])
            if preset["value"] == curr_hotkey:
                self.combo_toggle.setCurrentIndex(i)
        row_toggle.addWidget(self.combo_toggle, stretch=1)
        card_layout.addLayout(row_toggle)

        # Snip Tool Hotkey
        row_snip = QHBoxLayout()
        lbl_snip = QLabel(t("settings.lbl_snip_hotkey", "Screenshot Snip-Tool:"))
        lbl_snip.setProperty("class", "FormLabel")
        row_snip.addWidget(lbl_snip, stretch=1)

        self.combo_snip = QComboBox()
        self.combo_snip.setMinimumWidth(220)
        curr_snip = self.config.get("snip_hotkey", "<ctrl>+<cmd>+x")
        for i, preset in enumerate(SNIP_PRESETS):
            self.combo_snip.addItem(preset["label"], preset["value"])
            if preset["value"] == curr_snip:
                self.combo_snip.setCurrentIndex(i)
        row_snip.addWidget(self.combo_snip, stretch=1)
        card_layout.addLayout(row_snip)

        # Quit Shortcut
        row_quit = QHBoxLayout()
        lbl_quit = QLabel(t("settings.lbl_quit_shortcut", "Quit SpectreHUD Completely:"))
        lbl_quit.setProperty("class", "FormLabel")
        row_quit.addWidget(lbl_quit, stretch=1)

        self.combo_quit = QComboBox()
        self.combo_quit.setMinimumWidth(220)
        curr_quit = self.config.get("quit_hotkey", "<ctrl>+<cmd>+q")
        for i, preset in enumerate(QUIT_PRESETS):
            self.combo_quit.addItem(preset["label"], preset["value"])
            if preset["value"] == curr_quit:
                self.combo_quit.setCurrentIndex(i)
        row_quit.addWidget(self.combo_quit, stretch=1)
        card_layout.addLayout(row_quit)

        layout.addWidget(card_global)

        # 2. Local Overlay Shortcuts
        lbl_local = QLabel(t("settings.lbl_local_shortcuts", "In-App Shortcuts (Inside HUD)"))
        lbl_local.setProperty("class", "SettingsSectionTitle")
        layout.addWidget(lbl_local)

        card_local = QFrame()
        card_local.setProperty("class", "SettingsCard")
        local_layout = QVBoxLayout(card_local)
        local_layout.setSpacing(10)

        shortcuts = [
            ("Esc", t("settings.shortcut_esc", "Hide HUD overlay")),
            ("Ctrl + F", t("settings.shortcut_ctrl_f", "Focus spotlight command search")),
            ("Ctrl + N", t("settings.shortcut_ctrl_n", "Add new command / snippet")),
            ("Ctrl + P", t("settings.shortcut_ctrl_p", "Pause / resume clipboard recorder")),
            ("Ctrl + S", t("settings.shortcut_ctrl_s", "Capture region screenshot")),
            ("Ctrl + 1 / 2 / 3 / 4", t("settings.shortcut_modes", "Switch active mode (Cheatsheet, Loot, History, Report)")),
            ("Ctrl + ,", t("settings.shortcut_options", "Open settings & options")),
        ]

        for key_text, desc_text in shortcuts:
            row = QHBoxLayout()
            row.setContentsMargins(0, 1, 0, 1)
            lbl_desc = QLabel(desc_text)
            lbl_desc.setStyleSheet("color: #e6edf3; font-size: 12px;")
            row.addWidget(lbl_desc, stretch=1)

            lbl_key = QLabel(key_text)
            lbl_key.setProperty("class", "ShortcutKeyBadge")
            lbl_key.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(lbl_key, alignment=Qt.AlignmentFlag.AlignRight)
            local_layout.addLayout(row)

        layout.addWidget(card_local)

        # Reset button
        row_reset = QHBoxLayout()
        row_reset.addStretch()
        self.btn_reset_defaults = QPushButton(t("settings.btn_reset_defaults", "Restore Default Hotkeys"))
        self.btn_reset_defaults.setProperty("class", "SecondaryBtn")
        self.btn_reset_defaults.clicked.connect(self._reset_defaults)
        row_reset.addWidget(self.btn_reset_defaults)
        layout.addLayout(row_reset)

        layout.addStretch()
        scroll.setWidget(content)
        _configure_transparent_scroll_surfaces(scroll)
        outer_layout.addWidget(scroll)

    def _reset_defaults(self) -> None:
        self.combo_toggle.setCurrentIndex(0)
        self.combo_snip.setCurrentIndex(0)
        self.combo_quit.setCurrentIndex(0)

    def get_settings(self) -> Dict[str, Any]:
        return {
            "hotkey": self.combo_toggle.currentData() or "<ctrl>+<cmd>+<",
            "snip_hotkey": self.combo_snip.currentData() or "<ctrl>+<cmd>+x",
            "quit_hotkey": self.combo_quit.currentData() or "<ctrl>+<cmd>+q",
        }


class LanguageSettingsPage(QWidget):
    """Modular settings page for i18n language and regional settings."""

    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config_manager
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 12, 8)
        layout.setSpacing(14)

        lbl_lang = QLabel(t("settings.lbl_language_section", "Language and Regional Settings"))
        lbl_lang.setProperty("class", "SettingsSectionTitle")
        layout.addWidget(lbl_lang)

        card_lang = QFrame()
        card_lang.setProperty("class", "SettingsCard")
        card_layout = QVBoxLayout(card_lang)
        card_layout.setSpacing(14)

        # Language dropdown
        row_lang = QHBoxLayout()
        lbl_select = QLabel(t("settings.lbl_ui_language", "User Interface Language:"))
        lbl_select.setProperty("class", "FormLabel")
        row_lang.addWidget(lbl_select, stretch=1)

        self.combo_lang = QComboBox()
        self.combo_lang.setMinimumWidth(220)
        curr_lang = self.config.get("language", "de")
        for i, (code, name) in enumerate([("de", "Deutsch (German)"), ("en", "English (US)")]):
            self.combo_lang.addItem(name, code)
            if code == curr_lang:
                self.combo_lang.setCurrentIndex(i)
        row_lang.addWidget(self.combo_lang, stretch=1)
        card_layout.addLayout(row_lang)

        # Date Format
        row_date = QHBoxLayout()
        lbl_date = QLabel(t("settings.lbl_date_format", "Date & Time Format:"))
        lbl_date.setProperty("class", "FormLabel")
        row_date.addWidget(lbl_date, stretch=1)

        self.combo_date = QComboBox()
        self.combo_date.setMinimumWidth(220)
        self.combo_date.addItem("24-Stunden (YYYY-MM-DD HH:mm:ss)", "24h")
        self.combo_date.addItem("12-Stunden AM/PM (YYYY-MM-DD hh:mm:ss a)", "12h")
        curr_time_fmt = self.config.get("time_format", "24h")
        if curr_time_fmt == "12h":
            self.combo_date.setCurrentIndex(1)
        row_date.addWidget(self.combo_date, stretch=1)
        card_layout.addLayout(row_date)

        layout.addWidget(card_lang)
        layout.addStretch()

    def get_settings(self) -> Dict[str, Any]:
        return {
            "language": self.combo_lang.currentData() or "de",
            "time_format": self.combo_date.currentData() or "24h"
        }


class AppearanceSettingsPage(QWidget):
    """Settings page for themes, typography, and Loot presentation."""

    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config_manager
        self._init_ui()

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("SettingsScrollArea")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 4, 12, 8)
        layout.setSpacing(14)

        lbl_theme_section = QLabel(t("settings.lbl_theme_section", "Application Theme"))
        lbl_theme_section.setProperty("class", "SettingsSectionTitle")
        layout.addWidget(lbl_theme_section)

        card_theme = QFrame()
        card_theme.setProperty("class", "SettingsCard")
        theme_layout = QVBoxLayout(card_theme)
        theme_layout.setSpacing(10)

        self.theme_loader = ThemeLoader()
        self.combo_theme = QComboBox()
        current_theme = self.config.get("theme", ThemeLoader.FALLBACK_THEME_ID)
        for theme in self.theme_loader.list_themes():
            label = theme["name"]
            if theme.get("author"):
                label = f"{label} — {theme['author']}"
            self.combo_theme.addItem(label, theme["id"])
        theme_index = self.combo_theme.findData(current_theme)
        self.combo_theme.setCurrentIndex(theme_index if theme_index >= 0 else 0)

        theme_row = QHBoxLayout()
        theme_label = QLabel(t("settings.lbl_theme", "Theme:"))
        theme_label.setProperty("class", "FormLabel")
        theme_row.addWidget(theme_label)
        theme_row.addWidget(self.combo_theme, stretch=1)
        self.btn_open_theme_folder = QPushButton(
            t("settings.open_theme_folder", "Open custom themes...")
        )
        self.btn_open_theme_folder.setProperty("class", "BrowseBtn")
        self.btn_open_theme_folder.clicked.connect(self._open_theme_folder)
        theme_row.addWidget(self.btn_open_theme_folder)
        theme_layout.addLayout(theme_row)

        restart_hint = QLabel(
            t(
                "settings.theme_restart_hint",
                "Selecting a different theme restarts SpectreHUD after the settings are saved.",
            )
        )
        restart_hint.setProperty("class", "HintLabel")
        restart_hint.setWordWrap(True)
        theme_layout.addWidget(restart_hint)
        layout.addWidget(card_theme)

        lbl_typography = QLabel(t("settings.lbl_typography_section", "Typography"))
        lbl_typography.setProperty("class", "SettingsSectionTitle")
        layout.addWidget(lbl_typography)

        card_typography = QFrame()
        card_typography.setProperty("class", "SettingsCard")
        typography_layout = QVBoxLayout(card_typography)
        typography_layout.setSpacing(10)

        self.combo_ui_font = self._font_combo(UI_FONT_OPTIONS, self.config.get("ui_font", "segoe_ui"))
        self.combo_code_font = self._font_combo(CODE_FONT_OPTIONS, self.config.get("code_font", "consolas"))
        self.combo_report_font = self._font_combo(REPORT_FONT_OPTIONS, self.config.get("report_font", "segoe_ui"))
        for label, combo in (
            (t("settings.lbl_app_font", "Application font:"), self.combo_ui_font),
            (t("settings.lbl_code_font", "Code font:"), self.combo_code_font),
            (t("settings.lbl_report_font", "Report font (preview and HTML export):"), self.combo_report_font),
        ):
            row = QHBoxLayout()
            label_widget = QLabel(label)
            label_widget.setProperty("class", "FormLabel")
            row.addWidget(label_widget)
            row.addWidget(combo, stretch=1)
            typography_layout.addLayout(row)
        layout.addWidget(card_typography)

        lbl_loot_display = QLabel(t("settings.lbl_loot_display_section", "Loot Presentation"))
        lbl_loot_display.setProperty("class", "SettingsSectionTitle")
        layout.addWidget(lbl_loot_display)

        card_loot_display = QFrame()
        card_loot_display.setProperty("class", "SettingsCard")
        loot_display_layout = QVBoxLayout(card_loot_display)
        self.chk_loot_board = QCheckBox(
            t("settings.chk_loot_board", "Show Loot as Kanban board")
        )
        self.chk_loot_board.setToolTip(
            t(
                "settings.chk_loot_board_tip",
                "Organize loot by pentest phase and move entries between columns.",
            )
        )
        self.chk_loot_board.setChecked(self.config.get("loot_view_mode", "list") == "board")
        loot_display_layout.addWidget(self.chk_loot_board)
        layout.addWidget(card_loot_display)

        layout.addStretch()
        scroll.setWidget(content)
        _configure_transparent_scroll_surfaces(scroll)
        outer_layout.addWidget(scroll)

    @staticmethod
    def _font_combo(options, selected_key: str) -> QComboBox:
        combo = QComboBox()
        available_families = {
            family.casefold() for family in QFontDatabase.families()
        }
        for key, label in options:
            is_available = get_font_family(key).casefold() in available_families
            display_label = label
            if not is_available:
                display_label = f"{label} — {t('settings.font_not_installed', 'Not installed')}"
            combo.addItem(display_label, key)
            if not is_available:
                model = combo.model()
                if isinstance(model, QStandardItemModel):
                    item = model.item(combo.count() - 1)
                    if item is not None:
                        item.setEnabled(False)
        index = combo.findData(selected_key)
        if index < 0:
            model = combo.model()
            index = next(
                (
                    item_index
                    for item_index in range(combo.count())
                    if model.flags(model.index(item_index, 0)) & Qt.ItemFlag.ItemIsEnabled
                ),
                0,
            )
        combo.setCurrentIndex(index)
        return combo

    def _open_theme_folder(self) -> None:
        try:
            self.theme_loader.USER_THEMES_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(
                self,
                t("settings.theme_folder_error_title", "Theme folder unavailable"),
                t(
                    "settings.theme_folder_error_message",
                    "The custom theme folder could not be created:\n{error}",
                    error=str(exc),
                ),
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.theme_loader.USER_THEMES_DIR)))

    def get_settings(self) -> Dict[str, Any]:
        return {
            "theme": self.combo_theme.currentData() or ThemeLoader.FALLBACK_THEME_ID,
            "ui_font": self.combo_ui_font.currentData() or "segoe_ui",
            "code_font": self.combo_code_font.currentData() or "consolas",
            "report_font": self.combo_report_font.currentData() or "segoe_ui",
            "loot_view_mode": "board" if self.chk_loot_board.isChecked() else "list",
        }


class GeneralSettingsPage(QWidget):
    """Modular settings page for overlay behavior and default parameters."""

    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config_manager
        self._init_ui()

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("SettingsScrollArea")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 4, 12, 8)
        layout.setSpacing(14)

        # 1. Behavior Section
        lbl_behavior = QLabel(t("settings.lbl_behavior_section", "Overlay Behavior"))
        lbl_behavior.setProperty("class", "SettingsSectionTitle")
        layout.addWidget(lbl_behavior)

        card_behavior = QFrame()
        card_behavior.setProperty("class", "SettingsCard")
        b_layout = QVBoxLayout(card_behavior)
        b_layout.setSpacing(10)

        self.chk_always_on_top = QCheckBox(
            t("settings.chk_always_on_top", "Keep overlay always in foreground over other windows")
        )
        self.chk_always_on_top.setChecked(self.config.get("always_on_top", True))
        b_layout.addWidget(self.chk_always_on_top)

        self.chk_auto_hide = QCheckBox(
            t("settings.chk_auto_hide", "Automatically minimize overlay after copying command")
        )
        self.chk_auto_hide.setChecked(self.config.get("auto_hide_on_copy", False))
        b_layout.addWidget(self.chk_auto_hide)

        layout.addWidget(card_behavior)

        # 2. Defaults Section
        lbl_defaults = QLabel(t("settings.lbl_defaults_section", "Default Parameters"))
        lbl_defaults.setProperty("class", "SettingsSectionTitle")
        layout.addWidget(lbl_defaults)

        card_defaults = QFrame()
        card_defaults.setProperty("class", "SettingsCard")
        d_layout = QVBoxLayout(card_defaults)
        d_layout.setSpacing(12)

        # Default Target & Attacker IP
        row_ips = QHBoxLayout()
        row_ips.setSpacing(12)

        col_target = QVBoxLayout()
        lbl_t = QLabel(t("settings.lbl_default_target", "Default Target IP:"))
        lbl_t.setProperty("class", "FormLabel")
        col_target.addWidget(lbl_t)
        self.txt_default_target = QLineEdit(self.config.get("target_ip", "10.10.10.10"))
        col_target.addWidget(self.txt_default_target)
        row_ips.addLayout(col_target, stretch=1)

        col_attacker = QVBoxLayout()
        lbl_a = QLabel(t("settings.lbl_default_attacker", "Default LHOST IP:"))
        lbl_a.setProperty("class", "FormLabel")
        col_attacker.addWidget(lbl_a)
        self.txt_default_attacker = QLineEdit(self.config.get("attacker_ip", "10.10.14.5"))
        col_attacker.addWidget(self.txt_default_attacker)
        row_ips.addLayout(col_attacker, stretch=1)

        d_layout.addLayout(row_ips)

        # Default Wordlist
        lbl_w = QLabel(t("settings.lbl_default_wordlist", "Default Wordlist Path:"))
        lbl_w.setProperty("class", "FormLabel")
        d_layout.addWidget(lbl_w)

        row_w = QHBoxLayout()
        self.txt_wordlist = QLineEdit(self.config.get("wordlist", "/usr/share/wordlists/dirb/common.txt"))
        row_w.addWidget(self.txt_wordlist, stretch=1)

        btn_browse_w = QPushButton(t("dialog.browse", "Browse..."))
        btn_browse_w.setProperty("class", "BrowseBtn")
        btn_browse_w.clicked.connect(self._on_browse_wordlist)
        row_w.addWidget(btn_browse_w)
        d_layout.addLayout(row_w)

        # Default Workspace Directory
        lbl_ws = QLabel(t("settings.lbl_default_workspace", "Default Workspace / Projects Directory:"))
        lbl_ws.setProperty("class", "FormLabel")
        d_layout.addWidget(lbl_ws)

        row_ws = QHBoxLayout()
        self.txt_workspace = QLineEdit(self.config.get("workspace_dir", str(Path.home() / "spectre_projects")))
        row_ws.addWidget(self.txt_workspace, stretch=1)

        btn_browse_ws = QPushButton(t("dialog.browse", "Browse..."))
        btn_browse_ws.setProperty("class", "BrowseBtn")
        btn_browse_ws.clicked.connect(self._on_browse_workspace)
        row_ws.addWidget(btn_browse_ws)
        d_layout.addLayout(row_ws)

        # Optional Obsidian one-way export destination.  The vault must already
        # exist; only the configured export subfolder is created on demand.
        lbl_obsidian = QLabel(t("settings.lbl_obsidian_vault", "Obsidian Vault (optional):"))
        lbl_obsidian.setProperty("class", "FormLabel")
        d_layout.addWidget(lbl_obsidian)
        row_obsidian = QHBoxLayout()
        self.txt_obsidian_vault = QLineEdit(self.config.get("obsidian_vault_path", ""))
        self.txt_obsidian_vault.setPlaceholderText(t("settings.obsidian_vault_placeholder", "Select an existing Obsidian vault"))
        row_obsidian.addWidget(self.txt_obsidian_vault, stretch=1)
        btn_browse_obsidian = QPushButton(t("dialog.browse", "Browse..."))
        btn_browse_obsidian.setProperty("class", "BrowseBtn")
        btn_browse_obsidian.clicked.connect(self._on_browse_obsidian_vault)
        row_obsidian.addWidget(btn_browse_obsidian)
        d_layout.addLayout(row_obsidian)

        row_obsidian_folder = QHBoxLayout()
        lbl_obsidian_folder = QLabel(t("settings.lbl_obsidian_folder", "Obsidian export folder:"))
        lbl_obsidian_folder.setProperty("class", "FormLabel")
        row_obsidian_folder.addWidget(lbl_obsidian_folder)
        self.txt_obsidian_folder = QLineEdit(self.config.get("obsidian_export_folder", "CTF/SpectreHUD"))
        row_obsidian_folder.addWidget(self.txt_obsidian_folder, stretch=1)
        d_layout.addLayout(row_obsidian_folder)
        self.chk_obsidian_open = QCheckBox(t("settings.chk_obsidian_open", "Open exported note in Obsidian"))
        self.chk_obsidian_open.setChecked(self.config.get("obsidian_open_after_export", False))
        d_layout.addWidget(self.chk_obsidian_open)

        layout.addWidget(card_defaults)
        layout.addStretch()
        scroll.setWidget(content)
        _configure_transparent_scroll_surfaces(scroll)
        outer_layout.addWidget(scroll)

    def _on_browse_wordlist(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, t("settings.lbl_default_wordlist", "Default Wordlist Path:"), self.txt_wordlist.text().strip())
        if file_path:
            self.txt_wordlist.setText(file_path)

    def _on_browse_workspace(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, t("settings.lbl_default_workspace", "Default Workspace / Projects Directory:"), self.txt_workspace.text().strip())
        if folder:
            self.txt_workspace.setText(folder)

    def _on_browse_obsidian_vault(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, t("settings.lbl_obsidian_vault", "Obsidian Vault (optional):"), self.txt_obsidian_vault.text().strip())
        if folder:
            self.txt_obsidian_vault.setText(folder)

    def get_settings(self) -> Dict[str, Any]:
        return {
            "always_on_top": self.chk_always_on_top.isChecked(),
            "auto_hide_on_copy": self.chk_auto_hide.isChecked(),
            "target_ip": self.txt_default_target.text().strip(),
            "attacker_ip": self.txt_default_attacker.text().strip(),
            "wordlist": self.txt_wordlist.text().strip(),
            "workspace_dir": self.txt_workspace.text().strip(),
            "obsidian_vault_path": self.txt_obsidian_vault.text().strip(),
            "obsidian_export_folder": self.txt_obsidian_folder.text().strip() or "CTF/SpectreHUD",
            "obsidian_open_after_export": self.chk_obsidian_open.isChecked(),
        }


class SettingsDialog(BaseHudDialog):
    """
    Modular, frameless cyber settings dialog with sidebar navigation
    supporting Hotkeys, Language, General, and Appearance configuration.
    """

    settings_applied = pyqtSignal(dict)

    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(
            title=t("settings.title", "SPECTRE // SETTINGS & OPTIONS"),
            parent=parent
        )
        self.config = config_manager
        self.setMinimumWidth(720)
        self.setMinimumHeight(480)
        self.resize(780, 560)
        self._init_layout()

    def _init_layout(self) -> None:
        main_layout = self.body_layout
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Horizontal layout: Sidebar (left) + Stacked Pages (right)
        split_layout = QHBoxLayout()
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(0)

        # 1. Sidebar Navigation
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("SettingsSidebar")
        self.sidebar_frame.setFixedWidth(190)
        
        sidebar_layout = QVBoxLayout(self.sidebar_frame)
        sidebar_layout.setContentsMargins(8, 12, 8, 12)
        sidebar_layout.setSpacing(6)

        self.btn_nav_hotkeys = QPushButton(t("settings.nav_hotkeys", "Hotkeys & Shortcuts"))
        self.btn_nav_hotkeys.setProperty("class", "SettingsNavBtnActive")
        self.btn_nav_hotkeys.clicked.connect(lambda: self.switch_page(0))
        sidebar_layout.addWidget(self.btn_nav_hotkeys)

        self.btn_nav_language = QPushButton(t("settings.nav_language", "Language & Region"))
        self.btn_nav_language.setProperty("class", "SettingsNavBtn")
        self.btn_nav_language.clicked.connect(lambda: self.switch_page(1))
        sidebar_layout.addWidget(self.btn_nav_language)

        self.btn_nav_general = QPushButton(t("settings.nav_general", "General"))
        self.btn_nav_general.setProperty("class", "SettingsNavBtn")
        self.btn_nav_general.clicked.connect(lambda: self.switch_page(2))
        sidebar_layout.addWidget(self.btn_nav_general)

        self.btn_nav_appearance = QPushButton(t("settings.nav_appearance", "Appearance"))
        self.btn_nav_appearance.setProperty("class", "SettingsNavBtn")
        self.btn_nav_appearance.clicked.connect(lambda: self.switch_page(3))
        sidebar_layout.addWidget(self.btn_nav_appearance)

        sidebar_layout.addStretch()
        split_layout.addWidget(self.sidebar_frame)

        # 2. Right Page Container
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(14, 10, 14, 10)
        right_layout.setSpacing(10)

        # Stacked Pages
        self.stack = QStackedWidget()
        
        self.page_hotkeys = HotkeySettingsPage(self.config)
        self.page_language = LanguageSettingsPage(self.config)
        self.page_general = GeneralSettingsPage(self.config)
        self.page_appearance = AppearanceSettingsPage(self.config)

        self.stack.addWidget(self.page_hotkeys)
        self.stack.addWidget(self.page_language)
        self.stack.addWidget(self.page_general)
        self.stack.addWidget(self.page_appearance)
        
        right_layout.addWidget(self.stack, stretch=1)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        lbl_hint = QLabel(t("snippet_dialog.btn_hint", "↵ Enter: Save | Esc: Cancel"))
        lbl_hint.setStyleSheet("color: #8b949e; font-size: 11px;")
        btn_layout.addWidget(lbl_hint)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton(t("dialog.cancel", "Cancel"))
        self.btn_cancel.setProperty("class", "SecondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(t("settings.save_apply", "Save & Apply"))
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.clicked.connect(self._on_save_settings)
        btn_layout.addWidget(self.btn_save)

        right_layout.addLayout(btn_layout)
        split_layout.addWidget(right_container, stretch=1)

        main_layout.addLayout(split_layout)

    def switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        buttons = [
            self.btn_nav_hotkeys,
            self.btn_nav_language,
            self.btn_nav_general,
            self.btn_nav_appearance,
        ]
        for i, btn in enumerate(buttons):
            btn.setProperty("class", "SettingsNavBtnActive" if i == index else "SettingsNavBtn")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_save_settings(self) -> None:
        """Commits non-workspace settings, then requests runtime workspace activation.

        ``workspace_dir`` is intentionally not written here: AppController commits it
        only after the corresponding runtime switch has completed successfully.
        """
        from core.storage import PersistenceError
        all_settings: Dict[str, Any] = {}
        all_settings.update(self.page_hotkeys.get_settings())
        all_settings.update(self.page_language.get_settings())
        all_settings.update(self.page_general.get_settings())
        all_settings.update(self.page_appearance.get_settings())

        if "workspace_dir" in all_settings and all_settings["workspace_dir"]:
            from core.project.validator import validate_workspace_directory, WorkspaceError
            try:
                validate_workspace_directory(all_settings["workspace_dir"])
            except WorkspaceError as e:
                QMessageBox.warning(
                    self,
                    "Ungültiger Workspace-Pfad",
                    f"Das ausgewählte Workspace-Verzeichnis ist ungültig oder nicht beschreibbar:\n{e}"
                )
                return

        if all_settings.get("obsidian_vault_path"):
            from core.exporters import ExternalExportError, ObsidianExporter
            try:
                ObsidianExporter(
                    all_settings["obsidian_vault_path"],
                    all_settings.get("obsidian_export_folder", "CTF/SpectreHUD"),
                )
            except ExternalExportError as exc:
                QMessageBox.warning(
                    self,
                    t("settings.obsidian_invalid_title", "Invalid Obsidian settings"),
                    t("settings.obsidian_invalid_message", "The Obsidian vault or export folder is invalid:\n{error}", error=str(exc)),
                )
                return

        # A workspace change also requires a runtime switch in AppController.
        # Persist the remaining settings now, but let the controller commit the
        # workspace only after that switch succeeded.
        settings_to_persist = dict(all_settings)
        settings_to_persist.pop("workspace_dir", None)
        try:
            self.config.update(settings_to_persist)
        except PersistenceError as e:
            QMessageBox.critical(
                self,
                "Speichern fehlgeschlagen",
                f"Die Einstellungen konnten nicht gespeichert werden:\n{e}"
            )
            return

        if "language" in all_settings:
            from core.i18n import set_locale
            set_locale(all_settings["language"])

        self.settings_applied.emit(all_settings)
        self.accept()

"""
Modern Cyber Dark Glassmorphism / HUD Overlay Stylesheet for the CTF Cheatsheet Widget, Loot Manager & Projects.
"""

CYBER_DARK_QSS = """
/* Transparent Base Container */
QWidget#CentralWidget {
    background-color: transparent;
    font-family: 'Segoe UI', 'SF Pro Display', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
    color: #c9d1d9;
}

/* Outer HUD Frame with Glassmorphism / Acrylic Glow */
QFrame#HudFrame {
    background-color: rgba(13, 17, 23, 0.95);
    border: 1px solid rgba(0, 229, 255, 0.35);
    border-radius: 14px;
}

/* Header & Mode Switcher Bar */
QFrame#HeaderBar {
    background-color: rgba(22, 27, 34, 0.7);
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    border-bottom: 1px solid rgba(48, 54, 61, 0.5);
    padding: 8px 12px;
}

QPushButton.ModeSwitchBtn {
    background-color: rgba(13, 17, 23, 0.7);
    color: #8b949e;
    border: 1px solid rgba(48, 54, 61, 0.7);
    border-radius: 6px;
    padding: 4px 9px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.ModeSwitchBtn:hover {
    background-color: rgba(33, 38, 45, 0.9);
    color: #f0f6fc;
}

QPushButton.ModeSwitchBtnActive {
    background-color: rgba(31, 41, 61, 0.9);
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-radius: 6px;
    padding: 4px 9px;
    font-size: 11px;
    font-weight: bold;
}

/* Project Selector Button */
QPushButton.ProjectSelectBtn {
    background-color: rgba(31, 41, 61, 0.6);
    color: #58a6ff;
    border: 1px solid rgba(56, 139, 253, 0.4);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.ProjectSelectBtn:hover {
    background-color: rgba(56, 139, 253, 0.25);
    color: #00e5ff;
    border-color: #00e5ff;
}

QPushButton.ScreenshotBtn {
    background-color: rgba(0, 229, 255, 0.12);
    color: #00e5ff;
    border: 1px solid rgba(0, 229, 255, 0.4);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.ScreenshotBtn:hover {
    background-color: rgba(0, 229, 255, 0.25);
    border-color: #00e5ff;
}

/* Dark QMenu for Dropdowns */
QMenu {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 6px;
    color: #c9d1d9;
    font-size: 12px;
}

QMenu::item {
    background-color: transparent;
    padding: 6px 16px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #1f293d;
    color: #00e5ff;
}

QMenu::separator {
    height: 1px;
    background-color: #30363d;
    margin: 4px 8px;
}

/* Spotlight Search Section */
QFrame#SearchSection {
    background-color: transparent;
    padding: 6px 12px;
}

QLineEdit#SpotlightSearch {
    background-color: rgba(13, 17, 23, 0.85);
    border: 1px solid rgba(88, 166, 255, 0.25);
    border-radius: 10px;
    color: #ffffff;
    padding: 8px 14px;
    font-size: 14px;
    font-weight: 500;
}

QLineEdit#SpotlightSearch:focus {
    border: 1px solid #00e5ff;
    background-color: rgba(10, 16, 29, 0.95);
}

/* Filter Chips / Pills Bar */
QFrame#FilterPillsFrame {
    background-color: transparent;
    padding: 2px 10px 6px 10px;
    border-bottom: 1px solid rgba(48, 54, 61, 0.4);
}

QPushButton.FilterPill {
    background-color: rgba(22, 27, 34, 0.8);
    color: #8b949e;
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.FilterPill:hover {
    background-color: rgba(33, 38, 45, 0.9);
    color: #f0f6fc;
    border-color: rgba(88, 166, 255, 0.4);
}

QPushButton.FilterPillActive {
    background-color: #1f293d;
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}

/* Compact Variable Status Bar */
QFrame#CompactVarBar {
    background-color: rgba(17, 22, 29, 0.8);
    border-bottom: 1px solid rgba(48, 54, 61, 0.4);
    padding: 5px 12px;
}

QLabel.VarTagLabel {
    color: #8b949e;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}

QLineEdit.CompactVarInput {
    background-color: rgba(13, 17, 23, 0.8);
    border: 1px solid rgba(48, 54, 61, 0.6);
    border-radius: 5px;
    color: #58a6ff;
    padding: 3px 8px;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    font-weight: 600;
}

QLineEdit.CompactVarInput:focus {
    border: 1px solid #58a6ff;
    background-color: rgba(16, 23, 38, 0.9);
}

QPushButton.AutoDetectBtn {
    background-color: rgba(31, 41, 61, 0.6);
    color: #58a6ff;
    border: 1px solid rgba(56, 139, 253, 0.3);
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.AutoDetectBtn:hover {
    background-color: rgba(56, 139, 253, 0.2);
    color: #00e5ff;
    border-color: #00e5ff;
}

QPushButton.MiniPrimaryBtn {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    border-radius: 5px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.MiniPrimaryBtn:hover {
    background-color: #2ea043;
}

/* Loot Badges */
QLabel.LootBadge {
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: bold;
    text-transform: uppercase;
}

QLabel.BadgeCreds {
    background-color: rgba(210, 153, 34, 0.2);
    color: #e3b341;
    border: 1px solid rgba(210, 153, 34, 0.4);
}

QLabel.BadgeHash {
    background-color: rgba(163, 113, 247, 0.2);
    color: #bc8cff;
    border: 1px solid rgba(163, 113, 247, 0.4);
}

QLabel.BadgeFlag {
    background-color: rgba(63, 185, 80, 0.2);
    color: #56d364;
    border: 1px solid rgba(63, 185, 80, 0.4);
}

QLabel.BadgeScreenshot {
    background-color: rgba(0, 229, 255, 0.2);
    color: #00e5ff;
    border: 1px solid rgba(0, 229, 255, 0.4);
}

QLabel.BadgeDir {
    background-color: rgba(56, 139, 253, 0.2);
    color: #79c0ff;
    border: 1px solid rgba(56, 139, 253, 0.4);
}

QLabel.BadgeNote {
    background-color: rgba(110, 118, 129, 0.2);
    color: #8b949e;
    border: 1px solid rgba(110, 118, 129, 0.4);
}

/* Pentest Category Badge */
QLabel.CategoryBadge {
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: 600;
    background-color: rgba(56, 139, 253, 0.12);
    color: #58a6ff;
    border: 1px solid rgba(56, 139, 253, 0.3);
}

/* Loot Group Section Header */
QLabel.LootSectionHeader {
    color: #8b949e;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 10px 4px 2px 4px;
    background-color: transparent;
}

QPushButton.EditBtn {
    background-color: rgba(33, 38, 45, 0.7);
    color: #8b949e;
    border: 1px solid rgba(48, 54, 61, 0.6);
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 11px;
}

QPushButton.EditBtn:hover {
    background-color: rgba(56, 139, 253, 0.2);
    color: #58a6ff;
    border-color: #58a6ff;
}

QPushButton.ScreenshotBtn {
    background-color: rgba(0, 229, 255, 0.15);
    color: #00e5ff;
    border: 1px solid rgba(0, 229, 255, 0.4);
    border-radius: 7px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.ScreenshotBtn:hover {
    background-color: #00e5ff;
    color: #0d1117;
}

QLabel.BadgeNote {
    background-color: rgba(139, 148, 158, 0.2);
    color: #c9d1d9;
    border: 1px solid rgba(139, 148, 158, 0.4);
}

/* Snippet & Loot Cards */
QFrame#SnippetCard {
    background-color: rgba(22, 27, 34, 0.7);
    border: 1px solid rgba(48, 54, 61, 0.6);
    border-radius: 8px;
    margin-bottom: 6px;
    padding: 8px 12px;
}

QFrame#SnippetCard:hover {
    border: 1px solid rgba(0, 229, 255, 0.5);
    background-color: rgba(26, 33, 44, 0.85);
}

QLabel#SnippetTitle {
    color: #f0f6fc;
    font-size: 13px;
    font-weight: 600;
}

QLabel#SnippetCategory {
    color: #8b949e;
    font-size: 11px;
    font-weight: 500;
}

QLabel#SnippetDesc {
    color: #8b949e;
    font-size: 11px;
}

QLabel#CommandLabel {
    background-color: rgba(9, 13, 18, 0.92);
    border: 1px solid rgba(33, 38, 45, 0.9);
    border-radius: 6px;
    color: #39d353;
    font-family: 'Consolas', 'Cascadia Code', 'Fira Code', monospace;
    font-size: 12px;
    padding: 7px 10px;
    selection-background-color: #1f3d29;
}

QPlainTextEdit#CommandBox {
    background-color: rgba(9, 13, 18, 0.9);
    border: 1px solid rgba(33, 38, 45, 0.8);
    border-radius: 6px;
    color: #39d353;
    font-family: 'Consolas', 'Cascadia Code', 'Fira Code', monospace;
    font-size: 12px;
    padding: 6px 8px;
    selection-background-color: #1f3d29;
}

/* Copy Buttons */
QPushButton.CopyBtn {
    background-color: rgba(31, 41, 61, 0.8);
    color: #58a6ff;
    border: 1px solid rgba(56, 139, 253, 0.3);
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: 600;
    font-size: 12px;
}

QPushButton.CopyBtn:hover {
    background-color: #388bfd;
    color: #ffffff;
}

QPushButton.CopyBtnSuccess {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #39d353;
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: bold;
    font-size: 12px;
}

QPushButton.DangerBtn {
    background-color: transparent;
    color: #f85149;
    border: 1px solid rgba(218, 54, 51, 0.3);
    border-radius: 5px;
    padding: 3px 6px;
    font-size: 10px;
}

QPushButton.DangerBtn:hover {
    background-color: #da3633;
    color: #ffffff;
}

/* Secondary & Action Buttons */
QPushButton.SecondaryBtn {
    background-color: rgba(33, 38, 45, 0.8);
    color: #c9d1d9;
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 6px;
    padding: 5px 12px;
}

QPushButton.SecondaryBtn:hover {
    background-color: rgba(48, 54, 61, 0.9);
    color: #f0f6fc;
}

QPushButton.PrimaryBtn {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}

QPushButton.PrimaryBtn:hover {
    background-color: #2ea043;
}

/* Modern Ultra-Slim Scrollbars */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 2px 0px 2px 0px;
}

QScrollBar::handle:vertical {
    background: rgba(48, 54, 61, 0.6);
    min-height: 20px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #00e5ff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* REC Indicator & Privacy Warning */
QPushButton#RecIndicatorBtn {
    background-color: rgba(248, 81, 73, 0.2);
    border: 1px solid rgba(248, 81, 73, 0.7);
    border-radius: 4px;
    color: #ff7b72;
    font-size: 11px;
    font-weight: 800;
    padding: 3px 8px;
    letter-spacing: 0.5px;
}

QPushButton#RecIndicatorBtn:hover {
    background-color: rgba(248, 81, 73, 0.35);
    border-color: #ff7b72;
}

QPushButton#RecIndicatorBtn[paused="true"] {
    background-color: rgba(110, 118, 129, 0.15);
    border: 1px solid rgba(110, 118, 129, 0.4);
    color: #8b949e;
}

QPushButton#RecIndicatorBtn[paused="true"]:hover {
    background-color: rgba(110, 118, 129, 0.3);
    color: #c9d1d9;
}

QFrame#PrivacyWarningBanner {
    background-color: rgba(210, 153, 34, 0.12);
    border: 1px solid rgba(210, 153, 34, 0.35);
    border-radius: 6px;
    padding: 6px 10px;
    margin: 4px 0px;
}

QLabel#PrivacyWarningText {
    color: #e3b341;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.MiniActionBtn {
    background-color: rgba(33, 38, 45, 0.85);
    color: #c9d1d9;
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 6px;
    padding: 3px 9px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.MiniActionBtn:hover {
    background-color: rgba(48, 54, 61, 0.95);
    color: #00e5ff;
    border-color: rgba(0, 229, 255, 0.4);
}

QPushButton.MiniDangerBtn {
    background-color: transparent;
    color: #f85149;
    border: 1px solid rgba(218, 54, 51, 0.35);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.MiniDangerBtn:hover {
    background-color: rgba(218, 54, 51, 0.2);
    border-color: #f85149;
}

/* Custom Size Grip in Footer */
QSizeGrip {
    background-color: transparent;
    width: 14px;
    height: 14px;
    margin-right: -4px;
    margin-bottom: -2px;
}

/* Minimal HUD Footer */
QFrame#HudFooter {
    background-color: rgba(17, 22, 29, 0.7);
    border-top: 1px solid rgba(48, 54, 61, 0.4);
    border-bottom-left-radius: 14px;
    border-bottom-right-radius: 14px;
    padding: 5px 14px;
}

QLabel#FooterText {
    color: #6e7681;
    font-size: 11px;
}

/* Always on Top Checkbox in Footer */
QCheckBox#AlwaysOnTopCheck {
    color: #8b949e;
    font-size: 11px;
    font-weight: 500;
    spacing: 5px;
    margin-right: 4px;
}

QCheckBox#AlwaysOnTopCheck:hover {
    color: #58a6ff;
}

QCheckBox#AlwaysOnTopCheck:checked {
    color: #00e5ff;
    font-weight: 600;
}

QCheckBox#AlwaysOnTopCheck::indicator {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    border: 1px solid rgba(88, 166, 255, 0.4);
    background-color: rgba(13, 17, 23, 0.8);
}

QCheckBox#AlwaysOnTopCheck::indicator:hover {
    border-color: #00e5ff;
    background-color: rgba(31, 41, 61, 0.8);
}

QCheckBox#AlwaysOnTopCheck::indicator:checked {
    background-color: #00e5ff;
    border-color: #00e5ff;
}

/* Report Editor & Preview */
QPlainTextEdit.ReportSourceEditor {
    background-color: rgba(13, 17, 23, 0.95);
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px;
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    font-size: 12px;
}

QPlainTextEdit.ReportSourceEditor:focus {
    border: 1px solid #58a6ff;
}

QTextEdit.ReportPreview {
    background-color: rgba(17, 22, 29, 0.9);
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 12px;
    font-size: 13px;
}

QLabel.ReportStatusLabel {
    color: #8b949e;
    font-size: 12px;
    font-weight: 500;
}

/* QSplitter */
QSplitter::handle {
    background-color: #30363d;
    width: 4px;
    height: 4px;
}

QSplitter::handle:hover {
    background-color: #00e5ff;
}

/* Frameless HUD Dialog Shell */
QFrame#DialogHudFrame {
    background-color: rgba(13, 17, 23, 0.98);
    border: 1px solid rgba(0, 229, 255, 0.35);
    border-radius: 12px;
}

QFrame#DialogHeaderBar {
    background-color: rgba(22, 27, 34, 0.9);
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid rgba(48, 54, 61, 0.6);
    padding: 8px 12px;
}

QLabel#DialogTitle {
    color: #00e5ff;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

/* Form Section Labels */
QLabel.FormLabel {
    color: #8b949e;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin-top: 2px;
}

/* Form Inputs inside HUD and Dialogs */
QLineEdit, QPlainTextEdit, QTextEdit {
    background-color: rgba(22, 27, 34, 0.9);
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 6px;
    color: #f0f6fc;
    padding: 7px 10px;
    font-size: 12px;
    selection-background-color: #1f6feb;
}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border: 1px solid #00e5ff;
    background-color: rgba(16, 23, 38, 0.95);
}

QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {
    background-color: rgba(22, 27, 34, 0.4);
    color: #6e7681;
    border-color: rgba(48, 54, 61, 0.4);
}

/* QComboBox Styling */
QComboBox {
    background-color: rgba(22, 27, 34, 0.9);
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 6px;
    color: #f0f6fc;
    padding: 6px 10px;
    font-size: 12px;
    min-height: 22px;
}

QComboBox:hover {
    border-color: rgba(0, 229, 255, 0.4);
}

QComboBox:focus {
    border: 1px solid #00e5ff;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid rgba(48, 54, 61, 0.6);
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8b949e;
    margin-right: 2px;
}

QComboBox::down-arrow:hover {
    border-top-color: #00e5ff;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #f0f6fc;
    selection-background-color: #1f293d;
    selection-color: #00e5ff;
    padding: 4px;
    outline: none;
}

QPushButton.BrowseBtn {
    background-color: rgba(33, 38, 45, 0.85);
    color: #58a6ff;
    border: 1px solid rgba(56, 139, 253, 0.4);
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton.BrowseBtn:hover {
    background-color: rgba(56, 139, 253, 0.2);
    color: #00e5ff;
    border-color: #00e5ff;
}

/* Settings & Options Dialog Styles */
QFrame#SettingsSidebar {
    background-color: rgba(18, 22, 29, 0.9);
    border-right: 1px solid rgba(48, 54, 61, 0.6);
    padding: 10px 8px;
}

QPushButton.SettingsNavBtn {
    background-color: transparent;
    color: #8b949e;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 8px 12px;
    text-align: left;
    font-size: 12px;
    font-weight: 500;
}

QPushButton.SettingsNavBtn:hover {
    background-color: rgba(33, 38, 45, 0.8);
    color: #f0f6fc;
}

QPushButton.SettingsNavBtnActive {
    background-color: rgba(31, 41, 61, 0.9);
    color: #00e5ff;
    border: 1px solid rgba(0, 229, 255, 0.5);
    border-radius: 6px;
    padding: 8px 12px;
    text-align: left;
    font-size: 12px;
    font-weight: 600;
}

QLabel.SettingsSectionTitle {
    color: #00e5ff;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
    margin-bottom: 2px;
}

QFrame.SettingsCard {
    background-color: rgba(22, 27, 34, 0.7);
    border: 1px solid rgba(48, 54, 61, 0.6);
    border-radius: 8px;
    padding: 10px 14px;
}

QLabel.ShortcutKeyBadge {
    background-color: rgba(31, 41, 61, 0.9);
    color: #58a6ff;
    border: 1px solid rgba(56, 139, 253, 0.4);
    border-radius: 5px;
    padding: 2px 8px;
    font-family: 'Consolas', monospace;
    font-size: 11px;
    font-weight: bold;
}

/* Dialogs & Message Boxes Fallback */
QDialog, QMessageBox {
    background-color: #161b22;
    color: #f0f6fc;
    font-family: 'Segoe UI', 'SF Pro Display', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
    border: 1px solid #30363d;
}

QMessageBox QLabel, QDialog QLabel {
    color: #f0f6fc;
    font-size: 13px;
    background-color: transparent;
}

QMessageBox QPushButton, QDialogButtonBox QPushButton, QDialog QPushButton {
    background-color: #21262d;
    color: #f0f6fc;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 16px;
    min-width: 80px;
    font-size: 12px;
    font-weight: 600;
}

QMessageBox QPushButton:hover, QDialogButtonBox QPushButton:hover, QDialog QPushButton:hover {
    background-color: #30363d;
    color: #00e5ff;
    border-color: #00e5ff;
}

QMessageBox QPushButton:focus, QDialogButtonBox QPushButton:focus, QDialog QPushButton:focus {
    border: 1px solid #00e5ff;
    outline: none;
}
"""

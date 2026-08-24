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
    border-radius: 8px;
    padding: 5px 12px;
    font-size: 12px;
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
    border-radius: 8px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: bold;
}

/* Project Selector Button */
QPushButton.ProjectSelectBtn {
    background-color: rgba(31, 41, 61, 0.6);
    color: #58a6ff;
    border: 1px solid rgba(56, 139, 253, 0.4);
    border-radius: 7px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.ProjectSelectBtn:hover {
    background-color: rgba(56, 139, 253, 0.25);
    color: #00e5ff;
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

QLabel.BadgeDir {
    background-color: rgba(56, 139, 253, 0.2);
    color: #79c0ff;
    border: 1px solid rgba(56, 139, 253, 0.4);
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
"""

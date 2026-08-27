"""
Typography, Font Hierarchies, Badges, and Text Styles for SpectreHUD.
"""

TYPOGRAPHY_QSS = """
/* Transparent Base Container & Global Fonts */
QWidget#CentralWidget {
    background-color: transparent;
    font-family: 'Segoe UI', 'SF Pro Display', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
    color: #c9d1d9;
}

/* Card & Snippet Typography */
QLabel#SnippetTitle {
    color: #f0f6fc;
    font-size: 13px;
    font-weight: 600;
}

QLabel#SnippetCategory {
    background-color: rgba(56, 139, 253, 0.12);
    color: #79c0ff;
    border: 1px solid rgba(56, 139, 253, 0.35);
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
}

QLabel#SnippetDesc {
    color: #8b949e;
    font-size: 11px;
}

/* Variable Status Bar Labels */
QLabel.VarTagLabel {
    color: #79c0ff;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.3px;
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

/* Form Section Labels */
QLabel.FormLabel {
    color: #e6edf3;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin-top: 2px;
}

/* Settings Titles & Badges */
QLabel.SettingsSectionTitle {
    color: #00e5ff;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
    margin-bottom: 2px;
}

QLabel.ShortcutKeyBadge {
    background-color: rgba(31, 41, 61, 0.95);
    color: #58a6ff;
    border: 1px solid rgba(56, 139, 253, 0.5);
    border-radius: 5px;
    padding: 3px 10px;
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    font-weight: bold;
    min-height: 18px;
}

/* Footer & Banner Text */
QLabel#FooterText {
    color: #6e7681;
    font-size: 11px;
}

QLabel#PrivacyWarningText {
    color: #e3b341;
    font-size: 11px;
    font-weight: 500;
}

QLabel.ReportStatusLabel {
    color: #8b949e;
    font-size: 12px;
    font-weight: 500;
}
"""

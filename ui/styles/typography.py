"""
Typography, Font Hierarchies, Badges, and Text Styles for SpectreHUD.
"""

TYPOGRAPHY_QSS_TEMPLATE = """
/* Transparent Base Container & Global Fonts */
QWidget#CentralWidget {
    background-color: {BG_DARK};
    font-family: {ui_font};
    font-size: 13px;
    color: {TEXT_SECONDARY};
}

/* Native tooltips do not reliably inherit the application's text colour on
   Windows. Give every hover hint an explicit, high-contrast treatment. */
QToolTip {
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {CYBER_CYAN};
    border-radius: 4px;
    padding: 5px 8px;
    font-family: {ui_font};
    font-size: 12px;
}

/* Card & Snippet Typography */
QLabel#SnippetTitle {
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 600;
}

QLabel#SnippetCategory {
    background-color: {ACTIVE_BLUE_A12};
    color: {CYBER_BLUE_LIGHT};
    border: 1px solid {ACTIVE_BLUE_A35};
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
}

QLabel#SnippetDesc {
    color: {TEXT_MUTED};
    font-size: 11px;
}

/* Variable Status Bar Labels */
QLabel.VarTagLabel {
    color: {CYBER_BLUE_LIGHT};
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
    background-color: {WARNING_A20};
    color: {STATUS_WARNING};
    border: 1px solid {WARNING_A40};
}

QLabel.BadgeHash {
    background-color: {PURPLE_A20};
    color: {STATUS_PURPLE};
    border: 1px solid {PURPLE_A40};
}

QLabel.BadgeFlag {
    background-color: {SUCCESS_A20};
    color: {STATUS_GREEN_LIGHT};
    border: 1px solid {SUCCESS_A40};
}

QLabel.BadgeScreenshot {
    background-color: {CYAN_A20};
    color: {CYBER_CYAN};
    border: 1px solid {CYAN_A40};
}

QLabel.BadgeDir {
    background-color: {ACTIVE_BLUE_A20};
    color: {CYBER_BLUE_LIGHT};
    border: 1px solid {ACTIVE_BLUE_A40};
}

QLabel.BadgeNote {
    background-color: {MUTED_A20};
    color: {TEXT_MUTED};
    border: 1px solid {MUTED_A40};
}

/* Pentest Category Badge */
QLabel.CategoryBadge {
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: 600;
    background-color: {ACTIVE_BLUE_A12};
    color: {CYBER_BLUE};
    border: 1px solid {ACTIVE_BLUE_A30};
}

/* Loot Group Section Header */
QLabel.LootSectionHeader {
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 10px 4px 2px 4px;
    background-color: transparent;
}

/* Form Section Labels */
QLabel.FormLabel {
    color: {TEXT_FORM};
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin-top: 2px;
}

/* Settings Titles & Badges */
QLabel.SettingsSectionTitle {
    color: {CYBER_CYAN};
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
    margin-bottom: 2px;
}

QLabel.ShortcutKeyBadge {
    background-color: {NAV_A95};
    color: {CYBER_BLUE};
    border: 1px solid {ACTIVE_BLUE_A50};
    border-radius: 5px;
    padding: 3px 10px;
    font-family: {code_font};
    font-size: 11px;
    font-weight: bold;
    min-height: 18px;
}

/* Footer & Banner Text */
QLabel#FooterText {
    color: {TEXT_DIMMED};
    font-size: 11px;
}

QLabel#PrivacyWarningText {
    color: {STATUS_WARNING};
    font-size: 11px;
    font-weight: 500;
}

QLabel.ReportStatusLabel,
QLabel[class*="ReportStatusLabel"] {
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 500;
}
"""

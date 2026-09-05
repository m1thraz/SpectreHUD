"""
Card Containers, Frames, Code Blocks, and HUD Glass Styles for SpectreHUD.
"""

CARDS_QSS_TEMPLATE = """
/* Simulated glass with optional desktop bleed-through; painted by GlassPanel. */
QFrame#HudFrame {
    background-color: {HUD_BACKGROUND};
    qproperty-glassColor: {HUD_GLASS_COLOR};
    qproperty-glassIntensity: {HUD_INTENSITY};
    qproperty-bleedThrough: {BLEED_THROUGH};
    border: 1px solid {CYAN_A35};
    border-radius: 14px;
}

/* Header & Mode Switcher Bar */
QFrame#HeaderBar {
    background-color: {SURFACE_A70};
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    border-bottom: 1px solid {BORDER_A50};
    padding: 0px;
}

/* Header Navigation / Actions Divider */
QFrame.HeaderDivider,
QFrame[class~="HeaderDivider"],
QFrame[class*="HeaderDivider"] {
    background-color: {BORDER_A50};
    min-width: 1px;
    max-width: 1px;
    width: 1px;
    margin: 4px 4px;
    border: none;
}

/* Filter Chips / Pills Bar Frame */
QFrame#FilterPillsFrame {
    background-color: transparent;
    padding: 2px 10px 6px 10px;
    border-bottom: 1px solid {BORDER_A40};
}

/* Compact Variable Status Bar Frame */
QFrame#CompactVarBar {
    background-color: {PANEL_A80};
    border-bottom: 1px solid {BORDER_A40};
    padding: 5px 12px;
}

/* Snippet & Loot Cards */
QFrame#SnippetCard {
    background-color: {SURFACE_A85};
    border: 1px solid {BORDER_A70};
    border-radius: 8px;
    padding: 2px;
}

QFrame#SnippetCard:hover {
    border: 1px solid {CYAN_A50};
    background-color: {CARD_HOVER_A90};
}

/* Kanban columns reuse LootCards while retaining clear phase boundaries. */
QFrame[class="LootBoardColumn"] {
    background-color: {DARK_A72};
    border: 1px solid {BORDER_A80};
    border-radius: 8px;
}

QFrame[class="LootBoardColumn"][dragActive="true"] {
    background-color: {CARD_HOVER_A90};
    border: 2px solid {CYBER_CYAN};
}

QLabel[class="LootBoardColumnTitle"] {
    color: {CYBER_CYAN};
    font-size: 11px;
    font-weight: 700;
    padding: 2px;
}

QScrollArea#LootColumnScrollArea {
    background: transparent;
    border: none;
}

QScrollArea#LootColumnScrollArea QScrollBar:vertical,
QScrollArea#LootColumnScrollArea QScrollBar:horizontal {
    background: transparent;
    width: 0px;
    height: 0px;
}

/* Command Code Display Box */
QLabel#CommandLabel {
    background-color: {CODE_A95};
    border: 1px solid {BORDER_A80};
    border-radius: 6px;
    color: {STATUS_SUCCESS};
    font-family: {code_font};
    font-size: 12px;
    padding: 8px 12px;
    selection-background-color: {CODE_SELECTION};
}

QPlainTextEdit#CommandBox {
    background-color: {CODE_A90};
    border: 1px solid {CONTROL_A80};
    border-radius: 6px;
    color: {STATUS_SUCCESS};
    font-family: {code_font};
    font-size: 12px;
    padding: 6px 8px;
    selection-background-color: {CODE_SELECTION};
}

/* Inline Command Tweaker Container */
QFrame#TweakContainer {
    background-color: {DARK_A95};
    border: 1px solid {BLUE_A35};
    border-radius: 6px;
    margin-top: 4px;
    padding: 4px 6px;
}

QLineEdit.TweakLineEdit {
    background-color: {CODE_A95};
    color: {STATUS_SUCCESS};
    border: 1px solid {BORDER_A80};
    border-radius: 5px;
    font-family: {code_font};
    font-size: 12px;
    padding: 4px 8px;
}

QLineEdit.TweakLineEdit:focus {
    border: 1px solid {CYBER_CYAN};
    background-color: {CODE_A98};
}

/* Privacy Warning Banner */
QFrame#PrivacyWarningBanner {
    background-color: {WARNING_A12};
    border: 1px solid {WARNING_A35};
    border-radius: 6px;
    padding: 6px 10px;
    margin: 4px 0px;
}

/* Minimal HUD Footer Frame */
QFrame#HudFooter {
    background-color: {PANEL_A70};
    border-top: 1px solid {BORDER_A40};
    border-bottom-left-radius: 14px;
    border-bottom-right-radius: 14px;
    padding: 5px 14px;
}

/* Settings Card */
QFrame.SettingsCard {
    background-color: {SURFACE_A85};
    border: 1px solid {BORDER_A60};
    border-radius: 8px;
    padding: 12px 14px;
}
"""

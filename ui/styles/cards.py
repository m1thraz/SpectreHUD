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

/* Compact Variable Status Bar Frame — transparent so GlassPanel shines through seamlessly */
QFrame#CompactVarBar {
    background-color: transparent;
    border-bottom: 1px solid {BORDER_A40};
    padding: 5px 12px;
}

QFrame#CompactVarBar[collapsed="true"] {
    border: none;
    padding: 0px;
}

QWidget#ReportFormatToolbar[collapsed="true"] {
    background-color: transparent;
    border: none;
    padding: 0px;
}

/* Snippet & Loot Cards */
QFrame#SnippetCard {
    background-color: {SURFACE_A85};
    border: 1px solid {BORDER_A70};
    border-radius: 10px;
    padding: 4px;
}

QFrame#SnippetCard:hover {
    border: 1px solid {CYAN_A50};
    background-color: {CARD_HOVER_A90};
}

/* Kanban columns reuse LootCards while retaining clear phase boundaries. */
QFrame#lootCard[boardCard="true"] {
    background-color: {LOOT_CARD_SURFACE};
    border: 1px solid {LOOT_CARD_BORDER};
    border-radius: 10px;
}

QFrame#QuickNoteStreamCard {
    background: transparent;
    border: none;
}

QFrame#QuickNoteStreamCard[overdue="true"] {
    border-left: 2px solid {WARNING_A40};
}

QLabel#QuickNoteText {
    color: {TEXT_PRIMARY};
    background: transparent;
    border: none;
    font-size: 13px;
    padding: 4px;
}

QLabel#QuickNoteText[resolved="true"] {
    color: {TEXT_MUTED};
}

QLabel#QuickNoteMeta {
    color: {TEXT_MUTED};
    background: transparent;
    border: none;
    font-size: 10px;
}

QFrame#QuickNoteFocusReview {
    background-color: {BG_SURFACE};
    border: 1px solid {CYAN_A50};
    border-radius: 10px;
}

QLabel#QuickNoteReviewText {
    color: {TEXT_PRIMARY};
    background: transparent;
    border: none;
    font-size: 16px;
    padding: 12px;
}

QLabel.QuickNoteReviewProgress,
QLabel[class="QuickNoteReviewProgress"] {
    color: {CYBER_CYAN};
    font-size: 11px;
    font-weight: 600;
}

QFrame#QuickNoteReviewSummary {
    background-color: transparent;
    border: 1px solid {BORDER_A40};
    border-radius: 6px;
}

QLabel#QuickNoteReviewSummaryText {
    color: {TEXT_MUTED};
    background: transparent;
    border: none;
    font-size: 11px;
}

QFrame#lootCard[boardCard="true"]:hover {
    background-color: {LOOT_CARD_SURFACE};
    border: 1px solid {CYBER_CYAN};
}

QWidget#LootCardsContainer {
    background: transparent;
}

QFrame[class="LootBoardColumn"] {
    background-color: {LOOT_COLUMN_SURFACE};
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

QLabel[class="LootBoardColumnIndicator"], QLabel#LootBoardColumnIndicator {
    background-color: {DARK_A72};
    color: {CYBER_BLUE_LIGHT};
    border: 1px solid {ACTIVE_BLUE_A40};
    border-radius: 11px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}

QScrollArea[class="LootBoard"],
QScrollArea[class="LootBoard"] > QWidget > QWidget {
    background-color: {LOOT_COLUMN_SURFACE};
    border: none;
}

QWidget#LootCardActionBar {
    background: transparent;
}

QScrollArea#LootColumnScrollArea {
    background: transparent;
    border: none;
}

QScrollArea#LootColumnScrollArea QScrollBar:horizontal {
    background: transparent;
    width: 0px;
    height: 0px;
}

QScrollArea#LootColumnScrollArea QScrollBar:vertical {
    background: transparent;
    width: 4px;
    margin: 0px;
}

QScrollArea#LootColumnScrollArea QScrollBar::handle:vertical {
    background: {BORDER_A80};
    border-radius: 2px;
    min-height: 20px;
}

QScrollArea#LootColumnScrollArea QScrollBar::handle:vertical:hover {
    background: {CYBER_CYAN};
}

QScrollArea#LootColumnScrollArea QScrollBar::add-line:vertical,
QScrollArea#LootColumnScrollArea QScrollBar::sub-line:vertical,
QScrollArea#LootColumnScrollArea QScrollBar::add-page:vertical,
QScrollArea#LootColumnScrollArea QScrollBar::sub-page:vertical {
    background: transparent;
    width: 0px;
    height: 0px;
}

/* Command Code Display Box */
QLabel#CommandLabel, QTextEdit#CommandLabel {
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

"""
Card Containers, Frames, Code Blocks, and HUD Glass Styles for SpectreHUD.
"""

CARDS_QSS = """
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

/* Filter Chips / Pills Bar Frame */
QFrame#FilterPillsFrame {
    background-color: transparent;
    padding: 2px 10px 6px 10px;
    border-bottom: 1px solid rgba(48, 54, 61, 0.4);
}

/* Compact Variable Status Bar Frame */
QFrame#CompactVarBar {
    background-color: rgba(17, 22, 29, 0.8);
    border-bottom: 1px solid rgba(48, 54, 61, 0.4);
    padding: 5px 12px;
}

/* Snippet & Loot Cards */
QFrame#SnippetCard {
    background-color: rgba(22, 27, 34, 0.85);
    border: 1px solid rgba(48, 54, 61, 0.7);
    border-radius: 8px;
    padding: 2px;
}

QFrame#SnippetCard:hover {
    border: 1px solid rgba(0, 229, 255, 0.5);
    background-color: rgba(26, 33, 44, 0.9);
}

/* Kanban columns reuse LootCards while retaining clear phase boundaries. */
QFrame[class="LootBoardColumn"] {
    background-color: rgba(13, 17, 23, 0.72);
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 8px;
}

QLabel[class="LootBoardColumnTitle"] {
    color: #00e5ff;
    font-size: 11px;
    font-weight: 700;
    padding: 2px;
}

/* Command Code Display Box */
QLabel#CommandLabel {
    background-color: rgba(9, 13, 18, 0.95);
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 6px;
    color: #39d353;
    font-family: {code_font};
    font-size: 12px;
    padding: 8px 12px;
    selection-background-color: #1f3d29;
}

QPlainTextEdit#CommandBox {
    background-color: rgba(9, 13, 18, 0.9);
    border: 1px solid rgba(33, 38, 45, 0.8);
    border-radius: 6px;
    color: #39d353;
    font-family: {code_font};
    font-size: 12px;
    padding: 6px 8px;
    selection-background-color: #1f3d29;
}

/* Inline Command Tweaker Container */
QFrame#TweakContainer {
    background-color: rgba(13, 17, 23, 0.95);
    border: 1px solid rgba(88, 166, 255, 0.35);
    border-radius: 6px;
    margin-top: 4px;
    padding: 4px 6px;
}

QLineEdit.TweakLineEdit {
    background-color: rgba(9, 13, 18, 0.95);
    color: #39d353;
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 5px;
    font-family: {code_font};
    font-size: 12px;
    padding: 4px 8px;
}

QLineEdit.TweakLineEdit:focus {
    border: 1px solid #00e5ff;
    background-color: rgba(9, 13, 18, 0.98);
}

/* Privacy Warning Banner */
QFrame#PrivacyWarningBanner {
    background-color: rgba(210, 153, 34, 0.12);
    border: 1px solid rgba(210, 153, 34, 0.35);
    border-radius: 6px;
    padding: 6px 10px;
    margin: 4px 0px;
}

/* Minimal HUD Footer Frame */
QFrame#HudFooter {
    background-color: rgba(17, 22, 29, 0.7);
    border-top: 1px solid rgba(48, 54, 61, 0.4);
    border-bottom-left-radius: 14px;
    border-bottom-right-radius: 14px;
    padding: 5px 14px;
}

/* Settings Card */
QFrame.SettingsCard {
    background-color: rgba(22, 27, 34, 0.85);
    border: 1px solid rgba(48, 54, 61, 0.6);
    border-radius: 8px;
    padding: 12px 14px;
}
"""


def get_cards_qss(code_font: str) -> str:
    return CARDS_QSS.replace("{code_font}", code_font)

"""
Dialogs, Form Inputs, Dropdowns, Checkboxes, and Popups for SpectreHUD.
"""

DIALOGS_QSS = """
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

/* Compact Variable Input */
QLineEdit.CompactVarInput {
    background-color: rgba(13, 17, 23, 0.8);
    border: 1px solid rgba(48, 54, 61, 0.6);
    border-radius: 5px;
    color: #58a6ff;
    padding: 3px 8px;
    font-family: {code_font};
    font-size: 12px;
    font-weight: 600;
}

QLineEdit.CompactVarInput:focus {
    border: 1px solid #58a6ff;
    background-color: rgba(16, 23, 38, 0.9);
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

/* Settings Sidebar */
QFrame#SettingsSidebar {
    background-color: rgba(18, 22, 29, 0.9);
    border-right: 1px solid rgba(48, 54, 61, 0.6);
    padding: 10px 8px;
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

/* General Checkboxes */
QCheckBox {
    color: #f0f6fc;
    font-size: 12px;
    font-weight: 500;
    spacing: 8px;
}

QCheckBox:hover {
    color: #00e5ff;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid rgba(88, 166, 255, 0.5);
    background-color: rgba(13, 17, 23, 0.85);
}

QCheckBox::indicator:hover {
    border-color: #00e5ff;
    background-color: rgba(31, 41, 61, 0.85);
}

QCheckBox::indicator:checked {
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
    font-family: {code_font};
    font-size: 12px;
}

QPlainTextEdit.ReportSourceEditor:focus {
    border: 1px solid #58a6ff;
}

QTextEdit.ReportPreview {
    background-color: rgba(13, 17, 23, 0.98);
    color: #f0f6fc;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 14px;
    font-family: {ui_font};
    font-size: 13px;
    line-height: 1.6;
}

/* Dialogs & Message Boxes Fallback */
QDialog, QMessageBox {
    background-color: #161b22;
    color: #f0f6fc;
    font-family: {ui_font};
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


def get_dialogs_qss(ui_font: str, code_font: str) -> str:
    return DIALOGS_QSS.replace("{ui_font}", ui_font).replace("{code_font}", code_font)

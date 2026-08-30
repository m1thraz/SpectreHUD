"""
Dialogs, Form Inputs, Dropdowns, Checkboxes, and Popups for SpectreHUD.
"""

DIALOGS_QSS_TEMPLATE = """
/* Spotlight Search Section */
QFrame#SearchSection {
    background-color: transparent;
    padding: 6px 12px;
}

QLineEdit#SpotlightSearch {
    background-color: {DARK_A85};
    border: 1px solid {BLUE_A25};
    border-radius: 10px;
    color: {TEXT_WHITE};
    padding: 8px 14px;
    font-size: 14px;
    font-weight: 500;
}

QLineEdit#SpotlightSearch:focus {
    border: 1px solid {CYBER_CYAN};
    background-color: {SEARCH_FOCUS_A95};
}

/* Compact Variable Input */
QLineEdit.CompactVarInput {
    background-color: {DARK_A80};
    border: 1px solid {BORDER_A60};
    border-radius: 5px;
    color: {CYBER_BLUE};
    padding: 3px 8px;
    font-family: {code_font};
    font-size: 12px;
    font-weight: 600;
}

QLineEdit.CompactVarInput:focus {
    border: 1px solid {CYBER_BLUE};
    background-color: {INPUT_FOCUS_A90};
}

/* Frameless HUD Dialog Shell */
QFrame#DialogHudFrame {
    background-color: {DARK_A98};
    border: 1px solid {CYAN_A35};
    border-radius: 12px;
}

QFrame#DialogHeaderBar {
    background-color: {SURFACE_A90};
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid {BORDER_A60};
    padding: 8px 12px;
}

QLabel#DialogTitle {
    color: {CYBER_CYAN};
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

/* Form Inputs inside HUD and Dialogs */
QLineEdit, QPlainTextEdit, QTextEdit {
    background-color: {SURFACE_A90};
    border: 1px solid {BORDER_A80};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    padding: 7px 10px;
    font-size: 12px;
    selection-background-color: {SELECTION_BLUE};
}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border: 1px solid {CYBER_CYAN};
    background-color: {INPUT_FOCUS_A95};
}

QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {
    background-color: {SURFACE_A40};
    color: {TEXT_DIMMED};
    border-color: {BORDER_A40};
}

/* Dark QMenu for Dropdowns */
QMenu {
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    padding: 6px;
    color: {TEXT_SECONDARY};
    font-size: 12px;
}

QMenu::item {
    background-color: transparent;
    padding: 6px 16px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: {ACCENT_NAV_ACTIVE};
    color: {CYBER_CYAN};
}

QMenu::separator {
    height: 1px;
    background-color: {BORDER_DEFAULT};
    margin: 4px 8px;
}

/* QComboBox Styling */
QComboBox {
    background-color: {SURFACE_A90};
    border: 1px solid {BORDER_A80};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    padding: 6px 10px;
    font-size: 12px;
    min-height: 22px;
}

QComboBox:hover {
    border-color: {CYAN_A40};
}

QComboBox:focus {
    border: 1px solid {CYBER_CYAN};
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid {BORDER_A60};
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_MUTED};
    margin-right: 2px;
}

QComboBox::down-arrow:hover {
    border-top-color: {CYBER_CYAN};
}

QComboBox QAbstractItemView {
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_NAV_ACTIVE};
    selection-color: {CYBER_CYAN};
    padding: 4px;
    outline: none;
}

/* Settings Sidebar */
QFrame#SettingsSidebar {
    background-color: {SIDEBAR_A90};
    border-right: 1px solid {BORDER_A60};
    padding: 10px 8px;
}

/* Always on Top Checkbox in Footer */
QCheckBox#AlwaysOnTopCheck {
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 500;
    spacing: 5px;
    margin-right: 4px;
}

QCheckBox#AlwaysOnTopCheck:hover {
    color: {CYBER_BLUE};
}

QCheckBox#AlwaysOnTopCheck:checked {
    color: {CYBER_CYAN};
    font-weight: 600;
}

QCheckBox#AlwaysOnTopCheck::indicator {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    border: 1px solid {BLUE_A40};
    background-color: {DARK_A80};
}

QCheckBox#AlwaysOnTopCheck::indicator:hover {
    border-color: {CYBER_CYAN};
    background-color: {NAV_A80};
}

QCheckBox#AlwaysOnTopCheck::indicator:checked {
    background-color: {CYBER_CYAN};
    border-color: {CYBER_CYAN};
}

/* General Checkboxes */
QCheckBox {
    color: {TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 500;
    spacing: 8px;
}

QCheckBox:hover {
    color: {CYBER_CYAN};
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid {BLUE_A50};
    background-color: {DARK_A85};
}

QCheckBox::indicator:hover {
    border-color: {CYBER_CYAN};
    background-color: {NAV_A85};
}

QCheckBox::indicator:checked {
    background-color: {CYBER_CYAN};
    border-color: {CYBER_CYAN};
}

/* Report Editor & Preview */
QPlainTextEdit.ReportSourceEditor {
    background-color: {DARK_A95};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    padding: 10px;
    font-family: {code_font};
    font-size: 12px;
}

QPlainTextEdit.ReportSourceEditor:focus {
    border: 1px solid {CYBER_BLUE};
}

QTextEdit.ReportPreview {
    background-color: {DARK_A98};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    padding: 14px;
    font-family: {ui_font};
    font-size: 13px;
    line-height: 1.6;
}

/* Dialogs & Message Boxes Fallback */
QDialog, QMessageBox {
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    font-family: {ui_font};
    font-size: 13px;
    border: 1px solid {BORDER_DEFAULT};
}

QMessageBox QLabel, QDialog QLabel {
    color: {TEXT_PRIMARY};
    font-size: 13px;
    background-color: transparent;
}

QMessageBox QPushButton, QDialogButtonBox QPushButton, QDialog QPushButton {
    background-color: {BG_CONTROL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 6px;
    padding: 6px 16px;
    min-width: 80px;
    font-size: 12px;
    font-weight: 600;
}

QMessageBox QPushButton:hover, QDialogButtonBox QPushButton:hover, QDialog QPushButton:hover {
    background-color: {BORDER_DEFAULT};
    color: {CYBER_CYAN};
    border-color: {CYBER_CYAN};
}

QMessageBox QPushButton:focus, QDialogButtonBox QPushButton:focus, QDialog QPushButton:focus {
    border: 1px solid {CYBER_CYAN};
    outline: none;
}
"""

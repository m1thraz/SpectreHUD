"""
Table Views, Scroll Areas, Splitters, and Scrollbars for SpectreHUD.
"""

TABLES_QSS_TEMPLATE = """
/* Modern Ultra-Slim Scrollbars */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 2px 0px 2px 0px;
}

QScrollBar::handle:vertical {
    background: {BORDER_A60};
    min-height: 20px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: {CYBER_CYAN};
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    margin: 0px 2px 0px 2px;
}

QScrollBar::handle:horizontal {
    background: {BORDER_A60};
    min-width: 20px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal:hover {
    background: {CYBER_CYAN};
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Custom Size Grip in Footer */
QSizeGrip {
    background-color: transparent;
    width: 14px;
    height: 14px;
    margin-right: -4px;
    margin-bottom: -2px;
}

/* QSplitter */
QSplitter::handle {
    background-color: {BORDER_DEFAULT};
    width: 4px;
    height: 4px;
}

QSplitter::handle:hover {
    background-color: {CYBER_CYAN};
}

/* Scroll Area Styles */
QScrollArea#MainScrollArea {
    background: transparent;
    border: none;
}

/* Template management views */
QTableWidget#TemplateTable, QListWidget#TemplateSectionList {
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 6px;
    selection-background-color: {SELECTION_BLUE};
    selection-color: {TEXT_WHITE};
    outline: none;
}

QTableWidget#TemplateTable {
    gridline-color: {BORDER_DEFAULT};
    alternate-background-color: {BG_SURFACE};
}

QTableWidget#TemplateTable::item {
    padding: 5px;
}

QTableWidget#TemplateTable::item:hover,
QListWidget#TemplateSectionList::item:hover {
    background-color: {BG_CONTROL};
}

QListWidget#TemplateSectionList {
    padding: 4px;
}

QListWidget#TemplateSectionList::item {
    background-color: transparent;
    border-radius: 4px;
    padding: 6px 8px;
}

QListWidget#TemplateSectionList::item:selected {
    background-color: {SELECTION_BLUE};
    color: {TEXT_WHITE};
}

QHeaderView::section {
    background-color: {BG_CONTROL};
    color: {TEXT_PRIMARY};
    border: none;
    border-bottom: 1px solid {BORDER_DEFAULT};
    padding: 6px;
    font-weight: bold;
}
"""

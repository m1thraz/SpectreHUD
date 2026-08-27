"""
Table Views, Scroll Areas, Splitters, and Scrollbars for SpectreHUD.
"""

TABLES_QSS = """
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

QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    margin: 0px 2px 0px 2px;
}

QScrollBar::handle:horizontal {
    background: rgba(48, 54, 61, 0.6);
    min-width: 20px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal:hover {
    background: #00e5ff;
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
    background-color: #30363d;
    width: 4px;
    height: 4px;
}

QSplitter::handle:hover {
    background-color: #00e5ff;
}

/* Scroll Area Styles */
QScrollArea#MainScrollArea {
    background: transparent;
    border: none;
}
"""

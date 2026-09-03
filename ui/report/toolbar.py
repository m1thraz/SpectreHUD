"""Formatting-toolbar construction for the report editor."""

from collections.abc import Callable

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QMenu, QPushButton, QWidget

from core.i18n import t


def create_toolbar_divider(parent: QWidget | None = None) -> QFrame:
    """Creates a subtle vertical separator line for grouping toolbar buttons."""
    divider = QFrame(parent)
    divider.setFrameShape(QFrame.Shape.VLine)
    divider.setFrameShadow(QFrame.Shadow.Plain)
    divider.setProperty("class", "ToolbarDivider")
    divider.setFixedWidth(1)
    divider.setStyleSheet(
        "background-color: rgba(48, 54, 61, 0.7); max-height: 18px; margin: 4px 6px;"
    )
    return divider


def build_format_toolbar(parent: QWidget, callbacks: dict[str, Callable[[], None]]) -> QWidget:
    """
    Build the formatting toolbar split into 3 clear functional zones:
    1. Struktur (Headings dropdown H1-H6, Quote, Lists, Horizontal Rule)
    2. Inline-Stil (Bold, Italic, Strikethrough, Inline Code, Code Block)
    3. Einfügen (Image / Loot Screenshot, Link, Table)
    """
    toolbar_widget = QWidget(parent)
    layout = QHBoxLayout(toolbar_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)

    # -------------------------------------------------------------
    # Zone 1: Struktur (Headings Dropdown, Quote, Lists, HR)
    # -------------------------------------------------------------
    btn_heading = QPushButton("H ▾", toolbar_widget)
    btn_heading.setProperty("class", "SecondaryBtn FormatToolBtn HeadingDropdownBtn")
    btn_heading.setToolTip(t("report.format_headings", "Headings (H1–H6)"))

    heading_menu = QMenu(btn_heading)
    heading_menu.setProperty("class", "SecondaryMenu")
    for lvl in range(1, 7):
        act = heading_menu.addAction(f"H{lvl} — " + t(f"report.format_h{lvl}", f"Heading {lvl}"))
        act.triggered.connect(lambda _=False, level=lvl: callbacks[f"heading_{level}"]())
    btn_heading.setMenu(heading_menu)
    layout.addWidget(btn_heading)

    structure_buttons = (
        ("❝", "report.format_quote", "Blockquote", "quote"),
        ("•", "report.format_list", "Bullet List", "list"),
        ("1.", "report.format_numbered_list", "Numbered List", "numbered_list"),
        ("―", "report.format_horizontal_rule", "Horizontal Rule", "horizontal_rule"),
    )
    for label, key, fallback, callback_key in structure_buttons:
        btn = QPushButton(label, toolbar_widget)
        btn.setProperty("class", "SecondaryBtn FormatToolBtn")
        btn.setToolTip(t(key, fallback))
        btn.clicked.connect(callbacks[callback_key])
        layout.addWidget(btn)

    # Visual Divider between Struktur and Inline-Stil
    layout.addWidget(create_toolbar_divider(toolbar_widget))

    # -------------------------------------------------------------
    # Zone 2: Inline-Stil (Bold, Italic, Strikethrough, Code, Code Block)
    # -------------------------------------------------------------
    inline_buttons = (
        ("B", "report.format_bold", "Bold", "bold"),
        ("I", "report.format_italic", "Italic", "italic"),
        ("S̶", "report.format_strikethrough", "Strikethrough", "strikethrough"),
        ("</>", "report.format_code", "Inline Code", "code"),
        (">_", "report.format_code_block", "Code Block", "code_block"),
    )
    for label, key, fallback, callback_key in inline_buttons:
        btn = QPushButton(label, toolbar_widget)
        btn.setProperty("class", "SecondaryBtn FormatToolBtn")
        btn.setToolTip(t(key, fallback))
        btn.clicked.connect(callbacks[callback_key])
        layout.addWidget(btn)

    # Visual Divider between Inline-Stil and Einfügen
    layout.addWidget(create_toolbar_divider(toolbar_widget))

    # -------------------------------------------------------------
    # Zone 3: Einfügen (Image, Link, Table)
    # -------------------------------------------------------------
    insert_buttons = (
        ("🖼️", "report.format_image", "Insert Image", "image"),
        ("🔗", "report.format_link", "Link", "link"),
        ("▦", "report.format_table", "Table", "table"),
    )
    for label, key, fallback, callback_key in insert_buttons:
        btn = QPushButton(label, toolbar_widget)
        btn.setProperty("class", "SecondaryBtn FormatToolBtn")
        btn.setToolTip(t(key, fallback))
        btn.clicked.connect(callbacks[callback_key])
        layout.addWidget(btn)

    return toolbar_widget

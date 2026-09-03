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
        "background-color: rgba(139, 148, 158, 0.5); max-height: 20px; min-width: 1px; max-width: 1px; margin: 3px 6px;"
    )
    return divider


def build_format_toolbar(parent: QWidget, callbacks: dict[str, Callable[[], None]]) -> QWidget:
    """
    Build the formatting toolbar split into 3 clear functional zones on the left,
    plus a collapse/minimize toggle button on the far right (under the status label):
    1. Struktur (Headings dropdown H1-H6, Quote, Lists, Horizontal Rule)
    2. Inline-Stil (Bold, Italic, Strikethrough, Inline Code, Code Block)
    3. Einfügen (Image / Loot Screenshot, Link, Table)
    4. Minimize/Expand Toggle Button (far right)
    """
    toolbar_widget = QWidget(parent)
    main_layout = QHBoxLayout(toolbar_widget)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(3)

    # -------------------------------------------------------------
    # Tools Container: Holds all formatting buttons and dividers
    # -------------------------------------------------------------
    tools_container = QWidget(toolbar_widget)
    tools_layout = QHBoxLayout(tools_container)
    tools_layout.setContentsMargins(0, 0, 0, 0)
    tools_layout.setSpacing(3)

    # Zone 1: Struktur (Headings Dropdown, Quote, Lists, HR)
    btn_heading = QPushButton("H ▾", tools_container)
    btn_heading.setProperty("class", "SecondaryBtn FormatToolBtn HeadingDropdownBtn")
    btn_heading.setToolTip(t("report.format_headings", "Headings (H1–H6)"))

    heading_menu = QMenu(btn_heading)
    heading_menu.setProperty("class", "SecondaryMenu")
    for lvl in range(1, 7):
        act = heading_menu.addAction(f"H{lvl} — " + t(f"report.format_h{lvl}", f"Heading {lvl}"))
        act.triggered.connect(lambda _=False, level=lvl: callbacks[f"heading_{level}"]())
    btn_heading.setMenu(heading_menu)
    tools_layout.addWidget(btn_heading)

    structure_buttons = (
        ("❝", "report.format_quote", "Blockquote", "quote"),
        ("•", "report.format_list", "Bullet List", "list"),
        ("1.", "report.format_numbered_list", "Numbered List", "numbered_list"),
        ("―", "report.format_horizontal_rule", "Horizontal Rule", "horizontal_rule"),
    )
    for label, key, fallback, callback_key in structure_buttons:
        btn = QPushButton(label, tools_container)
        btn.setProperty("class", "SecondaryBtn FormatToolBtn")
        btn.setToolTip(t(key, fallback))
        btn.clicked.connect(callbacks[callback_key])
        tools_layout.addWidget(btn)

    # Visual Divider between Struktur and Inline-Stil
    tools_layout.addWidget(create_toolbar_divider(tools_container))

    # Zone 2: Inline-Stil (Bold, Italic, Strikethrough, Code, Code Block)
    inline_buttons = (
        ("B", "report.format_bold", "Bold", "bold"),
        ("I", "report.format_italic", "Italic", "italic"),
        ("S̶", "report.format_strikethrough", "Strikethrough", "strikethrough"),
        ("</>", "report.format_code", "Inline Code", "code"),
        (">_", "report.format_code_block", "Code Block", "code_block"),
    )
    for label, key, fallback, callback_key in inline_buttons:
        btn = QPushButton(label, tools_container)
        btn.setProperty("class", "SecondaryBtn FormatToolBtn")
        btn.setToolTip(t(key, fallback))
        btn.clicked.connect(callbacks[callback_key])
        tools_layout.addWidget(btn)

    # Visual Divider between Inline-Stil and Einfügen
    tools_layout.addWidget(create_toolbar_divider(tools_container))

    # Zone 3: Einfügen (Image, Link, Table)
    insert_buttons = (
        ("🖼️", "report.format_image", "Insert Image", "image"),
        ("🔗", "report.format_link", "Link", "link"),
        ("▦", "report.format_table", "Table", "table"),
    )
    for label, key, fallback, callback_key in insert_buttons:
        btn = QPushButton(label, tools_container)
        btn.setProperty("class", "SecondaryBtn FormatToolBtn")
        btn.setToolTip(t(key, fallback))
        btn.clicked.connect(callbacks[callback_key])
        tools_layout.addWidget(btn)

    main_layout.addWidget(tools_container)
    main_layout.addStretch()

    # -------------------------------------------------------------
    # Minimize / Expand Toggle Button (far right, under status label)
    # -------------------------------------------------------------
    btn_toggle = QPushButton("▲", toolbar_widget)
    btn_toggle.setProperty("class", "SecondaryBtn FormatToolBtn ToolbarToggleBtn")
    btn_toggle.setToolTip(t("report.toggle_toolbar_collapse", "Collapse formatting toolbar"))

    _collapsed = False

    def _on_toggle_clicked() -> None:
        nonlocal _collapsed
        _collapsed = not _collapsed
        tools_container.setVisible(not _collapsed)
        btn_toggle.setText("▼" if _collapsed else "▲")
        btn_toggle.setToolTip(
            t("report.toggle_toolbar_expand", "Expand formatting toolbar")
            if _collapsed
            else t("report.toggle_toolbar_collapse", "Collapse formatting toolbar")
        )

    btn_toggle.clicked.connect(_on_toggle_clicked)
    main_layout.addWidget(btn_toggle)

    # Expose elements for programmatic access / testing
    toolbar_widget.tools_container = tools_container
    toolbar_widget.btn_toggle = btn_toggle

    return toolbar_widget

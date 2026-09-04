"""Formatting-toolbar construction for the report editor."""

from collections.abc import Callable

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QMenu, QPushButton, QWidget

from core.i18n import t
from ui.styles.icons import icon
from ui.styles.palette import CYBER_CYAN, TEXT_PRIMARY


REPORT_TOOLBAR_ICON_SIZE = QSize(13, 13)


def _apply_icon_button(
    button: QPushButton,
    icon_name: str,
    accessible_name: str,
    color: str,
    active_color: str,
) -> None:
    """Apply the shared report-toolbar icon treatment to an icon-only button."""
    button.setIcon(icon(icon_name, color=color, color_active=active_color))
    button.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
    button.setAccessibleName(accessible_name)


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


def build_format_toolbar(
    parent: QWidget,
    callbacks: dict[str, Callable[[], None]],
    on_toggle_collapse: Callable[[bool], None] | None = None,
    icon_color: str = CYBER_CYAN,
    icon_active_color: str = TEXT_PRIMARY,
) -> QWidget:
    """
    Build the formatting toolbar split into clear functional zones on the left,
    plus a collapse/minimize toggle button on the far right (under the status label):
    1. Struktur (Headings dropdown H1-H6, Quote, Lists, Horizontal Rule)
    2. Text-Stil (Bold, Italic, Strikethrough)
    3. Code (Inline Code, Code Block)
    4. Ausrichtung (Align Left, Align Center, Align Right)
    5. Einfügen (Image / Loot Screenshot, Link, Table, Report Icon)
    6. Minimize/Expand Toggle Button (far right)
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
        ("", "fa5s.quote-right", "report.format_quote", "Blockquote", "quote"),
        ("", "fa5s.list-ul", "report.format_list", "Bullet List", "list"),
        ("", "fa5s.list-ol", "report.format_numbered_list", "Numbered List", "numbered_list"),
        ("―", None, "report.format_horizontal_rule", "Horizontal Rule", "horizontal_rule"),
    )
    for label, icon_name, key, fallback, callback_key in structure_buttons:
        btn = QPushButton(label, tools_container)
        btn.setObjectName(f"btn_{callback_key}")
        tooltip = t(key, fallback)
        btn.setToolTip(tooltip)
        if icon_name:
            btn.setProperty("class", "SecondaryBtn FormatToolBtn ReportIconBtn")
            _apply_icon_button(btn, icon_name, tooltip, icon_color, icon_active_color)
        else:
            btn.setProperty("class", "SecondaryBtn FormatToolBtn")
        btn.clicked.connect(callbacks[callback_key])
        tools_layout.addWidget(btn)

    # Visual Divider between Struktur and Inline-Stil
    tools_layout.addWidget(create_toolbar_divider(tools_container))

    # Zone 2: Typographic text formatting remains immediately recognizable.
    inline_buttons = (
        ("B", "report.format_bold", "Bold", "bold"),
        ("I", "report.format_italic", "Italic", "italic"),
        ("S̶", "report.format_strikethrough", "Strikethrough", "strikethrough"),
    )
    for label, key, fallback, callback_key in inline_buttons:
        btn = QPushButton(label, tools_container)
        btn.setProperty("class", "SecondaryBtn FormatToolBtn")
        btn.setToolTip(t(key, fallback))
        btn.clicked.connect(callbacks[callback_key])
        tools_layout.addWidget(btn)

    # Visual Divider between text formatting and code actions.
    tools_layout.addWidget(create_toolbar_divider(tools_container))

    # Zone 3: Inline Code stays typographic; Code Block is a structural icon action.
    btn_inline_code = QPushButton("</>", tools_container)
    btn_inline_code.setObjectName("btn_code")
    btn_inline_code.setProperty("class", "SecondaryBtn FormatToolBtn")
    btn_inline_code.setToolTip(t("report.format_code", "Inline Code"))
    btn_inline_code.clicked.connect(callbacks["code"])
    tools_layout.addWidget(btn_inline_code)

    btn_code_block = QPushButton(tools_container)
    btn_code_block.setObjectName("btn_code_block")
    btn_code_block.setProperty("class", "SecondaryBtn FormatToolBtn ReportIconBtn")
    code_block_tooltip = t("report.format_code_block", "Code Block")
    btn_code_block.setToolTip(code_block_tooltip)
    _apply_icon_button(
        btn_code_block, "fa5s.code", code_block_tooltip, icon_color, icon_active_color
    )
    btn_code_block.clicked.connect(callbacks["code_block"])
    tools_layout.addWidget(btn_code_block)

    # Visual Divider between Code and Ausrichtung
    tools_layout.addWidget(create_toolbar_divider(tools_container))

    # Zone 4: Ausrichtung (Align Left, Align Center, Align Right)
    align_buttons = (
        ("fa5s.align-left", "report.format_align_left", "Align Left (Ctrl+Shift+L)", "align_left"),
        ("fa5s.align-center", "report.format_align_center", "Align Center (Ctrl+Shift+E)", "align_center"),
        ("fa5s.align-right", "report.format_align_right", "Align Right (Ctrl+Shift+R)", "align_right"),
    )
    for icon_name, key, fallback, callback_key in align_buttons:
        btn = QPushButton(tools_container)
        btn.setObjectName(f"btn_{callback_key}")
        btn.setProperty("class", "SecondaryBtn FormatToolBtn ReportIconBtn")
        tooltip = t(key, fallback)
        btn.setToolTip(tooltip)
        _apply_icon_button(btn, icon_name, tooltip, icon_color, icon_active_color)
        btn.clicked.connect(callbacks[callback_key])
        tools_layout.addWidget(btn)

    # Visual Divider between Ausrichtung and Einfügen
    tools_layout.addWidget(create_toolbar_divider(tools_container))

    # Zone 5: Einfügen (Image, Link, Table, Report Icon, Page Break)
    insert_buttons = (
        ("fa5s.image", "report.format_image", "Insert Image", "image"),
        ("fa5s.link", "report.format_link", "Link", "link"),
        ("fa5s.table", "report.format_table", "Table", "table"),
        ("fa5s.icons", "report.insert_icon", "Insert Icon", "icon"),
        ("fa5s.file-alt", "report.format_page_break", "Insert Page Break", "page_break"),
    )
    for icon_name, key, fallback, callback_key in insert_buttons:
        btn = QPushButton(tools_container)
        btn.setObjectName(f"btn_insert_{callback_key}")
        btn.setProperty("class", "SecondaryBtn FormatToolBtn ReportIconBtn")
        tooltip = t(key, fallback)
        btn.setToolTip(tooltip)
        _apply_icon_button(btn, icon_name, tooltip, icon_color, icon_active_color)
        if callback_key in callbacks and callbacks[callback_key]:
            btn.clicked.connect(callbacks[callback_key])
        tools_layout.addWidget(btn)

    main_layout.addWidget(tools_container)
    main_layout.addStretch()

    # -------------------------------------------------------------
    # Minimize / Expand Toggle Button (far right, under status label)
    # -------------------------------------------------------------
    btn_toggle = QPushButton(toolbar_widget)
    btn_toggle.setObjectName("btn_toggle_toolbar")
    btn_toggle.setProperty(
        "class", "SecondaryBtn FormatToolBtn ReportIconBtn ToolbarToggleBtn"
    )

    _collapsed = False

    def _apply_collapsed_state(*, notify: bool = True) -> None:
        tools_container.setVisible(not _collapsed)
        tooltip = (
            t("report.toggle_toolbar_expand", "Expand toolbar")
            if _collapsed
            else t("report.toggle_toolbar_collapse", "Collapse toolbar")
        )
        btn_toggle.setToolTip(tooltip)
        _apply_icon_button(
            btn_toggle,
            "fa5s.chevron-down" if _collapsed else "fa5s.chevron-up",
            tooltip,
            icon_color,
            icon_active_color,
        )
        if notify and on_toggle_collapse is not None:
            on_toggle_collapse(_collapsed)

    def _on_toggle_clicked() -> None:
        nonlocal _collapsed
        _collapsed = not _collapsed
        _apply_collapsed_state()

    def set_collapsed(collapsed: bool) -> None:
        nonlocal _collapsed
        if _collapsed == collapsed:
            return
        _collapsed = collapsed
        _apply_collapsed_state()

    def is_collapsed() -> bool:
        return _collapsed

    _apply_collapsed_state(notify=False)
    btn_toggle.clicked.connect(_on_toggle_clicked)
    main_layout.addWidget(btn_toggle)

    # Expose elements for programmatic access / testing
    toolbar_widget.tools_container = tools_container
    toolbar_widget.btn_toggle = btn_toggle
    toolbar_widget.set_collapsed = set_collapsed
    toolbar_widget.is_collapsed = is_collapsed

    return toolbar_widget

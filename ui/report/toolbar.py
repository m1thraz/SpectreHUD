"""Formatting-toolbar construction for the report editor."""

from collections.abc import Callable

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from core.i18n import t


def build_format_toolbar(parent: QWidget, callbacks: dict[str, Callable[[], None]]) -> QWidget:
    """Build the toolbar while keeping formatting behavior owned by its caller."""
    toolbar_widget = QWidget(parent)
    layout = QHBoxLayout(toolbar_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)

    buttons = (
        ("H1", "report.format_h1", "Heading 1", "heading_1"),
        ("H2", "report.format_h2", "Heading 2", "heading_2"),
        ("H3", "report.format_h3", "Heading 3", "heading_3"),
        ("B", "report.format_bold", "Bold", "bold"),
        ("I", "report.format_italic", "Italic", "italic"),
        ("</>", "report.format_code", "Inline Code", "code"),
        ("```", "report.format_code_block", "Code Block", "code_block"),
        ("•", "report.format_list", "Bullet List", "list"),
        ("1.", "report.format_numbered_list", "Numbered List", "numbered_list"),
        ("🔗", "report.format_link", "Link", "link"),
        ("▦", "report.format_table", "Table", "table"),
    )
    for label, key, fallback, callback_key in buttons:
        button = QPushButton(label, toolbar_widget)
        button.setProperty("class", "SecondaryBtn")
        button.setToolTip(t(key, fallback))
        button.clicked.connect(callbacks[callback_key])
        layout.addWidget(button)
    return toolbar_widget
